"""CreatorStudios console tools: offline diagnostics and mod-library reports.

Does not contact The Sims Resource, load a session, or change game content.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

from library_insights import format_summary, scan_inventory, write_report

PROJECT = Path(__file__).resolve().parent.parent


def default_game():
    home = Path.home()
    candidates = [
        home / "Documents" / "Electronic Arts" / "The Sims 4",
        home / "OneDrive" / "Documents" / "Electronic Arts" / "The Sims 4",
    ]
    return next((path for path in candidates if path.is_dir()), candidates[0])


def settings_file():
    return Path(__file__).with_name("config.json")


def read_config():
    with settings_file().open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError("Console configuration must be a JSON object")
    return value


def resolved_download_folder(config):
    raw = os.path.expandvars(os.path.expanduser(config.get("downloadDirectory", "./Downloads")))
    folder = Path(raw)
    return folder.resolve() if folder.is_absolute() else (PROJECT / folder).resolve()


def queue_info(queue_file):
    if not queue_file.is_file():
        return {"count": 0, "urls": [], "file": str(queue_file)}
    from urllib.parse import urlparse
    urls = []
    for item in queue_file.read_text(encoding="utf-8-sig").splitlines():
        candidate = item.strip()
        try:
            parsed = urlparse(candidate)
        except ValueError:
            continue
        if (parsed.scheme == "https" and parsed.hostname in
                {"www.thesimsresource.com", "thesimsresource.com"} and
                parsed.username is None and parsed.password is None and
                parsed.path.startswith("/downloads/")):
            if candidate not in urls:
                urls.append(candidate)
    return {"count": len(urls), "urls": urls, "file": str(queue_file)}


def diagnostics(config, game):
    downloads = resolved_download_folder(config)
    results = [
        ("Python runtime", sys.version.split()[0], True),
        ("Downloads folder", str(downloads), downloads.is_dir()),
        ("Sims 4 user folder", str(game), game.is_dir()),
        ("Mods folder", str(game / "Mods"), (game / "Mods").is_dir()),
        ("Tray folder", str(game / "Tray"), (game / "Tray").is_dir()),
        ("Queue persistence", str(config.get("saveDownloadQueue", True)), True),
        ("Concurrent downloads", str(config.get("maxActiveDownloads", 4)),
         type(config.get("maxActiveDownloads", 4)) is int and
         1 <= config.get("maxActiveDownloads", 4) <= 10),
    ]
    return results


def build_parser():
    parser = argparse.ArgumentParser(
        prog="CreatorStudios Console",
        description="Offline tools for your Sims 4 content. Run start.bat --console for clipboard downloads.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Verify game paths and console settings")
    doctor.add_argument("--game", type=Path, help="The Sims 4 user data folder")
    audit = sub.add_parser("audit", help="Scan Sims 4 content and report exact duplicate files")
    audit.add_argument("--game", type=Path, help="The Sims 4 user data folder")
    audit.add_argument("--mods", type=Path, help="Custom Mods directory")
    audit.add_argument("--output", type=Path, help="Export report as .json or .csv")
    queue = sub.add_parser("queue", help="Show saved console download links (read-only)")
    queue.add_argument("--all", action="store_true", help="List each saved URL")
    sub.add_parser("settings", help="Show safe, non-secret console settings")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        config = read_config()
        game = (getattr(args, "game", None) or default_game()).expanduser()
        print("\n CREATORSTUDIOS  /  SIMS 4 CONSOLE\n" + "-" * 49)
        if args.command == "doctor":
            for name, value, okay in diagnostics(config, game):
                print(f" {'OK' if okay else 'CHECK':5}  {name}: {value}")
            print("\nTip: Missing game folders may be normal if The Sims 4 is not installed.")
        elif args.command == "audit":
            report = scan_inventory(args.mods or game / "Mods", game / "Tray")
            print(format_summary(report))
            for group in report["duplicate_groups"][:20]:
                print(f"  Duplicate ({group['bytes_per_file']:,} bytes each):")
                for path in group["paths"]:
                    print(f"    {path}")
            if len(report["duplicate_groups"]) > 20:
                print("  More groups omitted from screen output; export for all results.")
            for warning in report["warnings"][:10]:
                print(f"  Warning: {warning}")
            if args.output:
                print("Report saved:", write_report(report, args.output))
            print("No files were modified.")
        elif args.command == "queue":
            info = queue_info(Path(__file__).with_name("urls.txt"))
            print(f"{info['count']} valid, unique saved TSR links")
            if args.all:
                for item in info["urls"]:
                    print(" ", item)
            print("No queued downloads were started.")
        else:
            print("Downloads folder:", resolved_download_folder(config))
            for key in ("maxActiveDownloads", "saveDownloadQueue", "organizeDownloads",
                        "colorConsole", "watermark", "debug"):
                print(f" {key}: {config.get(key, 'not set')}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
