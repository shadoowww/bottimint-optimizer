# Guía de pruebas en máquina virtual

**Importante:** probá siempre en una VM antes de usar la herramienta en un equipo que te importe.

## Preparación

1. Creá una VM con **Windows 11** (y, si podés, otra con **Windows 10**), mínimo 4 GB de RAM y 60 GB de disco.
2. Completá la instalación de Windows, actualizá y abrí la **Microsoft Store** una vez (registra winget).
3. Activá la **Protección del sistema** en la unidad C: (Panel de control → Sistema → Protección del sistema).
4. Instalá Python 3.10+ (o usá el `.exe`).
5. **Sacá un snapshot** de la VM («estado limpio»).

## Lista de pruebas

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | Abrir la interfaz como administrador | Pestaña *Inicio* con datos del equipo, «Permisos: Administrador», winget «Disponible». |
| 2 | Abrir **sin** administrador | Aviso rojo arriba; aplicar cambios del sistema se rechaza. |
| 3 | Optimización → **Básico**, vista previa | 9 cambios; papelera en riesgo medio. |
| 4 | Aplicar **Básico** | Se crea el punto de restauración; se liberan MB/GB; aparece el informe en el Escritorio. |
| 5 | **Restaurar una sesión** (Básico) | Termina sin errores. |
| 6 | Aplicar **Profundo** | Apps de fábrica desinstaladas, publicidad apagada, tareas de telemetría deshabilitadas. La Store, Calculadora y Fotos siguen. |
| 7 | **Restaurar** el Profundo | Vuelven ajustes, tareas e inicio. Las apps: reinstalar desde la Store (esperado). |
| 8 | Aplicar **Extremo** | Servicios ajustados; Modo Juego activo; efectos visuales mínimos (cerrar sesión para verlos). |
| 9 | Comprobar la PC tras el Extremo | Internet, audio, Windows Update y Defender funcionan. |
| 10 | **Restaurar** el Extremo y reiniciar | Servicios y ajustes como al inicio (comparar con el snapshot). |
| 11 | Forzar un fallo del punto de restauración (desactivar la Protección del sistema) | Aborta con mensaje y **no cambia nada**. |
| 12 | Programas → **Verificar IDs del catálogo** | «Todos los IDs existen». Si alguno falla, corregirlo en `instalador.py`. |
| 13 | Programas → perfil **oficina** | Se instalan en silencio; informe en `C:\ProgramData\BottiMint\instalaciones`. |
| 14 | Programas → perfil **gamer** | Launchers y runtimes instalados; Steam puede pedir reinicio. |
| 15 | Volver al snapshot y repetir con **Windows 10** | Mismos resultados (winget puede requerir «Instalador de aplicaciones»). |

## Qué anotar

- Capturas de pantalla reales (reemplazan las de `docs/img/`).
- Cualquier ID de winget que no exista o cambie.
- Cualquier cambio que no se haya revertido bien: abrir un *issue* con el `manifest.json` de la sesión.
