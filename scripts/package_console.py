"""Build a clean portable CreatorStudios console ZIP from repository source."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import argparse
import hashlib

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ("README.md", "LICENSE", "NOTICE.md", "CHANGELOG.md", "requirements.txt", "requirements-console.txt", "start.bat", "Run Console.bat")
CONSOLE_VERSION = "1.1.0"


def collect(root):
    files = [root / name for name in DOCUMENTS]
    files.extend(sorted((root / "src").glob("*.py")))
    files.append(root / "src" / "config.json")
    files.extend(sorted(path for path in (root / "src" / "assets").glob("*") if path.is_file()))
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing release files: " + ", ".join(missing))
    return files


def build(output, root=ROOT):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = f"CreatorStudios-Sims4-Console-{CONSOLE_VERSION}"
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for path in collect(root):
            archive.write(path, f"{prefix}/{path.relative_to(root).as_posix()}")
        archive.writestr(f"{prefix}/.version", f"v{CONSOLE_VERSION}\n")
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    return output, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=f"dist/CreatorStudios-Sims4-Console-{CONSOLE_VERSION}.zip")
    args = parser.parse_args()
    output, sha = build(args.output)
    print(f"Packed {output}")
    print(f"SHA256 {sha}  {output.name}")


if __name__ == "__main__":
    main()
