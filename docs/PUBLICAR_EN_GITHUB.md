# Publicar BottiMint en GitHub — guía completa

Usuario: **shadoowww** · Repositorio: **bottimint-pc** · URL final: `https://github.com/shadoowww/bottimint-pc`

Los archivos `ci.yml` y `release.yml` de `github_workflows_para_copiar/` **son los workflows** de GitHub Actions. Hay que copiarlos a `.github/workflows/` (paso 4) para que funcionen.

## Antes de empezar (una sola vez)
1. Cuenta en github.com con **2FA** activado (Settings → Password and authentication).
2. Instalar **Git for Windows**: https://git-scm.com/download/win (todo por defecto).
3. Abrir una terminal (PowerShell) y configurar tu identidad:
   ```
   git config --global user.name "shadoowww"
   git config --global user.email "TU_CORREO_DE_GITHUB"
   ```
   Si no querés exponer tu correo, usá el correo `noreply` que figura en GitHub → Settings → Emails.
4. Ir a la carpeta del proyecto:
   ```
   cd "C:\Users\Nuevo Usuario\Downloads\Optimizer_Win11-10"
   ```

## Paso 1 — Limpiar la carpeta
- Borrá la carpeta **`optimizador\`** (restos de la versión vieja, son archivos de 88 bytes sin uso) y todas las carpetas `__pycache__`.
- No hace falta borrar nada más: el `.gitignore` ya excluye `.pyc`, `build/`, `dist/` y los informes.

## Paso 2 — Crear el repositorio vacío
1. github.com → **+** (arriba a la derecha) → **New repository**.
2. Repository name: `bottimint-pc`. Descripción: *Optimizador y instalador de programas para Windows 10/11 (reversible, con punto de restauración).*
3. **Public**.
4. **NO** marques «Add a README», «.gitignore» ni «license» (ya los tenés; si los marcás, el primer push da conflicto).
5. **Create repository**.

## Paso 3 — Revisar antes de subir
- `README.md`, `docs/` y `scripts/` ya apuntan a `shadoowww/bottimint-pc`.
- `LICENSE` figura a nombre de `shadoowww` (MIT). Cambialo si querés tu nombre real.
- Probá localmente: `python -m unittest discover -s tests -t .` (tiene que terminar en OK).

## Paso 4 — Copiar los workflows
```
mkdir .github\workflows
copy github_workflows_para_copiar\ci.yml .github\workflows\
copy github_workflows_para_copiar\release.yml .github\workflows\
```
Podés borrar después la carpeta `github_workflows_para_copiar`.

## Paso 5 — Subir el código
```
git init
git add .
git status
git commit -m "BottiMint 1.1.0"
git branch -M main
git remote add origin https://github.com/shadoowww/bottimint-pc.git
git push -u origin main
```
- `git status` (antes del commit) te deja ver qué se sube: no debería aparecer `__pycache__` ni `optimizador/`.
- Al hacer `push`, Windows te abre una ventana para iniciar sesión en GitHub (Git Credential Manager). Aceptá. **Nunca pegues tu contraseña en un archivo**; si te pide credenciales por consola, el «password» es un *token* (Settings → Developer settings → Personal access tokens), no tu contraseña.

## Paso 6 — Comprobar el CI
Repositorio → pestaña **Actions** → ejecución «CI». Tiene que quedar en verde (pruebas en Linux con xvfb, Windows, y `bandit`). Si algo falla, abrí el job rojo y mirá el log; el error suele ser claro.

## Paso 7 — Publicar la primera versión (Release)
```
git tag v1.1.0
git push origin v1.1.0
```
Se dispara `release.yml`: compila `BottiMint.exe` con PyInstaller en Windows, genera `BottiMint.exe.sha256`, crea la **atestación de procedencia** y publica todo en **Releases**. Tarda unos minutos. Revisá en Actions y luego en la pestaña **Releases**.

Si falló y querés repetir: arreglá, y movés la etiqueta:
```
git tag -d v1.1.0
git push origin :refs/tags/v1.1.0
git tag v1.1.0
git push origin v1.1.0
```

## Paso 8 — Proteger el repositorio (Settings)
1. **Code security** → activar *Dependabot alerts*, *Dependabot security updates*, *Secret scanning* y *Push protection*.
2. **Branches → Add branch ruleset** para `main`: exigir *Pull request* o al menos *Require status checks* (CI) y bloquear *force push*.
3. **Actions → General → Workflow permissions**: *Read repository contents* (el release declara los permisos extra que necesita).
4. **Security → Private vulnerability reporting**: activarlo, así te reportan fallos sin hacerlos públicos.
5. En *About* (engranaje en la portada): agregá descripción y *topics* (`windows`, `optimizer`, `winget`, `python`, `tkinter`).

## Paso 9 — Que cualquiera pueda verificarlo
Pegá esto en las notas del release:
```
1) Hash:           certutil -hashfile BottiMint.exe SHA256   (comparar con BottiMint.exe.sha256)
2) VirusTotal:     subir BottiMint.exe a https://www.virustotal.com
3) Procedencia:    gh attestation verify BottiMint.exe --repo shadoowww/bottimint-pc
```
Instalación rápida desde otra PC (sin pendrive):
```
irm https://raw.githubusercontent.com/shadoowww/bottimint-pc/main/scripts/descargar_y_ejecutar.ps1 -OutFile $env:TEMP\od.ps1
powershell -ExecutionPolicy Bypass -File $env:TEMP\od.ps1 -Repo shadoowww/bottimint-pc
```
Agregá `-Tag v1.1.0` para fijar una versión; el script verifica el hash antes de ejecutar.

## Paso 10 — Versiones futuras
1. Cambiá el número en `bottimint/__init__.py` y agregá la entrada en `CHANGELOG.md`.
2. `git add .` → `git commit -m "Versión 1.2.0"` → `git push`.
3. `git tag v1.2.0` → `git push origin v1.2.0`.

## Problemas comunes
| Síntoma | Causa / solución |
|---|---|
| `rejected ... fetch first` al hacer push | Marcaste README/licencia al crear el repo. Borrá el repo y creálo vacío, o `git pull origin main --allow-unrelated-histories` |
| `Authentication failed` | Usá el login del navegador o un token, no la contraseña |
| El job «bandit» falla | Mirar el log; el proyecto solo debería tener hallazgos bajos |
| SmartScreen avisa al abrir el .exe | Es normal: no está firmado. Por eso se publican hash, VirusTotal y atestación |
| No aparece el Release | La etiqueta debe empezar con `v` y haberse subido (`git push origin v1.1.0`) |
