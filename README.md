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

## Windows desktop app

Double-click start.bat to open Sims 4 Mod Library. The launcher sets up a
virtual environment on first use. Use start.bat --console for the original
clipboard interface.

- In **Discover**, open The Sims Resource website and paste an item URL into **Download and install**. The existing **Download Queue** also lets you review TSR dependencies before downloading.
- In **Discover**, enter a [CurseForge API key](https://docs.curseforge.com/rest-api/) to search Sims 4 resources. The key is held in memory for the session. Set `CURSEFORGE_API_KEY` to provide it at launch. Projects with a supported, available download have an **Install** button. **Open project** opens the project on CurseForge.
- Select your Sims 4 user data folder in **Settings**. **Import files** and Discover installs send `.package` and `.ts4script` files to Mods, and household, lot, and room files to Tray. The installer opens ZIP archives and skips existing filenames. Close the game before making changes.
- Use **Refresh Library** after deleting or moving game files outside the app. **Install History** retains receipts and lets you undo managed installations.
- Open **Console** to see download, install, and scan messages or copy the current session log.

The desktop app imports the existing console queue once. It saves the new queue,
library, and install history in `desktop-state.json`. **Profile backups** in **My Mod Library**
lets you restore one of the last ten autosaves. Autosaves cover profiles and app records.
The app loads the most recent readable snapshot if the primary state is missing or corrupt.
Game files are stored in their respective game folders. RAR and 7z installation is unsupported.

### Settings and standalone build

The Settings tab detects The Sims 4 under Windows Documents, including
redirected and OneDrive Documents folders. It shows the Mods, Tray, and saves
paths and lets you choose the game user data folder manually. You can also
change the download folder, concurrent download limit, category sorting, and
clipboard watching.

The standalone Windows executable includes Python and Qt. It stores settings
and install history under %LOCALAPPDATA%\Sims 4 Mod Library and defaults to a folder named
Sims 4 Mod Library inside Windows Downloads. The source launcher continues
to use its project-local state.

## PySide6 workspace (2.0)

Run start.bat for the default desktop workspace, start.bat --classic for
the previous Tkinter interface, or start.bat --console for the original
clipboard workflow. The Qt workspace uses the existing desktop-state.json
file and keeps prior settings, installed files, receipts, and saved profiles.
The standalone build and the source launcher retain their respective data
locations. Close one interface before opening another with the same state.

To build from the project folder after start.bat sets up the venv:

    venv\Scripts\python.exe -m pip install PyInstaller
    powershell -ExecutionPolicy Bypass -File .\build-desktop.ps1

The executable is written to dist by default. Pass -Output and -Work to choose
a destination and a scratch build folder.

To run the regression suite:

    venv\Scripts\python.exe -m pip install pytest pytest-qt
    venv\Scripts\python.exe -m pytest -q

Branch ui/pyside6-modernization contains the migration. The local Git baseline
commit b249bc3 preserves the pre-migration source. The classic UI can still
read the shared state; it only presents the history features it originally had.
