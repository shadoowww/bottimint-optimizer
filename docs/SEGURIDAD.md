# Seguridad

BottiMint modifica el sistema con permisos de administrador, así que la desconfianza es razonable. Este documento dice qué
hace el programa, qué defensas tiene el código y **cómo podés comprobarlo vos mismo** sin creerle a nadie.

## Qué datos maneja

- **No envía telemetría ni datos a ningún servidor.** La única actividad de red es la de `winget` al instalar o actualizar programas (y, si lo usás, el script opcional `descargar_y_ejecutar.ps1`, que habla con GitHub).
- No hay cuentas, ni anuncios, ni «versión premium».
- Lo que guarda queda **local**:
  - `C:\ProgramData\BottiMint\` → sesiones (manifiestos para deshacer) e informes. Con permisos de administrador, la carpeta se restringe a **SYSTEM y Administradores**.
  - `%APPDATA%\BottiMint\ajustes.json` → solo tu idioma y tu tema. Nada personal.
  - Un informe de texto en el Escritorio.

## Cómo verificar que el programa es seguro (hacelo, no confíes)

1. **Hash SHA256.** Cada release publica `BottiMint.exe` y `BottiMint.exe.sha256`. En PowerShell:
   `Get-FileHash .\BottiMint.exe -Algorithm SHA256` y compará con el archivo `.sha256`. Si difiere en un solo carácter, no lo ejecutes.
2. **VirusTotal.** Subí el `.exe` a <https://www.virustotal.com> (o buscá por su hash, sin subir nada). Los `.exe` hechos con PyInstaller a veces tienen 1–3 falsos positivos de motores heurísticos; si ves muchos, no lo uses y avisá.
3. **Procedencia (atestación de GitHub).** Los releases se compilan en GitHub Actions y quedan firmados con una *build provenance attestation*: prueba criptográfica de que ese `.exe` salió de este repositorio y de ese commit, no de la PC de nadie.
   `gh attestation verify BottiMint.exe -R shadoowww/bottimint-optimizer`
4. **Compilalo vos.** No hace falta confiar en el `.exe`: el programa es Python puro sin dependencias externas. `python -m bottimint` lo corre desde el código, y `scripts\BottiMint.bat` / `Compilar_exe.bat` generan el `.exe` en tu equipo. El código entero se puede leer en una tarde.
5. **Probalo primero en una VM** con snapshot ([PRUEBAS_VM.md](PRUEBAS_VM.md)). Antes de tocar nada, el programa crea un punto de restauración de Windows y verifica que exista; si no puede, aborta sin cambiar nada.

## Permisos

- Necesita **administrador** para cambiar servicios, registro del sistema, tareas programadas y crear el punto de restauración. Sin administrador, esas tareas se **omiten** (no se fuerzan).
- Los ajustes del usuario (publicidad, efectos visuales, Game DVR) se aplican al **usuario que ejecuta el programa**. Si se eleva con otra cuenta de administrador, esos ajustes van a esa cuenta.

## Defensas del código (revisión de seguridad)

| Riesgo | Defensa |
|---|---|
| **Borrado fuera de lo previsto** mediante *junctions* o enlaces simbólicos (en Windows `os.walk` entra a las junctions) | Recorrido propio que **nunca entra a enlaces ni puntos de reanálisis**; si encuentra uno, elimina el enlace y no toca su destino. Una carpeta raíz que sea enlace se ignora. |
| **Variables de entorno manipuladas** (`TEMP` apuntando a `System32` o a Documentos) | Lista de carpetas protegidas (System32, WinSxS, Program Files, Documentos, Escritorio, Imágenes, Descargas, OneDrive…) y de raíces; las rutas se resuelven con `realpath` antes de comparar. |
| **Secuestro de ejecutables** (un `powershell.exe` o `sc.exe` plantado en la carpeta actual o en el PATH, ejecutado como administrador) | Los comandos del sistema se lanzan por **ruta absoluta** desde `System32`. Nunca `shell=True`, siempre listas de argumentos (hay un test que lo impide). |
| **Carpeta de datos pre-creada por otro usuario** (junction en `ProgramData`) | Se rechaza si es un enlace; con administrador se fija el propietario y se restringen los permisos (`icacls`). |
| **Manifiesto de restauración manipulado** (alguien edita el JSON para que, al restaurar con privilegios, se toque el registro/servicios que quiera) | Al restaurar, **cada entrada se valida contra el catálogo**: el registro solo puede tocar las claves del cambio original, los servicios y tareas deben ser los del cambio, los GUID y nombres se validan con expresiones estrictas, las apps solo se registran desde `WindowsApps`. Lo que no coincide se ignora. El ID de sesión se valida (sin `..`). El manifiesto se escribe de forma **atómica**. |
| **Inyección en PowerShell** | Todo valor interpolado pasa por `ps_str` (comillas duplicadas) y además se valida antes (nombres de paquete, rutas). |
| **Inyección de opciones en winget** (un ID que empiece con `-`) | Los IDs deben cumplir `^[A-Za-z0-9][A-Za-z0-9._+-]*$`; todo el catálogo se prueba con ese filtro. Instalación con `--exact --source winget` (fuente oficial). |
| **Archivo temporal predecible** (`winget export`) | Carpeta temporal privada con nombre aleatorio, borrada al terminar. |
| **Archivo de ajustes manipulado** | Cada valor se compara con una lista cerrada (idiomas y temas); lo desconocido se ignora. |
| **Descarga alterada** (`descargar_y_ejecutar.ps1`) | Valida `Repo`/`Tag`, solo acepta URLs de `github.com`, verifica el SHA256 **sobre el mismo manejador de archivo bloqueado contra escritura** (sin ventana entre verificar y ejecutar). |
| **Apps críticas** | Lista explícita de apps a quitar + lista de apps protegidas que nunca se tocan (Store, Calculadora, Fotos, Terminal, Edge, Seguridad de Windows…). |
| **Código peligroso** | Sin `eval`, `exec`, `pickle`, `os.system` ni `shell=True` (tests). Análisis estático con **bandit** en cada push: sin hallazgos de severidad media o alta. |

Todo esto está cubierto por pruebas automáticas (`tests/test_seguridad.py`), que corren en cada push en Windows y Linux.

## Qué NO toca nunca

Windows Defender y el Firewall (no se desactivan), Windows Update (no se desactiva), servicios de red y audio, archivos personales y «limpiadores de registro». Ver [NIVELES.md](NIVELES.md).

## Límites conocidos (decirlo con honestidad)

- El `.exe` **no está firmado con un certificado de firma de código** (cuesta dinero y requiere identidad verificada). Por eso **SmartScreen puede mostrar una advertencia** y algunos antivirus pueden dar falsos positivos típicos de PyInstaller. Por eso existen el hash, la atestación y la opción de compilarlo vos.
- Un administrador local ya tiene control total del equipo: las defensas anteriores protegen contra **usuarios sin privilegios y contra datos manipulados**, no contra alguien que ya es administrador.
- Las apps desinstaladas y los archivos borrados **no se restauran** con la herramienta (las apps se reinstalan desde Microsoft Store; hay además un punto de restauración de Windows, que no recupera archivos personales).
- En el nivel Extremo, desactivar servicios tiene consecuencias funcionales (impresión, Bluetooth, Xbox, búsqueda). Se explican en pantalla y hay que confirmarlas.
- Las licencias de TeamViewer y AnyDesk **no son gratuitas para uso comercial**.
- Las traducciones al ruso, japonés y chino están hechas con ayuda de IA y cubren la interfaz; revisiones de hablantes nativos son bienvenidas.

## Reportar una vulnerabilidad

Abrí un aviso privado (Security → Report a vulnerability) en el repositorio. Evitá publicar detalles de explotación antes de que haya un arreglo.


Detalle completo de lo revisado, parcheado y probado: [AUDITORIA_SEGURIDAD.md](AUDITORIA_SEGURIDAD.md).
