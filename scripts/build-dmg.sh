#!/usr/bin/env bash
# Build Voicebox for this Mac in one step: Python server, Voicebox.app and .dmg.
# The .dmg is copied to dist-mac/ and shown in Finder.
#
# Usage: scripts/build-dmg.sh [--install]
#   --install   also replace /Applications/Voicebox.app with the new build
#
# This builds an unpublished local copy. To ship an update that installed
# copies pick up on their own, use scripts/release.sh instead.

source "$(dirname "$0")/mac-build-common.sh"

install=false
case "${1:-}" in
    "") ;;
    --install) install=true ;;
    *) die "usage: $0 [--install]" ;;
esac

require_tools
version="$("$VENV_PY" scripts/release_tools.py current)"

# Updater bundles need the signing key; a local .dmg doesn't, so skip them.
build_app --config '{"bundle":{"createUpdaterArtifacts":false}}'

dmg="$BUNDLE_DIR/dmg/Voicebox_${version}_${ARCH_FILE}.dmg"
[ -f "$dmg" ] || die "Expected $dmg, but the build did not produce it."
mkdir -p "$OUT_DIR"
cp "$dmg" "$OUT_DIR/"

if $install; then
    step "Installing to /Applications"
    osascript -e 'tell application "Voicebox" to quit' >/dev/null 2>&1 || true
    rm -rf /Applications/Voicebox.app
    ditto "$BUNDLE_DIR/macos/Voicebox.app" /Applications/Voicebox.app
fi

step "Done: $OUT_DIR/$(basename "$dmg")"
open -R "$OUT_DIR/$(basename "$dmg")"
