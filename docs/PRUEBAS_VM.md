# Virtual machine testing guide

**Important:** always test in a VM before using the tool on a machine you care about.

## Preparation

1. Create a VM with **Windows 11** (and, if you can, another with **Windows 10**), at least 4 GB of RAM and 60 GB of disk.
2. Finish the Windows installation, update it and open the **Microsoft Store** once (it registers winget).
3. Turn on **System Protection** for drive C: (Control Panel → System → System Protection).
4. Install Python 3.10+ (or use the `.exe`).
5. **Take a snapshot** of the VM ("clean state").

## Test checklist

| # | Test | Expected result |
|---|---|---|
| 1 | Open the interface as administrator | *Home* tab with machine data, "Permissions: Administrator", winget "Available". |
| 2 | Open it **without** administrator rights | Red notice at the top; applying system changes is refused. |
| 3 | Optimization → **Basic**, preview | 9 changes; recycle bin at medium risk. |
| 4 | Apply **Basic** | The restore point is created; MB/GB are freed; the report appears on the Desktop. |
| 5 | **Restore a session** (Basic) | Finishes without errors. |
| 6 | Apply **Deep** | Pre-installed apps uninstalled, advertising off, telemetry tasks disabled. The Store, Calculator and Photos remain. |
| 7 | **Restore** the Deep session | Settings, tasks and startup come back. Apps: reinstall from the Store (expected). |
| 8 | Apply **Extreme** | Services adjusted; Game Mode on; minimal visual effects (sign out to see them). |
| 9 | Check the PC after Extreme | Internet, audio, Windows Update and Defender work. |
| 10 | **Restore** the Extreme session and reboot | Services and settings as at the start (compare with the snapshot). |
| 11 | Force a restore-point failure (turn off System Protection) | Aborts with a message and **changes nothing**. |
| 12 | Programs → **Verify catalog IDs** | "All IDs exist". If any fails, fix it in `instalador.py`. |
| 13 | Programs → **office** profile | Installs silently; report in `C:\ProgramData\BottiMint\instalaciones`. |
| 14 | Programs → **gamer** profile | Launchers and runtimes installed; Steam may ask for a reboot. |
| 15 | Go back to the snapshot and repeat on **Windows 10** | Same results (winget may require "App Installer"). |

Also check that choosing a level in the Optimization tab changes nothing by itself (it only shows the preview) and that the **Exit** button asks for confirmation.

## What to write down

- Real screenshots (they replace those in `docs/img/`).
- Any winget ID that does not exist or changes.
- Any change that was not reverted properly: open an *issue* with the session's `manifest.json`.
