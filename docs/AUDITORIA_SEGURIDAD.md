# BottiMint security audit

This document details **what was reviewed, what was found, what was patched and which test verifies it**. It complements [`SEGURIDAD.md`](SEGURIDAD.md) (the summary for users).

> Honesty first: the security tests were written **after** the patches were applied, so they stay as a permanent regression safety net. No exploits were run against the previous version; the risks in the table are the ones that came out of reviewing the code with an attacker's mindset. Reproducible with `python -m unittest discover -s tests -t .`.

## 1. The two tests that failed (and why they were not injections)

Two tests failed during the hardening round. Neither was a real vulnerability:

| Test | What happened | Real cause | Fix |
|---|---|---|---|
| "`shell=True` is not used" | The test searches the code for that string and found it | A **comment** of mine in `limpieza.py` literally contained the text `shell=True` | I reworded the comment ("argument list, never a shell string"). The code never used a shell |
| Light theme contrast | Accent `#12a06e` on white = 3.34:1 (WCAG minimum 4.5:1) | An **accessibility** problem, not a security one | Light accent `#0a7d54` (5.15:1) |

The injection tests (`PruebasInyeccion`, `PruebasManifiesto`) passed on the first run because they were written against the already patched code.

## 2. Risks reviewed, patch and test

| # | Risk | Patch | Test |
|---|---|---|---|
| 1 | **Junctions / symlinks**: cleanup could follow a link and delete outside the temp folder | Own `_recorrer` walker; detects `FILE_ATTRIBUTE_REPARSE_POINT (0x400)` and does not enter. The link is removed, never its target | `PruebasEnlaces`, `PruebasJunctionReal` (Windows only, real `mklink /J`) |
| 2 | **Manipulated environment variables** (`TEMP=C:\Windows`) | `_es_ruta_peligrosa` resolves with `realpath` and compares against `_carpetas_protegidas` (Windows, System32, Program Files, Users root…) | `PruebasRutasProtegidas` |
| 3 | **Executable hijacking** (a fake `reg.exe` in the current directory or PATH) | `resolver_exe`: absolute paths in `System32`; no `shell=True`; arguments as a list | `PruebasEjecutables` |
| 4 | **Data folder** with a link or open permissions (another user could alter the backups) | `preparar_dir_datos`: rejects links/junctions; with admin rights applies `icacls` (owner Administrators, inheritance off, only SYSTEM and Administrators) | `PruebasEnlaces` |
| 5 | **Tampered restore manifest** (it is restored as admin: that would be privilege escalation) | Allowlist: registry keys, services, tasks, GUIDs and Appx packages validated against the catalog and regexes; `_loc_appx_valida` limits to `WindowsApps`; session ID `^\d{8}_\d{6}$`; read with `_leer_manifest`; atomic save | `PruebasManifiesto` |
| 6 | **PowerShell injection** | `ps_str` escapes quotes; nothing from the user is concatenated without going through it | `PruebasInyeccion` |
| 7 | **Injection through winget IDs** (`Foo --source evil`, `;`, `&`) | `id_valido` (strict regex) before calling winget | `PruebasInyeccion` |
| 8 | **Predictable temporary files** (`winget export`) | Private `mkdtemp` | `PruebasInyeccion` |
| 9 | **Tampered settings** (`ajustes.json` with arbitrary language/theme) | Validation against closed lists; on doubt, defaults | `PruebasAjustes` |
| 10 | **Download script** (`descargar_y_ejecutar.ps1`) | Validates `-Repo`/`-Tag`, only accepts `github.com` URLs, SHA256 computed on a locked handle (prevents swapping the file between verifying and running) | Manual review + bandit |
| 11 | **Supply chain** | Releases with SHA256 and provenance attestation (`actions/attest-build-provenance`); `bandit` job in CI | CI |
| 12 | **Translated texts** breaking placeholders or opening an injection path in messages | `test_idiomas` checks that every translation keeps its placeholders | `test_idiomas.py` |

## 3. Static analysis

`bandit` over `bottimint/`: **only low-severity findings** (use of `subprocess` with argument lists and absolute paths, expected in a system tool). No medium or high findings.

## 4. Tests

- 66 tests in total (1 skipped on Linux: the real-junction one, which only runs on Windows).
- GUI tests run under `xvfb`; the rest run without a display.
- They cover: links, dangerous paths, executables, injection, manifest, settings, languages, contrast and the exit confirmation.

## 5. Known limits (what is NOT claimed)

- **The .exe is not signed** (code signing costs money): Windows SmartScreen may warn. That is why the hash and the attestation are published and everyone is invited to check VirusTotal.
- A **malicious local administrator** is outside the threat model: they can already do everything BottiMint does.
- No audit guarantees "zero vulnerabilities". If you find one, see `SEGURIDAD.md` for how to report it.
- Testing in a VM remains the recommendation before using the Extreme level (`PRUEBAS_VM.md`).

## 6. How to verify it yourself

```
python -m unittest discover -s tests -t .
python -m bandit -r bottimint
certutil -hashfile BottiMint.exe SHA256        # compare with BottiMint.exe.sha256
gh attestation verify BottiMint.exe --repo shadoowww/bottimint-optimizer
```
