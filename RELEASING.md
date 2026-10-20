# Building and releasing Voicebox for macOS

This fork ships its own macOS builds. Installed copies update themselves from
this repository's GitHub releases.

## Build a .dmg

Double-click **`Build DMG.command`** in Finder, or run:

```bash
just dmg            # build dist-mac/Voicebox_<version>_aarch64.dmg
just dmg --install  # build it and replace /Applications/Voicebox.app
```

This builds the Python server with PyInstaller, then the Tauri app and the
.dmg. It does not change the version or publish anything.

## Publish an update

Double-click **`Release Update.command`**, or run:

```bash
just release          # 0.6.1 -> 0.6.2
just release minor    # 0.6.1 -> 0.7.0
just release major    # 0.6.1 -> 1.0.0
```

`scripts/release.sh` does the following:

1. Checks that you are on `main` with a clean tree that is not behind `origin/main`.
2. Bumps the version in every file listed in `.bumpversion.cfg`.
3. Builds a signed `Voicebox.app`, its update bundle (`.app.tar.gz` + `.sig`) and the .dmg.
4. Verifies the update signature against `plugins.updater.pubkey` in `tauri/src-tauri/tauri.conf.json`.
5. Commits the version bump, tags it `release-vX.Y.Z` and pushes both.
6. Creates a GitHub release containing the .dmg, the update bundle and `latest.json`.

If any step before the commit fails, the version bump is undone.

Tags use `release-v*` rather than `v*`. That keeps them from triggering the
upstream `.github/workflows/release.yml`, which needs upstream's Apple signing
secrets, and keeps them separate from upstream's tags.

## How installed copies update

On start, and every 6 hours while it runs, the app fetches
`https://github.com/<owner>/<repo>/releases/latest/download/latest.json`.
When that file names a newer version, the app downloads the update, checks its
signature and replaces itself in the background. The new version runs from the
next start. **Settings → App Updates → Restart Now** switches to it right away.

## One-time setup

- The update signing key lives at `~/.tauri/voicebox.key`. Back it up together
  with its password. Without them, installed copies can never receive another
  update.
- Store the key's password in the macOS Keychain once:

  ```bash
  just release-setup
  ```

- `gh` must be logged in (`gh auth status`).

Builds are signed with a self-signed certificate, "Voicebox Local Signing",
not with an Apple Developer ID. The first build creates it in
`~/Library/Keychains/voicebox-signing.keychain-db` and keeps that keychain's
password in the login Keychain (service `voicebox-codesign-keychain`). Every
build signed with it has the same identity, so macOS keeps the microphone,
Accessibility and Input Monitoring permissions across updates. (Ad-hoc signed
builds got a new identity each time, and dictation silently stopped pasting
after an update until the permissions were granted again.) If the keychain
is deleted, the next build creates a new certificate and the permissions have
to be granted once more.

Gatekeeper doesn't trust that certificate. On another Mac, the first launch of
a downloaded .dmg needs **System Settings → Privacy & Security → Open
Anyway**. Updates after that install on their own.
