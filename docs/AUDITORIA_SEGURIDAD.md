# Auditoría de seguridad de BottiMint

Este documento detalla **qué se revisó, qué se encontró, qué se parcheó y con qué prueba se verifica**. Complementa a [`SEGURIDAD.md`](SEGURIDAD.md) (resumen para usuarios).

> Honestidad primero: las pruebas de seguridad se escribieron **después** de aplicar los parches, de modo que quedan como red de seguridad permanente (regresión). No se ejecutaron exploits contra la versión anterior; los riesgos de la tabla son los que surgieron de revisar el código con mentalidad de atacante. Reproducible con `python -m unittest discover -s tests -t .`.

## 1. Los dos tests que fallaron (y por qué no eran inyecciones)

Durante la ronda de endurecimiento fallaron dos pruebas. Ninguna era una vulnerabilidad real:

| Test | Qué pasó | Causa real | Arreglo |
|---|---|---|---|
| «no se usa `shell=True`» | El test busca esa cadena en el código y la encontró | Un **comentario** mío en `limpieza.py` contenía literalmente el texto `shell=True` | Reescribí el comentario («lista de argumentos, nunca una cadena de shell»). El código nunca usó shell |
| Contraste del tema claro | Acento `#12a06e` sobre blanco = 3,34:1 (mínimo WCAG 4,5:1) | Problema de **accesibilidad**, no de seguridad | Acento claro `#0a7d54` (5,15:1) |

Las pruebas de inyección (`PruebasInyeccion`, `PruebasManifiesto`) pasaron a la primera porque se escribieron sobre el código ya parcheado.

## 2. Riesgos revisados, parche y prueba

| # | Riesgo | Parche | Prueba |
|---|---|---|---|
| 1 | **Junctions / symlinks**: la limpieza podía seguir un enlace y borrar fuera de la carpeta temporal | `_recorrer` propio; detecta `FILE_ATTRIBUTE_REPARSE_POINT (0x400)` y no entra. Se borra el enlace, nunca su destino | `PruebasEnlaces`, `PruebasJunctionReal` (solo Windows, `mklink /J` real) |
| 2 | **Variables de entorno manipuladas** (`TEMP=C:\Windows`) | `_es_ruta_peligrosa` resuelve con `realpath` y compara con `_carpetas_protegidas` (Windows, System32, Program Files, Users raíz…) | `PruebasRutasProtegidas` |
| 3 | **Secuestro de ejecutables** (un `reg.exe` falso en el directorio actual o en el PATH) | `resolver_exe`: rutas absolutas en `System32`; sin `shell=True`; argumentos como lista | `PruebasEjecutables` |
| 4 | **Carpeta de datos** con enlace o permisos abiertos (otro usuario podría alterar los respaldos) | `preparar_dir_datos`: rechaza enlaces/junctions; con admin aplica `icacls` (dueño Administradores, herencia off, solo SYSTEM y Administradores) | `PruebasEnlaces` |
| 5 | **Manifiesto de restauración alterado** (se restaura como admin: sería escalada) | Lista blanca: claves de registro, servicios, tareas, GUID y paquetes Appx validados contra el catálogo y regex; `_loc_appx_valida` limita a `WindowsApps`; ID de sesión `^\d{8}_\d{6}$`; lectura con `_leer_manifest`; guardado atómico | `PruebasManifiesto` |
| 6 | **Inyección en PowerShell** | `ps_str` escapa comillas; nada del usuario se concatena sin pasar por ahí | `PruebasInyeccion` |
| 7 | **Inyección por ID de winget** (`Foo --source evil`, `;`, `&`) | `id_valido` (regex estricta) antes de invocar winget | `PruebasInyeccion` |
| 8 | **Archivos temporales predecibles** (`winget export`) | `mkdtemp` privado | `PruebasInyeccion` |
| 9 | **Ajustes manipulados** (`ajustes.json` con idioma/tema arbitrarios) | Validación contra listas cerradas; ante dudas, valores por defecto | `PruebasAjustes` |
| 10 | **Script de descarga** (`descargar_y_ejecutar.ps1`) | Valida `-Repo`/`-Tag`, acepta solo URLs `github.com`, hash SHA256 calculado sobre un handle bloqueado (evita cambiar el archivo entre verificar y ejecutar) | Revisión manual + bandit |
| 11 | **Cadena de suministro** | Releases con SHA256 y atestación de procedencia (`actions/attest-build-provenance`); job `bandit` en CI | CI |
| 12 | **Textos traducidos** que rompan marcadores o abran una vía de inyección en mensajes | `test_idiomas` verifica que cada traducción conserve los placeholders | `test_idiomas.py` |

## 3. Análisis estático

`bandit` sobre `bottimint/`: **solo hallazgos de severidad baja** (uso de `subprocess` con lista de argumentos y rutas absolutas, esperado en una herramienta de sistema). Sin hallazgos medios ni altos.

## 4. Pruebas

- 65 pruebas en total (1 omitida en Linux: la de junction real, que solo corre en Windows).
- Las pruebas de GUI corren bajo `xvfb`; las demás, sin pantalla.
- Cubren: enlaces, rutas peligrosas, ejecutables, inyección, manifiesto, ajustes, idiomas, contraste y la confirmación de salida.

## 5. Límites conocidos (lo que NO se afirma)

- **El .exe no está firmado** (la firma de código cuesta dinero): Windows SmartScreen puede advertir. Por eso se publican hash, atestación y se invita a verificar en VirusTotal.
- Un **administrador local malicioso** queda fuera del modelo de amenazas: ya puede hacer todo lo que BottiMint hace.
- Ninguna auditoría garantiza «cero vulnerabilidades». Si encontrás una, ver `SEGURIDAD.md` para reportarla.
- Probar en una VM sigue siendo la recomendación antes de usar el nivel Extremo (`PRUEBAS_VM.md`).

## 6. Cómo verificar vos mismo

```
python -m unittest discover -s tests -t .
python -m bandit -r bottimint
certutil -hashfile BottiMint.exe SHA256        # comparar con BottiMint.exe.sha256
gh attestation verify BottiMint.exe --repo shadoowww/bottimint-pc
```
