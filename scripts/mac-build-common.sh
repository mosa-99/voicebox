# Shared setup for build-dmg.sh and release.sh. Source it; it cds to the repo
# root and enables strict mode. Kept compatible with macOS's bash 3.2.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Finder-launched .command files don't always inherit the login shell's PATH.
export PATH="$HOME/.bun/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

BUNDLE_DIR="$ROOT/tauri/src-tauri/target/release/bundle"
VENV_PY="$ROOT/backend/venv/bin/python"
OUT_DIR="$ROOT/dist-mac"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die() {
    printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2
    exit 1
}

require_tools() {
    [ "$(uname -s)" = "Darwin" ] || die "These scripts build the macOS app and only run on macOS."
    local tool
    for tool in just bun cargo; do
        command -v "$tool" >/dev/null 2>&1 || die "'$tool' not found. See docs/content/docs/developer/setup.mdx."
    done
    [ -x "$VENV_PY" ] || die "Python environment missing. Run once: just setup"
}

# Tauri names the macOS arch "aarch64"/"x64" in bundle files and
# "aarch64"/"x86_64" in updater platform keys.
case "$(uname -m)" in
    arm64) ARCH_FILE="aarch64" ARCH_UPDATER="aarch64" ;;
    *) ARCH_FILE="x64" ARCH_UPDATER="x86_64" ;;
esac

# build_app [extra `tauri build` args...]
build_app() {
    step "Building the Python server (PyInstaller, takes ~10 minutes)"
    just build-server
    # build_binary.py regenerates this tracked spec on every run; keep the tree clean.
    git checkout -- backend/voicebox-server.spec

    step "Building Voicebox.app and the .dmg"
    (cd tauri && bun run tauri build --bundles app,dmg "$@")
}
