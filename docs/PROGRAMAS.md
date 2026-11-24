# Program catalog

> Automatically generated from `bottimint/instalador.py` with `python scripts/generar_docs.py`. Do not edit by hand.

Everything is installed with **winget** (official `winget` source), silently and with the exact ID.

## Profiles

### `oficina` - Office / home PC

The basics for working and browsing.

Google Chrome, 7-Zip, VLC, LibreOffice, SumatraPDF, WhatsApp, Zoom, AnyDesk

### `gamer` - Gaming PC

Launchers, communication, recording and all the runtimes games ask for.

Google Chrome, 7-Zip, VLC, Discord, Steam, Epic Games Launcher, Ubisoft Connect, EA app, OBS Studio, Visual C++ 2015-2022 (x64), Visual C++ 2015-2022 (x86), Visual C++ 2013 (x64), Visual C++ 2013 (x86), .NET Desktop Runtime 8, .NET Desktop Runtime 9, DirectX (runtime legacy)

### `herramientas` - System tools

Diagnostic, editing and development utilities.

7-Zip, Notepad++, AnyDesk, Everything, WinDirStat, CrystalDiskInfo, HWiNFO, Rufus, PowerToys, Python 3.13, Git, Visual Studio Code

## Full catalog


### Browsers

| Program | winget ID | Description | Note |
|---|---|---|---|
| Google Chrome | `Google.Chrome` | Google's browser. |  |
| Mozilla Firefox | `Mozilla.Firefox` | Mozilla's browser, focused on privacy. |  |
| Brave | `Brave.Brave` | Browser with built-in ad blocking. |  |
| Microsoft Edge | `Microsoft.Edge` | Ships with Windows; useful to reinstall/update it. |  |

### Essentials

| Program | winget ID | Description | Note |
|---|---|---|---|
| 7-Zip | `7zip.7zip` | File compressor/extractor (zip, rar, 7z...). |  |
| VLC | `VideoLAN.VLC` | Video and audio player that plays everything. |  |
| Notepad++ | `Notepad++.Notepad++` | Advanced text editor. |  |
| LibreOffice | `TheDocumentFoundation.LibreOffice` | Free office suite (Word/Excel/PowerPoint compatible). |  |
| Adobe Acrobat Reader | `Adobe.Acrobat.Reader.64-bit` | Adobe's PDF reader. |  |
| SumatraPDF | `SumatraPDF.SumatraPDF` | Lightweight, fast PDF reader (Adobe alternative). |  |
| WhatsApp | `WhatsApp.WhatsApp` | WhatsApp for desktop. |  |
| Zoom | `Zoom.Zoom` | Video calls and meetings. |  |
| Telegram | `Telegram.TelegramDesktop` | Telegram messenger for desktop. |  |
| Discord | `Discord.Discord` | Voice and text chat (also widely used for gaming). |  |

### Utilities

| Program | winget ID | Description | Note |
|---|---|---|---|
| AnyDesk | `AnyDeskSoftwareGmbH.AnyDesk` | Remote desktop for remote support. | Free for personal use only: commercial/business use requires a license. |
| TeamViewer | `TeamViewer.TeamViewer` | Remote desktop for remote support. | Free for personal use only: commercial/business use requires a license. |
| Everything | `voidtools.Everything` | Instant file search. |  |
| PowerToys | `Microsoft.PowerToys` | Advanced Microsoft utilities for Windows. |  |
| WinDirStat | `WinDirStat.WinDirStat` | Shows what is taking up disk space. |  |
| CrystalDiskInfo | `CrystalDewWorld.CrystalDiskInfo` | Disk health status (SMART). |  |
| HWiNFO | `REALiX.HWiNFO` | Hardware information and sensors (temperatures, etc.). |  |
| Rufus | `Rufus.Rufus` | Creates bootable USB drives (to install Windows). |  |
| VirtualBox | `Oracle.VirtualBox` | Virtual machines. |  |

### Development

| Program | winget ID | Description | Note |
|---|---|---|---|
| Python 3.13 | `Python.Python.3.13` | Python language. |  |
| Git | `Git.Git` | Version control. |  |
| Visual Studio Code | `Microsoft.VisualStudioCode` | Code editor. |  |
| Node.js LTS | `OpenJS.NodeJS.LTS` | JavaScript runtime (stable version). |  |

### Gaming

| Program | winget ID | Description | Note |
|---|---|---|---|
| Steam | `Valve.Steam` | Valve's store and launcher. |  |
| Epic Games Launcher | `EpicGames.EpicGamesLauncher` | Epic's store and launcher (free weekly games). |  |
| Ubisoft Connect | `Ubisoft.Connect` | Ubisoft game launcher. |  |
| EA app | `ElectronicArts.EADesktop` | Electronic Arts game launcher. |  |
| GOG Galaxy | `GOG.Galaxy` | GOG launcher (DRM-free games). |  |
| Battle.net | `Blizzard.BattleNet` | Blizzard game launcher. |  |
| OBS Studio | `OBSProject.OBSStudio` | Screen recording and streaming. |  |

### Runtimes

| Program | winget ID | Description | Note |
|---|---|---|---|
| Visual C++ 2015-2022 (x64) | `Microsoft.VCRedist.2015+.x64` | Libraries that almost all games and programs require. |  |
| Visual C++ 2015-2022 (x86) | `Microsoft.VCRedist.2015+.x86` | 32-bit version (old programs). |  |
| Visual C++ 2013 (x64) | `Microsoft.VCRedist.2013.x64` | Games and programs from 2013-2015. |  |
| Visual C++ 2013 (x86) | `Microsoft.VCRedist.2013.x86` | 32-bit version. |  |
| .NET Desktop Runtime 8 | `Microsoft.DotNet.DesktopRuntime.8` | Required for desktop apps built on .NET 8. |  |
| .NET Desktop Runtime 9 | `Microsoft.DotNet.DesktopRuntime.9` | Required for desktop apps built on .NET 9. |  |
| DirectX (runtime legacy) | `Microsoft.DirectX` | Old DirectX libraries that some older games require. |  |

## Adding a program

1. Find the exact ID: `winget search <name>` (*Id* column) and check it with `winget show --id <ID> --exact`.
2. Add a `Programa(...)` line to `CATALOGO` (`bottimint/instalador.py`) and, if appropriate, its ID to a profile. Add the English text of the description to `bottimint/idiomas/en.py`.
3. Run `python scripts/generar_docs.py` and `python -m unittest discover -s tests -t .`.
