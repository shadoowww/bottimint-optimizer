# Security Policy

*Resumen en español al final.*

BottiMint runs with administrator rights and changes the system, so security reports are very welcome.

## Supported versions

Only the **latest release** receives security fixes. Please check that the problem still happens there before reporting it.

| Version | Supported |
|---|---|
| Latest release | Yes |
| Older releases | No: update to the latest one |

## Reporting a vulnerability

**Please do not open a public issue** for a security problem.

Report it privately: go to the **Security** tab of this repository and choose **[Report a vulnerability](https://github.com/shadoowww/bottimint-optimizer/security/advisories/new)**.

It helps a lot to include:

- the BottiMint version (shown in the window title) and your Windows version;
- whether you used the released `.exe` or ran it from source;
- the steps to reproduce it, and what an attacker would need beforehand (a standard user account, a file in a certain folder, an altered session manifest...);
- the impact you see (for example, running code as administrator or deleting files outside the intended folders);
- a harmless proof of concept, if you have one.

Before attaching logs, reports or screenshots, **remove personal data** (computer name, user name, paths with your user name, e-mail addresses). Never include passwords, keys or tokens. Please test only on your own machine or a virtual machine.

## What to expect

This is a personal project maintained in spare time, so there are no guaranteed response times. Reports are handled on a best-effort basis:

1. the report is reviewed and reproduced;
2. if it is confirmed, it is fixed in a new release, with an entry in the [changelog](CHANGELOG.md);
3. you are credited if you would like to be.

Please give reasonable time for a fix to be released before publishing details. There is no bug bounty program.

## Scope

**In scope:** the code in this repository, the released `.exe` files, the helper scripts and the build and release workflows. For example: privilege escalation, command or PowerShell injection, deleting files outside the intended folders, abuse of an altered session manifest, or tampering with the release pipeline.

**Out of scope:**

- anything that requires already being an administrator on the machine (an administrator can already do everything BottiMint does);
- the documented effects of the optimization levels (see [docs/NIVELES.md](docs/NIVELES.md));
- the `.exe` not being code-signed, SmartScreen warnings and antivirus false positives (known limits, see [docs/SEGURIDAD.md](docs/SEGURIDAD.md));
- vulnerabilities in Windows, `winget` or the programs it installs: please report those to their vendors.

## Checking what you run

How to verify a release (SHA256, build provenance attestation, building it yourself) and the defenses in the code are described in [docs/SEGURIDAD.md](docs/SEGURIDAD.md). The review history is in [docs/AUDITORIA_SEGURIDAD.md](docs/AUDITORIA_SEGURIDAD.md).

---

## Resumen en español

- Solo la **última versión publicada** recibe correcciones de seguridad.
- **No abras un issue público.** Reportá en privado desde la pestaña **Security → Report a vulnerability**.
- Incluí la versión de BottiMint y de Windows, los pasos para reproducirlo y el impacto. **Quitá tus datos personales** de capturas e informes y nunca envíes contraseñas ni claves.
- Es un proyecto personal: se responde cuando se puede, sin plazos garantizados ni recompensas.
