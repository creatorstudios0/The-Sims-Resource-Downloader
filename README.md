# The Sims Resource Downloader - Infinity Build

[![License: MIT](https://img.shields.io/github/license/Xientraa/The-Sims-Resource-Downloader?label=License&style=for-the-badge)](./LICENSE)

Production-ready custom build of **The Sims Resource Downloader**.

Original build by **Xientra**. This build adds a startup watermark, captcha prompt removal for TSR's currently broken captcha image response, organized download folders, colored console output, and GitHub-ready cleanup.

## Features

- Watches your clipboard for The Sims Resource links
- Downloads multiple items with a configurable active-download limit
- Uses fresh TSR download tickets when no reusable session is available
- Keeps downloaded archives intact
- Organizes downloads into `Mod Files`, `Tray Files`, and subfolders
- Prints a colored console log and branded startup banner

## Download Organization

The default download folder is `./Downloads`, which means a `Downloads` folder inside this project. In this local copy it resolves to:

```text
F:\The-Sims-Resource-Downloader-0.5.1\Downloads
```

Finished downloads are sorted into folders such as:

```text
Downloads\Mod Files\CAS
Downloads\Mod Files\Build Buy
Downloads\Mod Files\Script Mods
Downloads\Mod Files\Package Mods
Downloads\Tray Files\Lots
Downloads\Tray Files\Rooms
Downloads\Tray Files\Households
Downloads\Other Files\Archives
```

## Configuration

Edit [src/config.json](./src/config.json) to change runtime settings.

| Option | Description | Type |
| - | - | - |
| `downloadDirectory` | Directory where files are downloaded and organized. | string |
| `maxActiveDownloads` | Maximum number of concurrent downloads. | integer |
| `saveDownloadQueue` | Saves and reloads active, queued, and VIP-only URLs. | boolean |
| `organizeDownloads` | Sorts finished downloads into mod/tray subfolders. | boolean |
| `colorConsole` | Enables colored console output. | boolean |
| `watermark` | Text shown in the startup banner. | string |
| `debug` | Enables debug logging. | boolean |

## Setup

```sh
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt
```

Or run:

```sh
setup.bat
```

## Usage

```sh
start.bat
```

Then copy The Sims Resource item links. The downloader monitors your clipboard and queues valid links automatically.

## GitHub Notes

- Runtime files such as `Downloads/`, logs, saved sessions, and queues are ignored by Git.
- CI runs `python -m compileall src` on push and pull request.
- See [GITHUB_UPLOAD.md](./GITHUB_UPLOAD.md) for the exact upload checklist.

## Attribution

This project is based on the original **The Sims Resource Downloader** by Xientra and remains under the MIT License. See [NOTICE.md](./NOTICE.md) and [LICENSE](./LICENSE).
