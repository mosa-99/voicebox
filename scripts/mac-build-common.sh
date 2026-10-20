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

# Code signing. An ad-hoc signed build gets a new identity every time, so
# macOS drops the Accessibility, Input Monitoring and Microphone grants after
# each update and dictation stops pasting. A self-signed certificate gives
# every build the same identity, so the grants survive updates. It lives in
# its own keychain (created on first use, password in the login Keychain).
# Gatekeeper doesn't trust it, which doesn't matter for an app built on this
# Mac or updated in place.
CODESIGN_IDENTITY="Voicebox Local Signing"
CODESIGN_KEYCHAIN="$HOME/Library/Keychains/voicebox-signing.keychain-db"
CODESIGN_KEYCHAIN_SERVICE="voicebox-codesign-keychain"

# codesign looks identities up through the user's keychain search list.
add_codesign_keychain_to_search_list() {
    local keychains=() line
    while IFS= read -r line; do
        line="${line#*\"}"
        line="${line%\"*}"
        [ -n "$line" ] && keychains+=("$line")
    done < <(security list-keychains -d user)
    security list-keychains -d user -s "${keychains[@]}" "$CODESIGN_KEYCHAIN"
}

create_codesign_identity() {
    step "Creating the code signing certificate \"$CODESIGN_IDENTITY\" (one time)"
    local tmp password
    tmp="$(mktemp -d)"
    # One random password for the keychain (kept in the login Keychain) and
    # the throwaway .p12 that carries the key into it.
    password="$(/usr/bin/openssl rand -hex 24)"
    cat >"$tmp/cert.cnf" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $CODESIGN_IDENTITY
[ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
EOF
    # /usr/bin/openssl (LibreSSL) writes a PKCS#12 that `security import` reads;
    # OpenSSL 3's default one fails with "MAC verification failed".
    /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 7300 -config "$tmp/cert.cnf" \
        -keyout "$tmp/key.pem" -out "$tmp/cert.pem" 2>/dev/null
    /usr/bin/openssl pkcs12 -export -inkey "$tmp/key.pem" -in "$tmp/cert.pem" \
        -name "$CODESIGN_IDENTITY" -passout "pass:$password" -out "$tmp/identity.p12"

    security create-keychain -p "$password" "$CODESIGN_KEYCHAIN"
    security set-keychain-settings "$CODESIGN_KEYCHAIN" # never auto-lock
    security unlock-keychain -p "$password" "$CODESIGN_KEYCHAIN"
    security import "$tmp/identity.p12" -k "$CODESIGN_KEYCHAIN" -P "$password" -T /usr/bin/codesign >/dev/null
    # Lets codesign use the key without a "codesign wants to access" prompt.
    security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$password" "$CODESIGN_KEYCHAIN" >/dev/null
    security add-generic-password -U -a "$USER" -s "$CODESIGN_KEYCHAIN_SERVICE" \
        -l "Voicebox code signing keychain" -w "$password"
    rm -rf "$tmp"
    add_codesign_keychain_to_search_list
}

# Unlock the signing keychain and point `tauri build` at the identity.
use_codesign_identity() {
    [ -f "$CODESIGN_KEYCHAIN" ] || create_codesign_identity
    local password
    password="$(security find-generic-password -a "$USER" -s "$CODESIGN_KEYCHAIN_SERVICE" -w 2>/dev/null)" ||
        die "The password for $CODESIGN_KEYCHAIN is missing from the login Keychain.
Delete that file and build again to create a new certificate (macOS will then ask for Accessibility once more)."
    security unlock-keychain -p "$password" "$CODESIGN_KEYCHAIN"
    security list-keychains -d user | grep -q "$CODESIGN_KEYCHAIN" || add_codesign_keychain_to_search_list
    export APPLE_SIGNING_IDENTITY="$CODESIGN_IDENTITY"
}

# build_app [extra `tauri build` args...]
build_app() {
    step "Building the Python server (PyInstaller, takes ~10 minutes)"
    just build-server
    # build_binary.py regenerates this tracked spec on every run; keep the tree clean.
    git checkout -- backend/voicebox-server.spec

    use_codesign_identity

    step "Building Voicebox.app and the .dmg"
    (cd tauri && bun run tauri build --bundles app,dmg "$@")
}
