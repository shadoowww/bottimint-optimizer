# Niveles de optimización

> Generado automáticamente desde `bottimint/nucleo.py` con `python scripts/generar_docs.py`. No editar a mano.

Los niveles son **acumulativos**: Profundo incluye todo Básico, y Extremo incluye todo Profundo.
Antes de aplicar cualquiera se crea un **punto de restauración de Windows** y se verifica; si no se puede crear, **no se modifica nada**.

## Básico - Limpieza general

**Ideal para:** Cualquier PC lenta, con poco espacio o que hace tiempo no se limpia.

**Qué hace**

- Borra archivos temporales de Windows y del usuario.
- Vacía cachés de navegadores, miniaturas, informes de error y descargas de Windows Update ya instaladas.
- Vacía la papelera y la caché DNS.

**Consecuencias a tener en cuenta**

- La primera vez que se abren las webs cargan un poco más lento (se rearma la caché).
- Lo que está en la papelera se pierde para siempre.
- No se desactiva ningún servicio ni programa: la PC funciona igual que antes, con más espacio.

**Reversibilidad:** No hay nada que restaurar: son archivos descartables que Windows vuelve a crear solo.

### Cambios que incorpora este nivel (9)

| Cambio | Grupo | Riesgo | Reversible | Marcado por defecto | Qué hace | Consecuencia |
|---|---|---|---|---|---|---|
| **Temporales del usuario**<br>`limp_temp_usuario` | Limpieza | 🟢 bajo | no | sí | Archivos temporales del usuario actual (carpeta TEMP). | Un programa abierto puede perder un borrador temporal no guardado. Cerrar todo antes. |
| **Temporales de Windows**<br>`limp_temp_windows` | Limpieza | 🟢 bajo | no | sí | Archivos temporales de C:\Windows\Temp. | Ninguna. |
| **Caché de navegadores**<br>`limp_navegadores` | Limpieza | 🟢 bajo | no | sí | Caché de Chrome, Edge, Brave y Firefox. No toca contraseñas ni historial. | Las webs cargan un poco más lento la primera vez. Cerrar los navegadores antes. |
| **Caché de Internet / miniaturas**<br>`limp_inetcache` | Limpieza | 🟢 bajo | no | sí | Caché de Internet y miniaturas del Explorador. | Las miniaturas se regeneran al abrir carpetas con imágenes. |
| **Informes y volcados de error**<br>`limp_errores` | Limpieza | 🟢 bajo | no | sí | Informes y volcados de error de Windows. | Se pierden registros de cuelgues pasados (solo sirven para diagnosticar). |
| **Caché de Windows Update**<br>`limp_windows_update` | Limpieza | 🟢 bajo | no | sí | Descargas de Windows Update ya instaladas. | Ninguna importante: Windows vuelve a bajar lo que necesite. |
| **Caché de Optimización de entrega**<br>`limp_delivery_opt` | Limpieza | 🟢 bajo | no | sí | Caché de Optimización de entrega. | Ninguna. |
| **Vaciar papelera de reciclaje**<br>`limp_papelera` | Limpieza | 🟠 medio | no | sí | Vacía la papelera de reciclaje. | Lo que está en la papelera se pierde definitivamente. Confirmá que no necesitás nada de ahí. |
| **Vaciar caché DNS**<br>`limp_dns` | Limpieza | 🟢 bajo | no | sí | Vacía la caché DNS. | Ninguna. |

## Profundo - Limpieza + eliminar lo que sobra

**Ideal para:** PC con mucho 'software basura' de fábrica, publicidad en el menú Inicio o que tarda en arrancar.

**Qué hace**

- Todo lo del nivel Básico.
- Desinstala apps preinstaladas innecesarias (Solitario, Noticias, Clima, Clipchamp, Teams personal, juegos de relleno, etc.).
- Apaga sugerencias, publicidad y recomendaciones del menú Inicio y la pantalla de bloqueo.
- Desactiva tareas programadas de telemetría de Microsoft.
- Deshabilita programas de inicio conocidos que no hacen falta (Spotify, Teams, Skype, actualizadores de Adobe/Java...).
- Limpia componentes viejos de Windows (WinSxS).

