#!/bin/bash
# Double-click in Finder to publish a new patch version to GitHub. Installed
# copies of Voicebox then update themselves (see scripts/release.sh).
cd "$(dirname "$0")" || exit 1
version="$(backend/venv/bin/python scripts/release_tools.py current 2>/dev/null)"
echo "Voicebox $version is the current version."
echo "This builds the next patch version and publishes it to GitHub."
read -r -p "Press Enter to release, or close this window to cancel. " _
./scripts/release.sh patch
status=$?
echo
read -n 1 -s -r -p "Press any key to close this window."
exit $status
