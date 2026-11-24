# Catálogo de programas

> Generado automáticamente desde `bottimint/instalador.py` con `python scripts/generar_docs.py`. No editar a mano.

Todo se instala con **winget** (fuente oficial `winget`), en silencio y con el ID exacto.

## Perfiles

### `oficina` - PC de oficina / hogar

Lo básico para trabajar y navegar.

Google Chrome, 7-Zip, VLC, LibreOffice, SumatraPDF, WhatsApp, Zoom, AnyDesk

### `gamer` - PC gamer

Launchers, comunicación, grabación y todos los runtimes que piden los juegos.

Google Chrome, 7-Zip, VLC, Discord, Steam, Epic Games Launcher, Ubisoft Connect, EA app, OBS Studio, Visual C++ 2015-2022 (x64), Visual C++ 2015-2022 (x86), Visual C++ 2013 (x64), Visual C++ 2013 (x86), .NET Desktop Runtime 8, .NET Desktop Runtime 9, DirectX (runtime legacy)

### `herramientas` - Herramientas de sistema

Utilidades de diagnóstico, edición y desarrollo.

7-Zip, Notepad++, AnyDesk, Everything, WinDirStat, CrystalDiskInfo, HWiNFO, Rufus, PowerToys, Python 3.13, Git, Visual Studio Code

## Catálogo completo


### Navegadores

| Programa | ID de winget | Descripción | Nota |
|---|---|---|---|
| Google Chrome | `Google.Chrome` | Navegador de Google. |  |
| Mozilla Firefox | `Mozilla.Firefox` | Navegador de Mozilla, enfocado en privacidad. |  |
| Brave | `Brave.Brave` | Navegador con bloqueo de anuncios incluido. |  |
| Microsoft Edge | `Microsoft.Edge` | Viene con Windows; sirve para reinstalarlo/actualizarlo. |  |

### Esenciales

| Programa | ID de winget | Descripción | Nota |
|---|---|---|---|
| 7-Zip | `7zip.7zip` | Compresor/descompresor de archivos (zip, rar, 7z...). |  |
| VLC | `VideoLAN.VLC` | Reproductor de video y audio que lee todo. |  |
| Notepad++ | `Notepad++.Notepad++` | Editor de texto avanzado. |  |
| LibreOffice | `TheDocumentFoundation.LibreOffice` | Suite de oficina gratuita (Word/Excel/PowerPoint compatibles). |  |
| Adobe Acrobat Reader | `Adobe.Acrobat.Reader.64-bit` | Lector de PDF de Adobe. |  |
| SumatraPDF | `SumatraPDF.SumatraPDF` | Lector de PDF liviano y rápido (alternativa a Adobe). |  |
| WhatsApp | `WhatsApp.WhatsApp` | WhatsApp de escritorio. |  |
| Zoom | `Zoom.Zoom` | Videollamadas y reuniones. |  |
| Telegram | `Telegram.TelegramDesktop` | Mensajería Telegram de escritorio. |  |
| Discord | `Discord.Discord` | Chat de voz y texto (también muy usado en gaming). |  |

### Utilidades

| Programa | ID de winget | Descripción | Nota |
|---|---|---|---|
| AnyDesk | `AnyDeskSoftwareGmbH.AnyDesk` | Escritorio remoto para dar soporte a distancia. | Uso gratuito solo personal: para uso comercial/empresas requiere licencia. |
| TeamViewer | `TeamViewer.TeamViewer` | Escritorio remoto para soporte a distancia. | Uso gratuito solo personal: para uso comercial/empresas requiere licencia. |
| Everything | `voidtools.Everything` | Búsqueda instantánea de archivos. |  |
| PowerToys | `Microsoft.PowerToys` | Utilidades avanzadas de Microsoft para Windows. |  |
| WinDirStat | `WinDirStat.WinDirStat` | Muestra qué ocupa espacio en el disco. |  |
| CrystalDiskInfo | `CrystalDewWorld.CrystalDiskInfo` | Estado de salud de discos (SMART). |  |
| HWiNFO | `REALiX.HWiNFO` | Información y sensores de hardware (temperaturas, etc.). |  |
| Rufus | `Rufus.Rufus` | Crea pendrives booteables (instalar Windows). |  |
| VirtualBox | `Oracle.VirtualBox` | Máquinas virtuales. |  |

### Desarrollo

| Programa | ID de winget | Descripción | Nota |
|---|---|---|---|
| Python 3.13 | `Python.Python.3.13` | Lenguaje Python. |  |
| Git | `Git.Git` | Control de versiones. |  |
| Visual Studio Code | `Microsoft.VisualStudioCode` | Editor de código. |  |
| Node.js LTS | `OpenJS.NodeJS.LTS` | Entorno de ejecución JavaScript (versión estable). |  |

### Gaming

| Programa | ID de winget | Descripción | Nota |
|---|---|---|---|
| Steam | `Valve.Steam` | Tienda y launcher de Valve. |  |
| Epic Games Launcher | `EpicGames.EpicGamesLauncher` | Tienda y launcher de Epic (juegos gratis semanales). |  |
| Ubisoft Connect | `Ubisoft.Connect` | Launcher de juegos Ubisoft. |  |
| EA app | `ElectronicArts.EADesktop` | Launcher de juegos de Electronic Arts. |  |
| GOG Galaxy | `GOG.Galaxy` | Launcher de GOG (juegos sin DRM). |  |
| Battle.net | `Blizzard.BattleNet` | Launcher de juegos Blizzard. |  |
| OBS Studio | `OBSProject.OBSStudio` | Grabación y streaming de pantalla. |  |

### Runtimes

| Programa | ID de winget | Descripción | Nota |
|---|---|---|---|
| Visual C++ 2015-2022 (x64) | `Microsoft.VCRedist.2015+.x64` | Librerías que piden casi todos los juegos y programas. |  |
| Visual C++ 2015-2022 (x86) | `Microsoft.VCRedist.2015+.x86` | Versión de 32 bits (programas viejos). |  |
| Visual C++ 2013 (x64) | `Microsoft.VCRedist.2013.x64` | Juegos y programas de 2013-2015. |  |
| Visual C++ 2013 (x86) | `Microsoft.VCRedist.2013.x86` | Versión de 32 bits. |  |
| .NET Desktop Runtime 8 | `Microsoft.DotNet.DesktopRuntime.8` | Necesario para apps de escritorio hechas en .NET 8. |  |
| .NET Desktop Runtime 9 | `Microsoft.DotNet.DesktopRuntime.9` | Necesario para apps de escritorio hechas en .NET 9. |  |
| DirectX (runtime legacy) | `Microsoft.DirectX` | Librerías DirectX antiguas que piden algunos juegos viejos. |  |

## Agregar un programa

1. Buscá el ID exacto: `winget search <nombre>` (columna *Id*) y comprobá con `winget show --id <ID> --exact`.
2. Agregá una línea `Programa(...)` en `CATALOGO` (`bottimint/instalador.py`) y, si corresponde, su ID en un perfil.
3. Ejecutá `python scripts/generar_docs.py` y `python -m unittest discover -s tests -t .`.
