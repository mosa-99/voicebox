#!/bin/bash
# Double-click in Finder to build Voicebox.dmg for this Mac (see scripts/build-dmg.sh).
cd "$(dirname "$0")" || exit 1
./scripts/build-dmg.sh
status=$?
echo
read -n 1 -s -r -p "Press any key to close this window."
exit $status
