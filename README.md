# The Sims Resource Downloader & Sims 4 Mod Library

[![License: MIT](https://img.shields.io/github/license/creatorstudios0/The-Sims-Resource-Downloader?label=License&style=for-the-badge)](./LICENSE)

Download and organize The Sims 4 custom content on Windows. Choose the desktop library for a graphical workspace or the console downloader for clipboard-based downloads.

## Downloads

| Edition | Get it | What it does |
| --- | --- | --- |
| **Sims 4 Mod Library 2.0.0** | [Download Windows EXE](https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases/download/desktop-v2.0.0/Sims.4.Mod.Library.2.0.exe) · [Release notes](https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases/tag/desktop-v2.0.0) | Browse The Sims Resource and CurseForge, queue downloads, review installs, scan your library, and back up profiles. |
| **The Sims Resource Downloader v1.0.3** | [Console release](https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases/tag/v1.0.3) | Watch the clipboard for The Sims Resource links and download and sort files automatically. |

### Windows desktop app

Download and run `Sims.4.Mod.Library.2.0.exe` on 64-bit Windows. The unsigned executable includes its Python and Qt runtime.

### Console downloader

Extract the source ZIP from the console release and run `start.bat`. It installs the required dependencies on first run. Then copy a The Sims Resource item link to start downloading. If you already have the console downloader, run `start.bat` and accept the v1.0.3 update. This patch fixes corrupted resumed downloads and preserves existing `src/config.json` settings.

## Console features

- Watches your clipboard for The Sims Resource links
- Downloads multiple items with a configurable active-download limit
- Uses fresh TSR download tickets when no reusable session is available
- Keeps downloaded archives intact
- Organizes downloads into `Mod Files`, `Tray Files`, and subfolders
- Prints a colored console log and branded startup banner

## Console download organization

The console downloader saves files in `Downloads/` inside the project by default. Finished downloads are sorted into folders such as:

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

## Console configuration

In a fresh v1.0.3 installation, copy `src/config.defaults.json` to `src/config.json` before editing your settings. If `src/config.json` already exists, edit that file.

| Option | Description | Type |
| - | - | - |
| `downloadDirectory` | Directory where files are downloaded and organized. | string |
| `maxActiveDownloads` | Maximum number of concurrent downloads. | integer |
| `saveDownloadQueue` | Saves and reloads active, queued, and VIP-only URLs. | boolean |
| `organizeDownloads` | Sorts finished downloads into mod/tray subfolders. | boolean |
| `colorConsole` | Enables colored console output. | boolean |
| `watermark` | Text shown in the startup banner. | string |
| `debug` | Enables debug logging. | boolean |

## Project notes

- Runtime files such as `Downloads/`, logs, saved sessions, and queues are ignored by Git.
- CI runs `python -m compileall src` on push and pull request.
- See [GITHUB_UPLOAD.md](./GITHUB_UPLOAD.md) for the exact upload checklist.

## Attribution

This project is based on the original **The Sims Resource Downloader** by Xientra and remains under the MIT License. See [NOTICE.md](./NOTICE.md) and [LICENSE](./LICENSE).
