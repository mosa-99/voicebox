#!/usr/bin/env bash
# Publish a new Voicebox version that every installed copy installs on its own.
#
# Bumps the version, builds a signed Voicebox.app + .dmg, checks the update
# signature against the app's pubkey, commits and tags the bump, pushes main,
# and creates a GitHub release with latest.json. Installed apps poll that
# file (tauri.conf.json -> plugins.updater.endpoints) and install the update
# in the background.
#
# Usage: scripts/release.sh [patch|minor|major]   (default: patch)
# One-time setup: scripts/setup-release-signing.sh
#
# Tags are named release-vX.Y.Z, not vX.Y.Z, so they never trigger the
# upstream release workflow (.github/workflows/release.yml, which needs
# upstream's Apple signing secrets) and never collide with upstream tags.

source "$(dirname "$0")/mac-build-common.sh"

part="${1:-patch}"
case "$part" in
    patch | minor | major) ;;
    *) die "usage: $0 [patch|minor|major]" ;;
esac

KEY_FILE="$HOME/.tauri/voicebox.key"
KEYCHAIN_SERVICE="voicebox-updater-signing"

require_tools
command -v gh >/dev/null 2>&1 || die "'gh' not found. Install it with: brew install gh"
gh auth status >/dev/null 2>&1 || die "gh is not logged in. Run: gh auth login"
[ -f "$KEY_FILE" ] || die "Update signing key $KEY_FILE is missing."
password="$(security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)" ||
    die "Signing password is not in the Keychain. Run once: scripts/setup-release-signing.sh"

step "Checking the repository"
[ "$(git branch --show-current)" = "main" ] || die "Releases are cut from main. Run: git switch main"
[ -z "$(git status --porcelain)" ] || die "There are uncommitted changes. Commit or stash them first."
git fetch -q origin main
git merge-base --is-ancestor origin/main HEAD || die "main is behind origin/main. Run: git pull"

repo="$("$VENV_PY" scripts/release_tools.py repo)"
current="$("$VENV_PY" scripts/release_tools.py current)"
previous_tag="$(git describe --tags --abbrev=0 --match 'release-v*' 2>/dev/null || true)"

version_files=()
while IFS= read -r file; do version_files+=("$file"); done < <("$VENV_PY" scripts/release_tools.py files)

new="$("$VENV_PY" scripts/release_tools.py bump "$part")"
tag="release-v$new"

committed=false
undo_bump() {
    if ! $committed; then
        git checkout -- "${version_files[@]}" 2>/dev/null || true
    fi
}
trap undo_bump EXIT

if git rev-parse -q --verify "refs/tags/$tag" >/dev/null || [ -n "$(git ls-remote --tags origin "refs/tags/$tag")" ]; then
    die "Tag $tag already exists."
fi
echo "Releasing $current -> $new to github.com/$repo"

export TAURI_SIGNING_PRIVATE_KEY="$KEY_FILE"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="$password"
build_app
unset TAURI_SIGNING_PRIVATE_KEY TAURI_SIGNING_PRIVATE_KEY_PASSWORD

step "Preparing release files"
dmg="$BUNDLE_DIR/dmg/Voicebox_${new}_${ARCH_FILE}.dmg"
app_tar="$BUNDLE_DIR/macos/Voicebox.app.tar.gz"
for f in "$dmg" "$app_tar" "$app_tar.sig"; do
    [ -f "$f" ] || die "Expected $f, but the build did not produce it."
done

out="$OUT_DIR/v$new"
rm -rf "$out"
mkdir -p "$out"
asset="Voicebox_${new}_${ARCH_FILE}.app.tar.gz"
cp "$dmg" "$out/"
cp "$app_tar" "$out/$asset"
cp "$app_tar.sig" "$out/$asset.sig"
"$VENV_PY" scripts/release_tools.py verify "$out/$asset" "$out/$asset.sig"

{
    echo "Voicebox $new for macOS (Apple Silicon)."
    echo
    echo "Installed copies update themselves. For a fresh install, download the .dmg below."
    if [ -n "$previous_tag" ]; then
        echo
        echo "Changes since ${previous_tag#release-}:"
        git log --no-merges --format='- %s' "$previous_tag..HEAD"
    fi
} >"$out/notes.md"

"$VENV_PY" scripts/release_tools.py latest-json \
    --version "$new" --tag "$tag" --repo "$repo" --asset "$asset" \
    --sig "$out/$asset.sig" --notes-file "$out/notes.md" \
    --platform "darwin-$ARCH_UPDATER" --out "$out/latest.json"

step "Committing and pushing $tag"
git add -- "${version_files[@]}"
git commit -q -m "chore(release): v$new"
committed=true
git tag -a "$tag" -m "Voicebox v$new"
git push -q origin HEAD:main
git push -q origin "$tag"

step "Publishing the GitHub release"
gh release create "$tag" --repo "$repo" --title "Voicebox v$new" --notes-file "$out/notes.md" --latest \
    "$out/$(basename "$dmg")" "$out/$asset" "$out/$asset.sig" "$out/latest.json" ||
    die "Upload failed. The tag is pushed; retry with:
  gh release create $tag --repo $repo --title 'Voicebox v$new' --notes-file '$out/notes.md' --latest '$out'/*.dmg '$out/$asset' '$out/$asset.sig' '$out/latest.json'"

published="$(curl -fsSL "https://github.com/$repo/releases/latest/download/latest.json" | "$VENV_PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])' || true)"
[ "$published" = "$new" ] || die "Release created, but latest.json on GitHub reports '$published' instead of $new."

step "Released Voicebox v$new"
echo "  https://github.com/$repo/releases/tag/$tag"
echo "  Installed copies pick it up on their next start (or within 6 hours) and install it automatically."