**Consecuencias a tener en cuenta**

- Las apps desinstaladas desaparecen; si las quiere de nuevo hay que bajarlas de Microsoft Store.
- Los programas que se deshabilitaron del inicio ya no se abren solos (se abren a mano cuando se necesitan).
- Dejan de aparecer apps sugeridas y publicidad en Inicio.

**Reversibilidad:** Registro, tareas e inicio se restauran con un clic. Las apps se intentan recuperar; si no, Microsoft Store.

### Cambios que incorpora este nivel (9)

| Cambio | Grupo | Riesgo | Reversible | Marcado por defecto | Qué hace | Consecuencia |
|---|---|---|---|---|---|---|
| **Desinstalar apps preinstaladas innecesarias**<br>`apps_bloat` | Apps preinstaladas | 🟢 bajo | no | sí | Quita Solitario, Noticias, Clima, Finanzas, Deportes, Obtener ayuda, Sugerencias, Office Hub, Feedback Hub, Mixed Reality, 3D Viewer, Skype, People, Cortana, Clipchamp, Teams personal, Power Automate y juegos/promos de terceros (Candy Crush, TikTok, Netflix, Spotify, Disney, Facebook, Instagram, Amazon...). | Las apps desaparecen del menú Inicio. Si las querés, se bajan de Microsoft Store. |
| **Desinstalar Vincular con el móvil y Correo/Calendario**<br>`apps_opcionales` | Apps preinstaladas | 🟠 medio | no | no | Quita 'Vincular con el móvil' (Phone Link) y las apps Correo y Calendario de Windows. | No se podrá usar Phone Link ni la app de Correo/Calendario. Si las usás, NO marcar. |
| **Apagar publicidad y sugerencias de Windows**<br>`reg_sugerencias` | Publicidad y sugerencias | 🟢 bajo | sí | sí | Desactiva el ID de publicidad, apps sugeridas, consejos, recomendaciones del menú Inicio y anuncios en el Explorador. | Dejan de aparecer apps sugeridas y publicidad en Inicio/bloqueo. Aplica al usuario actual. |
| **Desactivar tareas programadas de telemetría**<br>`tareas_telemetria` | Telemetría | 🟢 bajo | sí | sí | Deshabilita tareas que recopilan y envían datos de uso (Compatibility Appraiser, CEIP, Feedback, etc.). | Microsoft recibe menos datos de uso. Sin efecto en el funcionamiento diario. |
| **Deshabilitar programas de inicio innecesarios**<br>`inicio_conocidos` | Programas de inicio | 🟢 bajo | sí | sí | Deshabilita al arranque: Spotify, Discord, Teams, Skype, actualizadores de Adobe/Java, Edge auto-inicio, CCleaner Monitor, iTunes Helper, Cortana. | Esos programas no se abren solos: se abren a mano cuando se necesitan. Revisá si usás Discord/Spotify siempre. |
| **Limpiar componentes de Windows (WinSxS)**<br>`limp_componentes` | Mantenimiento | 🟢 bajo | no | sí | Elimina versiones viejas de componentes de Windows (WinSxS). Libera varios GB. Lento. | Ya no se pueden desinstalar actualizaciones antiguas. El proceso tarda varios minutos. |
| **Verificar archivos del sistema (SFC)**<br>`limp_sfc` | Mantenimiento | 🟢 bajo | no | no | Verifica y repara archivos dañados de Windows (10-30 min). | Ninguna; solo tarda. Úsalo si la PC tiene errores o cuelgues. |
| **Reparar imagen de Windows (DISM)**<br>`limp_dism` | Mantenimiento | 🟢 bajo | no | no | Repara la imagen de Windows (útil si SFC no pudo reparar). | Ninguna; puede tardar y necesita internet. |
| **Optimizar unidad (desfragmentar / TRIM)**<br>`limp_defrag` | Mantenimiento | 🟢 bajo | no | no | Desfragmenta si es disco mecánico; hace TRIM si es SSD. | En HDD puede tardar horas; la PC va más lenta mientras corre. |

