# CreatorStudios Sims 4 Suite v2.1.1

This release includes Sims 4 Mod Library 2.1.1 for 64-bit Windows and the portable Console 1.1.0 ZIP. `SHA256SUMS.txt` contains the hashes for both downloads.

## Desktop changes

- The redesigned Dashboard puts installed mods, queued downloads, completed installs, and storage at the top. Discover, file import, and the library are one click away. Library health, Patch Day, backups, and recent installs each have a dedicated section.
- Settings and the Download Queue clipboard watcher use sliding on/off switches. The controls support keyboard input and respect reduced motion.
- Discover keeps the current results if loading another page fails, so you can retry.
- Patch Day refreshes the library before reviewing script mods and matches the script file extension exactly.
- The app can open when optional backup metadata is malformed. Content backups ask you to select the real folder if Mods or Tray points to a filesystem link.

## Upgrade

Download and run the new Windows executable. The desktop app stores its settings and library data separately from the executable. Keep a backup of your library data and game content before upgrading.

For the console edition, extract the ZIP into a separate folder. Preserve your existing `src/config.json`, `src/session`, `src/urls.txt`, and `Downloads/` when moving to the new folder.
