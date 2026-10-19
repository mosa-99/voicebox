#!/usr/bin/env bash
# One-time setup for scripts/release.sh: store the update-signing key's
# password in the macOS Keychain, then prove it unlocks the key and that the
# resulting signature matches the pubkey baked into the app.

source "$(dirname "$0")/mac-build-common.sh"

KEY_FILE="$HOME/.tauri/voicebox.key"
KEYCHAIN_SERVICE="voicebox-updater-signing"

[ -f "$KEY_FILE" ] || die "No signing key at $KEY_FILE.
Create one with: (cd tauri && bun run tauri signer generate -w ~/.tauri/voicebox.key)
and put the contents of ~/.tauri/voicebox.key.pub into plugins.updater.pubkey in tauri/src-tauri/tauri.conf.json."

step "Saving the signing key password in the Keychain"
echo "Type the password you chose for $KEY_FILE (twice):"
# With -w last and no value, `security` prompts, so the password never appears in ps.
security add-generic-password -U -a "$USER" -s "$KEYCHAIN_SERVICE" -l "Voicebox update signing key" -w

step "Checking the password against the key"
password="$(security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -w)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
echo "voicebox signing check" >"$tmp/check.txt"
if ! (cd tauri && TAURI_PRIVATE_KEY_PASSWORD="$password" bun run tauri signer sign -f "$KEY_FILE" "$tmp/check.txt") >"$tmp/sign.log" 2>&1; then
    security delete-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" >/dev/null 2>&1 || true
    die "That password does not unlock $KEY_FILE. Nothing was saved; run this script again."
fi
"$VENV_PY" scripts/release_tools.py verify "$tmp/check.txt" "$tmp/check.txt.sig"

step "Done. scripts/release.sh can now sign updates without asking."
