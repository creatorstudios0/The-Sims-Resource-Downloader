# CreatorStudios Sims 4 Suite 2.1.0 — Release Candidate

**Status:** Draft / QA required. Do not label this release as tested or published until the Windows workflow and application smoke tests pass.

## Two editions in one release

- **CreatorStudios Sims 4 Mod Library 2.1.0** — Windows PySide6 desktop executable with the updated CreatorStudios interface, dashboard Quick Switch, Discover integrations, queue, library, backups and new background audit exports.
- **CreatorStudios Sims 4 Console 1.1.0** — source ZIP with clipboard-based downloader and offline commands for health diagnostics, library audits, queue inspection and settings inspection.
- **SHA256SUMS.txt** — SHA-256 checksums for both downloadable files.

## Highlights

### Desktop
- CreatorStudios violet-and-midnight visual identity.
- Prominent dashboard actions for discovery, library, health scans, and inventory export.
- Ctrl+K Quick Switch to navigate pages and common actions.
- Read-only mod and Tray inventory exports as JSON or CSV.
- Reports exact byte-identical duplicates, duplicate filenames, disabled files, and warnings.
- Background auditing so large libraries do not block the interface.

### Console
- `start.bat --console` runs the existing clipboard downloader.
- `start.bat --doctor` checks game folder locations and key settings without downloading.
- `start.bat --audit` checks files and duplicates without modifying game content.
- `start.bat --audit --output "audit.json"` exports a full file inventory report.
- `start.bat --queue` shows a saved-link count; `--queue --all` prints valid links.
- `start.bat --settings` prints basic non-secret settings.
- Legacy automatic replacement of source files was disabled, preventing accidental overwrites of console configuration during suite updates.

## Upgrade and data safety

- Copy existing `src/config.json`, `src/session`, `src/urls.txt`, and `Downloads/` to a separate backup before installing a new console ZIP. Do not overwrite your data with the fresh ZIP defaults.
- Desktop application state is stored outside this source ZIP; keep your profile backups.
- Duplicate findings are informational. No automated duplicate removal is provided.
- A shared filename or size alone does **not** establish a conflict.
- Third-party source websites and their access policies still apply. A CurseForge API key may be necessary for live discovery.

## Build and publication

The workflow `.github/workflows/suite-release.yml` runs a Python regression gate, repeats checks on Windows, builds the EXE using PyInstaller, creates a console ZIP, and generates SHA-256 checksums.

Run the workflow manually to obtain test artifacts without publishing a release. After review and integration, pushing a new `suite-v2.1.0` tag triggers creation of a **draft** GitHub Release with both editions attached. A maintainer must review and publish the draft.

## Required release QA

- Launch the bundled EXE on a clean 64-bit Windows machine, without a developer Python install.
- Validate Qt desktop import, login-independent navigation, Ctrl+K, catalog search (with approved credentials), and reviewed install workflow.
- Test a new install, a duplicated mod, a disabled mod, and a real profile backup/restore.
- Run console downloads and resume tests with approved samples, and inspect queue persistence.
- Run doctor, audit, JSON/CSV exports, and verify that game content stays unchanged.
- Verify packaged ZIP and EXE hashes against SHA256SUMS.txt.
- Verify upgraded installations preserve `src/config.json`, sessions, queue, downloads and existing desktop state.

## Credits

Maintained by CreatorStudios. Original The Sims Resource Downloader by Xientra, licensed under MIT. Retain LICENSE and NOTICE.