## Extremo / Gaming - Mínimo de procesos

**Ideal para:** PC de juegos o equipos con poca RAM / disco mecánico donde se busca la mayor reducción posible.

**Qué hace**

- Todo lo del nivel Profundo.
- Desactiva servicios innecesarios (telemetría, fax, mapas, modo demo, seguimiento de vínculos...).
- Opcionales según el equipo: SysMain, búsqueda de Windows, cola de impresión, Bluetooth, servicios Xbox.
- Impide que las apps de la Tienda corran en segundo plano y quita Widgets/Noticias.
- Modo Juego activo, grabación en segundo plano (Game DVR) desactivada, efectos visuales mínimos.
- Plan de energía de alto rendimiento (solo PC de escritorio por defecto).

**Consecuencias a tener en cuenta**

- Sin cola de impresión no se puede imprimir; sin Bluetooth no andan auriculares/mouse inalámbricos; sin servicios Xbox no andan Game Pass ni juegos de la Tienda de Microsoft.
- Sin la búsqueda de Windows, buscar archivos desde el Explorador/Inicio es más lento.
- Algunas apps (Correo, Alarmas) no actualizan ni notifican en segundo plano.
- Las ventanas ya no tienen animaciones ni transparencias.
- Si querés volver a usar algo de lo anterior, se restaura en un clic desde la herramienta.

**Reversibilidad:** Todo se deshace con 'restaurar' (guarda el estado original de cada servicio y ajuste) y además existe el punto de restauración de Windows.

### Cambios que incorpora este nivel (16)

