# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico.

## [1.1.0] - 2026-11-24

### Cambiado
- La app ahora se llama **BottiMint** (paquete `bottimint`, `BottiMint.exe`, `C:\ProgramData\BottiMint`).
- Uso universal: se quitaron los datos de «técnico/negocio» y las menciones a «cliente»; el perfil `tecnico` pasó a `herramientas`.

### Agregado
- **Tema claro y oscuro** (botones ☀ / ☾ en la cabecera), con acento mint, respeto del modo de Windows por defecto y barra de título oscura.
- **Idiomas:** español, inglés (completo), ruso, japonés y chino (interfaz; descripciones largas en inglés). Selector en la cabecera.
- Preferencias (idioma/tema) guardadas por usuario en `%APPDATA%\BottiMint\ajustes.json`, validadas contra listas cerradas.
- Atestación de procedencia (GitHub build provenance) en los releases y análisis estático `bandit` en CI.

- **Botón «Salir»** (⏻) con confirmación; avisa de forma especial si hay una tarea en curso. También confirma al cerrar con la X.
- **Interfaz redondeada**: botones, selectores de nivel, tarjetas y diálogos con esquinas redondeadas (`bottimint/widgets.py`). Diálogos propios con tema claro/oscuro.
- **Optimización:** el botón «Aplicar cambios marcados (N)» ahora está sobre la lista de casillas (siempre visible), con contador de cambios marcados; se desactiva si no hay nada marcado. Elegir un nivel solo muestra la vista previa (lectura), nunca aplica.
- Documento `docs/AUDITORIA_SEGURIDAD.md` y guía de publicación actualizada.

### Seguridad
- Limpieza: recorrido propio que no entra a junctions/enlaces; protección de carpetas críticas aunque una variable de entorno apunte ahí.
- Comandos del sistema por ruta absoluta de System32; carpeta de datos con comprobación de enlaces y permisos restringidos.
- Restauración: cada entrada del manifiesto se valida contra el catálogo; ID de sesión validado; escritura atómica.
- Validación de IDs de winget, escape de valores en PowerShell, carpeta temporal privada.
- `descargar_y_ejecutar.ps1`: valida parámetros y URLs, soporta `-Tag`, verifica el hash sobre el archivo bloqueado contra escritura.
- Nuevas pruebas: `tests/test_seguridad.py`, `tests/test_idiomas.py` (55 en total).

## [1.0.0] - 2026-11-24

### Agregado
- **Optimización por niveles** (Básico, Profundo, Extremo/Gaming), acumulativos, con explicación y consecuencias de cada cambio.
- **Punto de restauración obligatorio y verificado** antes de aplicar; si no se puede crear, no se modifica nada.
- **Restauración** por sesión: manifiesto con el estado previo de registro, servicios, tareas programadas, inicio y plan de energía.
- Opciones que dependen del equipo (SSD/HDD, batería, impresoras) para preseleccionar solo lo conveniente.
- **Módulo de programas** (winget): catálogo curado con categoría Gaming, perfiles oficina/gamer/técnico, detección de instalados, verificación de IDs y actualización masiva.
- **Interfaz gráfica** unificada (tkinter) con confirmación obligatoria de consecuencias.
- Informes para el cliente (Escritorio y `C:\ProgramData\BottiMint`).
- CI (tests en Windows y Linux) y release automático del `.exe` con SHA256.
- Script `descargar_y_ejecutar.ps1` con verificación de integridad.
