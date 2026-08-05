# Changelog

All notable changes to this project will be documented in this file.

---

## [0.5.2-production] — 2026-08-04

### Added
- **Retry logic with exponential backoff** in `TSRDownload.py` — failed downloads are automatically retried up to 3 times before giving up, with a growing delay between each attempt.
- **Request timeouts** on all network calls across `TSRDownload.py`, `TSRSession.py`, and `TSRUrl.py` — prevents the tool from hanging forever if TSR's servers are slow or unresponsive.
- **Duplicate file detection** — before downloading, the tool now scans all organized subfolders to check if the file already exists, skipping if found.
- **Config validation on startup** — `config.json` is now validated when the tool starts. Invalid types or missing keys print a clear, human-readable error pointing to exactly what needs to be fixed.
- **Session download stats** — after all active downloads complete, the tool logs a summary: `X downloaded, Y failed`.
- **One-click launcher** (`start.bat`) — combined `setup.bat` and `start.bat` into a single launcher that automatically installs Python if missing, repairs broken virtual environments, and checks GitHub for updates.
- **GitHub update check** in `start.bat` — compares the running version against the latest release on GitHub and prompts to update if a newer version is available.

### Fixed
- **Stale virtual environment detection** — `start.bat` now tests if the venv Python actually works. If it was created on a different machine, the old environment is deleted and rebuilt automatically.
- **File descriptor leaks** — all `open()` calls in `main.py`, `config.py`, and `TSRDownload.py` now use `with` context managers.
- **Multiprocessing resource leak** — replaced per-download `Pool(1)` instances (which were never closed) with a single `ThreadPoolExecutor`.
- **Variable shadowing** — renamed loop variable `id` to `item_id` in `main.py` to avoid shadowing Python's built-in `id()`.
- **Clipboard crash protection** — `clipboard.paste()` is now wrapped in a try/except so non-text clipboard content doesn't crash the tool.

---

## [0.5.1-production] — Initial production release

### Added
- Startup watermark and branded console banner.
- Captcha prompt removal for TSR's broken captcha image response.
- Organized download folders (`Mod Files`, `Tray Files`, `Other Files` with subcategories).
- Colored console output via ANSI escape codes with Windows VT100 support.
- GitHub-ready project cleanup (`.gitignore`, CI workflow, `NOTICE.md`).
- `saveDownloadQueue` option to persist and reload active/queued/VIP URLs across sessions.

### Changed
- Based on the original **The Sims Resource Downloader** by Xientra (MIT License).
