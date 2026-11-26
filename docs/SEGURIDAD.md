# Security

BottiMint changes the system with administrator rights, so distrust is reasonable. This document explains what the program
does, what defenses the code has, and **how you can check it yourself** without taking anyone's word for it.

## What data it handles

- **It sends no telemetry or data to any server.** The only network activity is `winget` when installing or updating programs (and, only if you press **Install winget** and it is missing, the download of the App Installer from Microsoft's servers; and, if you use it, the optional `descargar_y_ejecutar.ps1` script, which talks to GitHub).
- No accounts, no ads, no "premium version".
- What it stores stays **local**:
  - `C:\ProgramData\BottiMint\` → sessions (manifests used to undo changes) and reports. With administrator rights the folder is restricted to **SYSTEM and Administrators**.
  - `%APPDATA%\BottiMint\ajustes.json` → only your language and theme. Nothing personal.
  - A text report on the Desktop.

## How to verify the program is safe (do it, don't just trust)

1. **SHA256 hash.** Every release publishes `BottiMint.exe` and `BottiMint.exe.sha256`. In PowerShell:
   `Get-FileHash .\BottiMint.exe -Algorithm SHA256` and compare with the `.sha256` file. If a single character differs, do not run it.
2. **VirusTotal.** Upload the `.exe` to <https://www.virustotal.com> (or search by its hash without uploading anything). `.exe` files built with PyInstaller sometimes get 1–3 false positives from heuristic engines; if you see many, don't use it and report it.
3. **Provenance (GitHub attestation).** Releases are built in GitHub Actions and carry a *build provenance attestation*: cryptographic proof that the `.exe` came from this repository and this commit, not from someone's PC.
   `gh attestation verify BottiMint.exe -R shadoowww/bottimint-optimizer`
4. **Build it yourself.** You don't need to trust the `.exe`: the program is pure Python with no external dependencies. `python -m bottimint` runs it from source, and `scripts\BottiMint.bat` / `Compilar_exe.bat` build the `.exe` on your machine. The whole code base can be read in an afternoon.
5. **Try it in a VM first** with a snapshot ([PRUEBAS_VM.md](PRUEBAS_VM.md)). Before touching anything, the program creates a Windows restore point and verifies it exists; if it cannot, it aborts without changing anything.

## Permissions

- It needs **administrator** rights to change services, system registry, scheduled tasks and to create the restore point. Without administrator rights those tasks are **skipped** (never forced).
- User-level settings (advertising, visual effects, Game DVR) are applied to the **user running the program**. If you elevate with a different administrator account, those settings go to that account.

## Code defenses (security review)

| Risk | Defense |
|---|---|
| **Deleting outside the intended folders** through *junctions* or symbolic links (on Windows `os.walk` follows junctions) | Own directory walker that **never enters links or reparse points**; if it finds one it removes the link itself and leaves its target alone. A root folder that is a link is ignored. |
| **Manipulated environment variables** (`TEMP` pointing at `System32` or Documents) | List of protected folders (System32, WinSxS, Program Files, Documents, Desktop, Pictures, Downloads, OneDrive…) and of drive roots; paths are resolved with `realpath` before comparing. |
| **Environment used to locate the system** (with UAC the elevated process inherits the environment of whoever launched it: a changed `SystemRoot`, `USERPROFILE` or `ProgramData` could unprotect real folders, run a fake `powershell.exe` as administrator or redirect the manifests) | The Windows folder, System32, Program Files, `ProgramData`, the user profile and its personal folders are asked to Windows itself (`GetSystemDirectoryW`, `SHGetKnownFolderPath`; `confiables.py`), never read from environment variables. A test fails if any module reads those variables directly. Only `TEMP` is still taken from the environment, and it goes through the protected-folders check. |
| **Executable hijacking** (a `powershell.exe`, `sc.exe` or `winget.exe` planted in the current folder or in PATH, run as administrator) | System commands are launched by **absolute path** from `System32`; if one does not exist the call fails ("command not found") instead of falling back to the bare name, which Windows would search for in the current folder and in PATH. At startup the current directory is also removed from the executable and DLL search (`NoDefaultCurrentDirectoryInExePath`, `SetDllDirectory("")`). Never `shell=True`, always argument lists (a test enforces this). |
| **Data folder pre-created by another user** (a junction in `ProgramData`) | It is rejected if it is a link; with administrator rights the owner is set and the permissions are restricted (`icacls`), also for everything already inside (walked top-down, never following links). If that fails, nothing is changed. |
| **Tampered restore manifest** (someone edits the JSON so that, when restoring with privileges, arbitrary registry keys/services get touched) | On restore, **every entry is validated against the catalog**: the registry can only touch the keys of the original change, services and tasks must be those of the change, GUIDs and names are checked with strict expressions, apps are only registered from `WindowsApps`, registry types and values must be of the same kind as the setting, and only startup entries of that change are re-enabled. Anything that does not match is ignored. The session ID is validated (no `..`). The manifest is written **atomically**. |
| **PowerShell injection** | Every interpolated value goes through `ps_str` (doubled quotes) and is also validated beforehand (package names, paths). |
| **Option injection in winget** (an ID starting with `-`) | IDs must match `^[A-Za-z0-9][A-Za-z0-9._+-]*$`; the whole catalog is tested against that filter. Installs use `--exact --source winget` (official source). |
| **Installing winget from the internet** | Only after an explicit confirmation. Fixed URLs (`aka.ms` and `github.com/microsoft/...`), nothing from the user or from the network is mixed into the script, a private temporary folder; **before installing**, the three files must carry a valid Microsoft signature; Windows verifies it again on install and the publisher (`CN=Microsoft Corporation`) is checked afterwards. A test forbids any other host. |
| **Predictable temporary file** (`winget export`) | Private temporary folder with a random name, deleted afterwards. |
| **Tampered settings file** | Every value is compared with a closed list (languages and themes); anything unknown is ignored. |
| **Altered download** (`descargar_y_ejecutar.ps1`) | Validates `Repo`/`Tag`, only accepts `github.com` URLs, verifies the SHA256 **on the same write-locked file handle** (no gap between verifying and running). |
| **Critical apps** | Explicit list of apps to remove + a list of protected apps that are never touched (Store, Calculator, Photos, Terminal, Edge, Windows Security…). |
| **Tampered release pipeline** | GitHub Actions pinned by commit; build dependencies pinned by version and SHA256; the job that builds has no write permission and the one that publishes runs nothing from the project; CodeQL and OpenSSF Scorecard; Dependabot proposes updates. |
| **Dangerous code** | No `eval`, `exec`, `pickle`, `os.system` or `shell=True` (tests). Static analysis with **bandit** on every push: no medium or high severity findings. |

All of this is covered by automated tests (`tests/test_seguridad.py`) that run on every push on Windows and Linux. The full list of what was reviewed, patched and tested is in [AUDITORIA_SEGURIDAD.md](AUDITORIA_SEGURIDAD.md).

## What it never touches

Windows Defender and the Firewall (never disabled), Windows Update (never disabled), network and audio services, personal files and "registry cleaners". See [NIVELES.md](NIVELES.md).

## Known limits (stated honestly)

- The `.exe` is **not signed with a code-signing certificate** (it costs money and requires a verified identity). That is why **SmartScreen may show a warning** and some antivirus products may give the typical PyInstaller false positives. That is why the hash, the attestation and the option to build it yourself exist.
- A local administrator already has full control of the machine: the defenses above protect against **unprivileged users and tampered data**, not against someone who is already an administrator.
- Uninstalled apps and deleted files are **not restored** by the tool (apps are reinstalled from the Microsoft Store; there is also a Windows restore point, which does not recover personal files).
- At the Extreme level, disabling services has functional consequences (printing, Bluetooth, Xbox, search). They are explained on screen and must be confirmed.
- TeamViewer and AnyDesk licenses are **not free for commercial use**.
- The Russian, Japanese and Chinese translations were made with AI help and cover the interface; reviews by native speakers are welcome.

## Reporting a vulnerability

Open a private advisory (Security → Report a vulnerability) on the repository. Please avoid publishing exploitation details before a fix is available.
