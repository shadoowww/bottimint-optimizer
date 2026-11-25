# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Semantic versioning.

## [Unreleased]

## [1.3.1] - 2026-11-25

### Changed
- **Performance: the preview (`plan()`) of the Deep and Extreme levels is about 6x faster** (measured on a real Windows 10 machine: ~17 s -> ~3 s). The time was spent launching many separate PowerShell processes (~1-1.6 s each) for read-only queries:
  - Scheduled tasks: `tareas_telemetria` started one PowerShell per task (8 tasks, ~8-9 s). New `Entorno.tareas_estado()` reads all tasks with a single PowerShell call (~1 s) and filters them in Python, so no task name is ever interpolated into a script. Names are matched case-insensitively, like Windows does. If the listing fails or cannot be parsed, it falls back to the previous per-task query.
  - Store apps: the 5 app changes (`apps_bloat`, `apps_opcionales`, `apps_inicio`, `apps_xbox`, `apps_extra`) each ran `Get-AppxPackage` to get the same list (5 x ~1.6 s). New `Entorno.lecturas_en_cache()` makes `plan()` ask Windows only once. The cache lives only inside `plan()` and is removed when it ends; `aplicar()` does not use it because the list changes while apps are being removed.
  - `CambioTareas.aplicar()` also reads the task states in one call instead of one per task.
- The preview shows exactly the same results as before (same changes, same "applies / does not apply" and same default selection); only the waiting time changed. Verified against the previous per-task query on a real machine.
- Not changed: system detection at startup (`detectar_equipo()`, ~2.4 s, one PowerShell call), cleanups, restore points and the apply/restore logic.

### Tests
- 86 tests (was 82): `plan()` requests the app list only once and leaves no cache behind, nested cache use, `tareas_estado()` makes a single PowerShell call and handles case differences and missing tasks, and falls back to the per-task query when the output is unreadable or PowerShell returns a single object instead of a list.

## [1.3.0] - 2026-11-25

### Added
- **Deep level, cleaner Start menu (Windows 10 and 11):**
  - `apps_inicio`: removes OneNote, To Do, Maps, Voice Recorder, Paint 3D, LinkedIn, Copilot, Dev Home and Journal (and their Start tiles).
  - `apps_xbox`: removes the Xbox app and the Game Bar. It does not touch the Xbox sign-in component that some Microsoft Store games use. Warns that Win+G may show a prompt.
  - `apps_extra` (unchecked by default): Camera, Sticky Notes and the new Outlook.
  - `inicio_pines`: unpins **everything** from Start (Windows 10 tiles and Windows 11 pins) so it is left empty. It runs after the apps are removed. The previous layout cannot be restored.
  - Calculator, Photos, Clock, Media Player, Snipping Tool, Paint, Edge, Store and Windows Security stay protected.
- **Copilot:** `reg_copilot` turns Windows Copilot off by policy and hides its taskbar button (removing the app alone was not enough). Restorable.
- **OneDrive:** `onedrive` (unchecked by default) uninstalls OneDrive with Windows' own uninstaller and blocks its return by policy. It does not delete your OneDrive folder or the cloud. It refuses to run if Desktop/Documents/Pictures are stored in OneDrive, and reinstalls OneDrive on restore.
- **Startup programs:** the change now also disables OneDrive, Edge and Chrome preloading, OneNote, Phone Link, Xbox and Copilot, and keeps security, audio, network and drivers.
- The version is shown in the window title and in the header.
- Docs: Windows 11 and Windows 10 VM test report with before/after measurements (`docs/VM_TEST_REPORT.md`); README roadmap and results updated.
- Translations: all new texts in English (complete); status messages also in Russian, Japanese and Chinese.

### Changed
- **UI:** removed the empty detail box under the change list; the details of the selected change now show in the right-hand panel. The list gets the freed space.
- **UI:** clear status line: "Working… wait for it to finish" with a progress bar, then "Done. You can choose whatever you want." (or an error notice). The progress bar is only visible while working.
- Apps that Windows refuses to remove are now reported (as a failed change, or next to the count) instead of being silently skipped.

### Tests
- 82 tests (was 74): Start menu apps and protection, Xbox, Copilot, OneDrive (apply, restore, Known Folder Move guard), unpin, startup programs, failed app removal, title version, translations of the new dynamic messages.

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
