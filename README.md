# The Sims Resource Downloader & Sims 4 Mod Library

[![License: MIT](https://img.shields.io/github/license/creatorstudios0/The-Sims-Resource-Downloader?label=License&style=for-the-badge)](./LICENSE)

Download and organize The Sims 4 custom content on Windows. Choose the desktop library for a graphical workspace or the console downloader for clipboard-based downloads.

## Downloads

| Edition | Get it | What it does |
| --- | --- | --- |
| **CreatorStudios Sims 4 Mod Library 2.1.0** | [Download Windows EXE](https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases/download/suite-v2.1.0/CreatorStudios.Sims.4.Mod.Library.2.1.0.exe) | Browse The Sims Resource and CurseForge, queue downloads, review installs, scan your library, and back up profiles. |
| **CreatorStudios Sims 4 Console 1.1.0** | [Download Console ZIP](https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases/download/suite-v2.1.0/CreatorStudios-Sims4-Console-1.1.0.zip) | Watch the clipboard for The Sims Resource links and download and sort files automatically. |

Release notes and SHA-256 checksums are available on the [Suite 2.1.0 release page](https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases/tag/suite-v2.1.0).

### Windows desktop app

Download and run `CreatorStudios.Sims.4.Mod.Library.2.1.0.exe` on 64-bit Windows. The unsigned executable includes its Python and Qt runtime.

### Console downloader

Extract the Console ZIP into a separate folder and open `Run Console.bat`. The launcher installs the required dependencies on first run. Copy a The Sims Resource item link to start downloading.

If you’re upgrading, back up your existing `src/config.json`, `src/session`, `src/urls.txt`, and `Downloads/` before transferring them into the new installation.

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

Edit `src/config.json` to change console settings.

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

## Sims 4 Mod Library for Windows

Run `start.bat` to open the desktop app, `start.bat --console` for the clipboard downloader, or `start.bat --classic` for the original desktop interface. In the app, set the Sims 4 user data folder under **Settings**. **Import files** installs supported ZIPs and loose content into Mods or Tray. **Refresh Library** reconciles files that were deleted outside the app. **Profile backups** recover app records. **Console** shows recent activity.

To use browser handoffs, build and run the packaged app, then select **Enable website links** in Settings. Enter an approved CurseForge API key in **Discover** or launch with `CURSEFORGE_API_KEY` set. Clicking **Open in Mod Library** reviews the requested file, downloads it after confirmation, and shows a file-by-file install preview. Close the preview to leave the downloaded file available without installing it.

```powershell
venv\Scripts\python.exe -m pip install PyInstaller pytest pytest-qt
powershell -ExecutionPolicy Bypass -File .\build-desktop.ps1
venv\Scripts\python.exe -m pytest -q
```

Dashboard **Patch Day Checkup** flags game version changes. **Create backup ZIP** saves the current Mods and Tray content, including subfolders and quarantined files. Use **Open last backup** to locate the archive and extract selected files into their matching folders.

## Discover website

From the `website` directory, run `node build.mjs` and `node dev.mjs`. The local preview uses sample data and is available at `http://127.0.0.1:8766`. Use `node --test catalog.test.mjs` after building to verify the catalog.

The private preview uses fictional listings and original generated artwork from a six-panel brief featuring a cottage, hairstyle, kitchen, outfit, family, and study. Set the approved `CURSEFORGE_API_KEY` on the server to enable live Sims 4 search. That key is read only by the Worker. Source sites handle files that are unavailable for third-party downloads. The site links to The Sims Resource and does not host its content.

For an editable Apache/XAMPP sample catalog, run `node build.mjs` and `node export-apache.mjs C:/xampp/htdocs/sims4-mod-library` from `website`. Use a new destination when exporting so existing edits are preserved.

## Attribution

This project is based on the original **The Sims Resource Downloader** by Xientra and remains under the MIT License. See [NOTICE.md](./NOTICE.md) and [LICENSE](./LICENSE).

## CreatorStudios desktop interface

The Windows Qt desktop preview has a CreatorStudios visual refresh: a violet-accented
workspace, a dashboard with direct library/discovery/scan actions, and a keyboard-driven
**Quick Switch**. Press **Ctrl+K** to search pages and actions (Enter runs the selected
command; Escape closes the dialog). Existing downloads, installs, profiles, backups,
settings, and console operations use their previous implementations.

The CreatorStudios interface retains the existing download, install, backup and console features.

### Verification on Windows

```powershell
venv\Scripts\python.exe -m compileall src
venv\Scripts\python.exe -m unittest discover -s tests -p test_palette_search.py -v
venv\Scripts\python.exe -m pytest -q
```

Smoke-test at 785px minimum width and at 1320px: sidebar collapse, Ctrl+K matching,
Enter/Escape behavior, keyboard navigation, library selection and install preview,
folder scans, backups and restores, and readability with custom accent colors.

## CreatorStudios Sims 4 Suite 2.1.0

**Desktop 2.1.0 + Console 1.1.0.** The release workflow packages a Windows desktop
executable and separate portable console ZIP in the same GitHub Release. See
[release notes](./RELEASE_NOTES_2.1.0.md). The release workflow publishes after
the default-branch build and test gates pass; manual QA remains recommended.

### Windows console commands

```bat
Run Console.bat
start.bat --console
start.bat --doctor
start.bat --audit
start.bat --audit --output "C:\\Users\\Public\\CreatorStudios-Audit.json"
start.bat --queue --all
start.bat --settings
```

The **audit** is read-only: it counts installed .package, .ts4script and Tray files,
including .disabled mods, flags exact byte-identical groups, and can export JSON or
CSV. Duplicate results are advisory; the program never deletes duplicates. Folder
scanning skips links and limits the number of indexed files.

### Desktop audit

Use **Dashboard → Export mod audit** or **Settings → Library management → Export
audit report** to save a report. The work runs outside the UI thread. Press
**Ctrl+K** to open CreatorStudios Quick Switch.

### Developer checks

```powershell
python -m pip install -r requirements.txt pytest pytest-qt
$env:PYTHONPATH="src;scripts"
$env:QT_QPA_PLATFORM="offscreen"
python -m compileall src scripts tests
python -m pytest -q
python scripts/package_console.py
```

On Windows, prepare the venv, install PyInstaller and run
`powershell -ExecutionPolicy Bypass -File .\\build-desktop.ps1`.