| Cambio | Grupo | Riesgo | Reversible | Marcado por defecto | Qué hace | Consecuencia |
|---|---|---|---|---|---|---|
| **Telemetría de Windows al mínimo**<br>`reg_telemetria` | Telemetría | 🟢 bajo | sí | sí | Pone la recolección de diagnóstico al mínimo permitido y apaga avisos de comentarios. | Microsoft recibe el mínimo de datos. En ediciones Home/Pro Windows mantiene un nivel básico obligatorio. |
| **Servicios de telemetría y reportes**<br>`svc_telemetria` | Servicios | 🟢 bajo | sí | sí | Deshabilita 'Experiencias del usuario y telemetría' (DiagTrack), enrutador push (dmwappushservice) y Informe de errores (WerSvc). | No se envían informes de errores a Microsoft. No afecta el uso diario. |
| **Servicios que casi nadie usa**<br>`svc_inutiles` | Servicios | 🟢 bajo | sí | sí | Deshabilita Fax, Mapas descargados, Modo demo de tienda, Uso compartido de Media Player, Seguimiento de vínculos distribuidos y Programa Windows Insider. | No se puede enviar/recibir fax, ni usar mapas sin conexión, ni recibir builds Insider. Para casi todos, sin efecto. |
| **Servicio de ubicación**<br>`svc_geoloc` | Servicios | 🟢 bajo | sí | no | Deshabilita el servicio de geolocalización. | Las apps de clima/mapas no detectan la ubicación solas. |
| **Optimización de entrega en manual**<br>`svc_entrega` | Servicios | 🟢 bajo | sí | sí | Pasa a manual el servicio que comparte descargas de Windows con otras PCs de internet. | Windows Update sigue funcionando; solo deja de compartir ancho de banda. |
| **SysMain (Superfetch)**<br>`svc_sysmain` | Servicios (según equipo) | 🟠 medio | sí | según el equipo | Deshabilita la precarga de programas en RAM. Recomendado en SSD; en disco mecánico conviene dejarlo. | En disco mecánico las apps abren más lento. En SSD no se nota. |
| **Búsqueda de Windows (indexación)**<br>`svc_busqueda` | Servicios (según equipo) | 🟠 medio | sí | según el equipo | Deshabilita el indexador. Reduce mucho el uso de disco en discos mecánicos. | Buscar archivos desde el Explorador/Inicio es mucho más lento. Outlook pierde la búsqueda rápida. |
| **Cola de impresión**<br>`svc_impresion` | Servicios (según equipo) | 🔴 alto | sí | según el equipo | Deshabilita el servicio de impresión (también cierra una puerta de ataques conocida). | NO se podrá imprimir (ni a PDF desde algunas apps) hasta restaurar. Solo para equipos sin impresora. |
| **Bluetooth**<br>`svc_bluetooth` | Servicios (según equipo) | 🔴 alto | sí | no | Deshabilita el servicio de soporte Bluetooth. | Dejan de funcionar auriculares, mouse y teclados Bluetooth. Solo si no los usás. |
| **Servicios de Xbox**<br>`svc_xbox` | Servicios (según equipo) | 🔴 alto | sí | no | Deshabilita autenticación, partidas guardadas, accesorios y red de Xbox. | NO funcionan Game Pass, app de Xbox ni juegos de Microsoft Store. Steam/Epic/Battle.net no se afectan. |
| **Bloquear apps de la Tienda en segundo plano**<br>`reg_segundo_plano` | Procesos en segundo plano | 🟠 medio | sí | sí | Impide que las apps de la Tienda corran en segundo plano y quita Widgets/Noticias. | Apps como Correo, Alarmas o Clima no actualizan ni notifican con la app cerrada. Widgets desaparece. |
| **Modo Juego activo y sin grabación en segundo plano**<br>`reg_gaming` | Gaming | 🟢 bajo | sí | sí | Activa el Modo Juego y apaga Game DVR (grabación automática en segundo plano). | Win+G ya no graba clips automáticamente. Mejor rendimiento y menos procesos al jugar. Aplica al usuario actual. |
| **Programación de GPU acelerada por hardware (HAGS)**<br>`reg_hags` | Gaming | 🟠 medio | sí | no | Activa HAGS. Puede mejorar latencia en GPUs recientes (NVIDIA serie 10+, AMD RX 5000+). | Requiere reiniciar. En algunos drivers/juegos causa cuelgues o peor rendimiento: probar y revertir si pasa. |
| **Efectos visuales mínimos**<br>`reg_visual` | Efectos visuales | 🟢 bajo | sí | sí | Apaga transparencias y animaciones de ventanas y barra de tareas. | La interfaz se ve más 'plana', sin efectos de transición. Se nota al cerrar sesión y volver a entrar. |
| **Plan de energía: Alto rendimiento**<br>`energia` | Energía | 🟠 medio | sí | según el equipo | Evita que el procesador baje de frecuencia para ahorrar energía. | Más consumo y calor. En notebooks reduce mucho la autonomía de la batería. |
| **Desactivar hibernación e inicio rápido**<br>`hibernacion` | Energía | 🟢 bajo | sí | no | Elimina hiberfil.sys (libera gigas = tamaño de la RAM) y desactiva el inicio rápido. | No se puede hibernar y el arranque puede ser unos segundos más lento. Útil si falta espacio en disco. |

## Qué NO toca nunca

- Windows Defender ni el Firewall (no se desactivan ni se modifican).
- Windows Update: no se desactiva; solo se limpian las descargas que ya se instalaron.
- Servicios de red y audio.
- Apps críticas: Microsoft Store, Calculadora, Fotos, Bloc de notas, Terminal, Edge, Seguridad de Windows.
- Archivos personales (documentos, fotos, escritorio).
- El registro de Windows más allá de los ajustes listados arriba (no hay «limpiador de registro»).
