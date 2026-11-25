# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Semantic versioning.

## [Unreleased]

## [1.3.3] - 2026-11-25

### Changed
- **Performance: checking the machine and choosing a level is much faster.** Measured on a real Windows 10 machine, against 1.3.2 (all read-only; nothing that changes the system was touched):

  | Step | Before | Now |
  |---|---|---|
  | Startup (detect machine + system info + winget + installed programs) | 4.8 s | 2.8 s |
  | Preview of Deep level, first time | 3.0 s | 1.0 s |
  | Preview of Extreme level, first time | 2.6 s | 1.0 s |
  | Going Basic > Deep > Extreme > Basic > Deep > Extreme | 10.6 s | 1.0 s |

  What was done:
  - **Startup reads run at the same time.** Detecting the machine, the system info, winget and the installed-programs list (`winget export`, the slowest) are independent: before they ran one after another.
  - **The preview checks the changes in parallel** (up to 8 read-only queries at once, in order-preserving fashion) and, when the machine was not detected yet, detects it at the same time.
  - **Switching level reuses what was already checked.** Levels are cumulative and what each change reports does not depend on the level, so going up a level only checks the new changes, and going down checks nothing. The "Update preview" button, applying and restoring still check everything again, because the system may have changed.
  - **The preview no longer reads each app's install location** (`InstallLocation` was ~1.1 s of the 1.6 s that `Get-AppxPackage` took; the preview only needs the names). Applying still reads it, because it is saved in the session to be able to re-register the app when restoring.
- The results are exactly the same as before: same changes, same "applies / does not apply" and same default selection (verified on a real machine for the three levels, with and without the reuse).
- `Entorno.listar_appx()` now takes `ubicacion` (default `True`, the previous behaviour). A custom environment that overrides it must accept that argument.

### Not changed (on purpose)
- **Applying a level** (restore point, removing apps, disabling tasks and services, restoring) runs exactly as before. Its slowest step, one PowerShell per app removed, could be batched, but it changes the system and it should be tested in a virtual machine first (`docs/PRUEBAS_VM.md`).
- `detectar_equipo()` (~2.3 s, one PowerShell call) is unchanged: it now overlaps with other reads instead of waiting for them.
- Measured and discarded: sending the app list as plain text instead of JSON (no faster, the cost is reading the install location, not the JSON).

### Tests
- 104 tests (was 95): the parallel preview gives the same results in the same order as checking one by one; reuse between levels (only new changes are checked, same result as checking everything, clearing it forces a new check); one single `Get-AppxPackage` even with parallel checks; one machine detection; a failing change does not break the rest; the preview does not ask for the install location but applying does (and saves it); the GUI checks each level once per session and "Update preview" checks again; startup detects installed programs only once.

## [1.3.2] - 2026-11-25

Security release (hardening round 2). Two weaknesses found in a code review with an attacker's mindset and **reproduced before patching**; nothing was exploited outside a test machine and no one has reported abuse. Details in `docs/AUDITORIA_SEGURIDAD.md` (items 15 and 16).

### Security
- **System locations are no longer taken from environment variables.** With UAC, the elevated process inherits the environment of whoever launched it. With `SystemRoot`, `USERPROFILE` or `ProgramData` changed:
  - the cleanup accepted real system folders (`C:\Windows\System32\drivers\etc`) and the real Documents folder, because the list of protected folders was built from those variables;
  - `powershell.exe`, `sc.exe`, `reg.exe`... were launched from a fake `System32` with administrator rights;
  - the manifests folder (`sesiones\`) followed a fake `ProgramData`.

  Now the Windows folder, System32, Program Files, `ProgramData`, the user profile and its personal folders (Documents, Desktop, Pictures, Videos, Music, Downloads, Contacts, Favorites; including the real redirected ones, for example to OneDrive) are asked to Windows with `GetWindowsDirectoryW`, `GetSystemDirectoryW` and `SHGetKnownFolderPath`. New module `bottimint/confiables.py`; it is also used by `limpieza.env()`/`join_env()`, the OneDrive checks, the Appx location check, the desktop report and the data folder of `nucleo.py` and `instalador.py`. Outside Windows (CI, tests) the variables are still used as a fallback. `TEMP` still comes from the environment (it is a user setting) but goes through the protected-folders check.
- **Executables are never searched for in the current folder or in PATH.** When a command was not in its expected folder (typically `winget`, which lives in each user's profile, for example when elevating with another administrator account), `resolver_exe()` returned the bare name and Windows looked for it first in the current folder (for example Downloads). A planted `winget.exe` would have run as administrator. Now it always returns an absolute path; if it does not exist the call fails with "command not found" (code 127) and nothing is run.
- **The current directory is removed from the executable and DLL search at startup** (`NoDefaultCurrentDirectoryInExePath=1` and `SetDllDirectory("")`, inherited by child processes), as an extra layer.

### Changed
- If `winget` is missing for the account running the program, the "winget not available" notice appears as before; nothing else changes for the user. Normal use (same account, `winget` installed) is unaffected.

### Tests
- 95 tests (was 86): the two tests that checked the old behaviour (trusting the environment) were rewritten to check the opposite; new ones cover manipulated variables against the real Windows API, a decoy `winget.exe` in the current folder, a missing `winget` for another account, the data folder, startup hardening, and a guard that fails if any module reads `SystemRoot`/`ProgramData`/`USERPROFILE`... directly again. Verified: 9 of them fail against the 1.3.1 code.

### Known limits (unchanged)
- A user who is already an administrator can do everything BottiMint does; this release protects against a changed environment and planted files, not against that.
- The `.exe` is still not code-signed, and PyInstaller's own bootloader loads its DLLs before this code runs.

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
