# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Semantic versioning.

## [1.2.0] - 2026-11-24

### Added
- **Install winget from the app:** if winget is missing, the Home and Programs tabs show a clear notice with an **Install winget** button (and pressing *Install selected* offers it too). It first tries to register the App Installer that ships with Windows; if it is not there, it downloads it from Microsoft's official servers (fixed `github.com/microsoft` and `aka.ms` URLs), Windows verifies the package signature and the publisher is checked afterwards. It always asks for confirmation first; nothing is downloaded automatically.
- **Extreme / Gaming:** new change *Remove all Windows animations* (menus, windows, lists, tooltips, fades, smooth scrolling; applied instantly) that **keeps ClearType font smoothing on** so text stays sharp, and new change *Solid black desktop background* (no wallpaper image; the original wallpaper and color come back on restore).
- *Minimal visual effects* now also turns off Aero Peek, list-selection fade and the menu delay.
- `python -m bottimint programas winget` now installs winget when it is missing.
- README: US flag for the English link, "How to install" heading, and the standalone VM section replaced by a short pointer in the Security section.
- Tests: winget installation (register / download / failure / official hosts only), animations + black background (apply, restore, tampered manifest). 74 in total.

## [1.1.1] - 2026-11-24

### Changed
- **Optimization:** the "Apply selected changes (N)" button now sits above the checkbox list (always visible), with a counter of selected changes; it is disabled when nothing is selected. Choosing a level only shows the (read-only) preview and never applies anything; the log message says so.
- More compact panels and log so everything fits on small screens.
- **Documentation is now in English** (the Spanish README is kept as `README.es.md`). README screenshots updated; internal publishing files were removed from the repository.

## [1.1.0] - 2026-11-24

### Changed
- The app is now called **BottiMint** (package `bottimint`, `BottiMint.exe`, `C:\ProgramData\BottiMint`).
- Universal use: the "technician/business" details and the mentions of "client" were removed; the `tecnico` profile became `herramientas`.

### Added
- **Light and dark themes** (☀ / ☾ buttons in the header), mint accent, follows the Windows mode by default and dark title bar.
- **Languages:** Spanish, English (complete), Russian, Japanese and Chinese (interface; long descriptions fall back to English). Selector in the header.
- Preferences (language/theme) stored per user in `%APPDATA%\BottiMint\ajustes.json`, validated against closed lists.
- Build provenance attestation (GitHub) on releases and `bandit` static analysis in CI.
- **"Exit" button** (⏻) with confirmation; it warns specially if a task is running. Closing with the X also asks for confirmation.
- **Rounded interface:** buttons, level selectors, cards and dialogs with rounded corners (`bottimint/widgets.py`). Own dialogs with light/dark theme.
- `docs/AUDITORIA_SEGURIDAD.md` (security audit).

### Security
- Cleanup: own directory walker that never enters junctions/links; protection of critical folders even if an environment variable points there.
- System commands by absolute System32 path; data folder with link checks and restricted permissions.
- Restore: every manifest entry is validated against the catalog; session ID validated; atomic writes.
- winget ID validation, PowerShell value escaping, private temporary folder.
- `descargar_y_ejecutar.ps1`: validates parameters and URLs, supports `-Tag`, verifies the hash on a write-locked file handle.
- New tests: `tests/test_seguridad.py`, `tests/test_idiomas.py` (55 in total).

## [1.0.0] - 2026-11-24

### Added
- **Tiered optimization** (Basic, Deep, Extreme/Gaming), cumulative, with an explanation and the consequences of every change.
- **Mandatory, verified restore point** before applying; if it cannot be created, nothing is modified.
- **Per-session restore:** manifest with the previous state of registry, services, scheduled tasks, startup and power plan.
- Machine-dependent options (SSD/HDD, battery, printers) to preselect only what makes sense.
- **Programs module** (winget): curated catalog with a Gaming category, office/gamer/tools profiles, installed-program detection, ID verification and bulk update.
- Unified **graphical interface** (tkinter) with mandatory confirmation of the consequences.
- Reports (Desktop and `C:\ProgramData\BottiMint`).
- CI (tests on Windows and Linux) and automatic release of the `.exe` with SHA256.
- `descargar_y_ejecutar.ps1` script with integrity verification.
