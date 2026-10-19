#!/usr/bin/env python3
"""Helpers for scripts/release.sh: version bumps, updater manifest, signature check.

Subcommands:
  current                      print the version from .bumpversion.cfg
  bump {patch,minor,major}     rewrite every file listed in .bumpversion.cfg, print the new version
  files                        print the files a release commit touches
  repo                         print "owner/name" from the updater endpoint in tauri.conf.json
  latest-json ...              write the latest.json manifest the Tauri updater reads
  verify FILE SIG              check a Tauri .sig against the pubkey in tauri.conf.json

`verify` needs the `cryptography` package, which the backend venv already has.
"""

import argparse
import base64
import configparser
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUMP_CFG = ROOT / ".bumpversion.cfg"
TAURI_CONF = ROOT / "tauri" / "src-tauri" / "tauri.conf.json"
CARGO_LOCK = ROOT / "tauri" / "src-tauri" / "Cargo.lock"


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def read_bump_config() -> configparser.RawConfigParser:
    cfg = configparser.RawConfigParser()
    cfg.read(BUMP_CFG, encoding="utf-8")
    return cfg


def current_version() -> str:
    return read_bump_config().get("bumpversion", "current_version")


def version_files(cfg: configparser.RawConfigParser) -> list[tuple[Path, str, str]]:
    files = []
    for section in cfg.sections():
        if section.startswith("bumpversion:file:"):
            path = ROOT / section.removeprefix("bumpversion:file:")
            files.append(
                (path, cfg.get(section, "search"), cfg.get(section, "replace"))
            )
    return files


def next_version(current: str, part: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", current)
    if not match:
        fail(f"current_version {current!r} is not MAJOR.MINOR.PATCH")
    major, minor, patch = (int(x) for x in match.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def rewrite(path: Path, old: str, new: str, count: int | None = None) -> None:
    # newline="" keeps the file's own line endings untouched.
    with path.open(encoding="utf-8", newline="") as f:
        text = f.read()
    if old not in text:
        fail(f"{path.relative_to(ROOT)}: {old!r} not found")
    text = text.replace(old, new) if count is None else text.replace(old, new, count)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def cmd_bump(part: str) -> None:
    cfg = read_bump_config()
    current = cfg.get("bumpversion", "current_version")
    new = next_version(current, part)
    for path, search, replace in version_files(cfg):
        rewrite(
            path,
            search.format(current_version=current, new_version=new),
            replace.format(current_version=current, new_version=new),
        )
    rewrite(
        BUMP_CFG, f"current_version = {current}", f"current_version = {new}", count=1
    )
    print(new)


def cmd_files() -> None:
    paths = [p for p, _, _ in version_files(read_bump_config())] + [
        BUMP_CFG,
        CARGO_LOCK,
    ]
    for path in paths:
        print(path.relative_to(ROOT))


def updater_config() -> dict:
    return json.loads(TAURI_CONF.read_text(encoding="utf-8"))["plugins"]["updater"]


def cmd_repo() -> None:
    endpoint = updater_config()["endpoints"][0]
    match = re.fullmatch(
        r"https://github\.com/([^/]+/[^/]+)/releases/latest/download/latest\.json",
        endpoint,
    )
    if not match:
        fail(f"updater endpoint is not a GitHub releases URL: {endpoint}")
    print(match.group(1))


def cmd_latest_json(args: argparse.Namespace) -> None:
    url = f"https://github.com/{args.repo}/releases/download/{args.tag}/{args.asset}"
    manifest = {
        "version": args.version,
        "notes": Path(args.notes_file).read_text(encoding="utf-8").strip(),
        "pub_date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": {
            args.platform: {
                "signature": Path(args.sig).read_text(encoding="utf-8").strip(),
                "url": url,
            }
        },
    }
    Path(args.out).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def decode_minisign_box(b64_text: str) -> list[str]:
    return base64.b64decode(b64_text.strip()).decode("utf-8").splitlines()


def cmd_verify(file: str, sig: str) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    pub_raw = base64.b64decode(decode_minisign_box(updater_config()["pubkey"])[1])
    pub_keyid, pub_key = (
        pub_raw[2:10],
        Ed25519PublicKey.from_public_bytes(pub_raw[10:42]),
    )

    lines = decode_minisign_box(Path(sig).read_text(encoding="utf-8"))
    sig_raw = base64.b64decode(lines[1])
    algorithm, sig_keyid, signature = sig_raw[:2], sig_raw[2:10], sig_raw[10:74]
    trusted_comment = lines[2].removeprefix("trusted comment: ").encode("utf-8")
    global_signature = base64.b64decode(lines[3])

    if sig_keyid != pub_keyid:
        fail("signature was made with a different key than the app's pubkey")
    data = Path(file).read_bytes()
    message = hashlib.blake2b(data).digest() if algorithm == b"ED" else data
    try:
        pub_key.verify(signature, message)
        pub_key.verify(global_signature, signature + trusted_comment)
    except InvalidSignature:
        fail(f"signature does not match {file}")
    print(f"signature OK (key {pub_keyid[::-1].hex().upper()})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("current")
    sub.add_parser("files")
    sub.add_parser("repo")
    bump = sub.add_parser("bump")
    bump.add_argument("part", choices=["patch", "minor", "major"])
    latest = sub.add_parser("latest-json")
    for name in ("version", "tag", "repo", "asset", "sig", "notes-file", "out"):
        latest.add_argument(f"--{name}", required=True)
    latest.add_argument("--platform", default="darwin-aarch64")
    verify = sub.add_parser("verify")
    verify.add_argument("file")
    verify.add_argument("sig")
    args = parser.parse_args()

    if args.command == "current":
        print(current_version())
    elif args.command == "bump":
        cmd_bump(args.part)
    elif args.command == "files":
        cmd_files()
    elif args.command == "repo":
        cmd_repo()
    elif args.command == "latest-json":
        cmd_latest_json(args)
    elif args.command == "verify":
        cmd_verify(args.file, args.sig)


if __name__ == "__main__":
    main()
