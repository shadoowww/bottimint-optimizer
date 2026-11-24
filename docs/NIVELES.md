# Optimization levels

> Automatically generated from `bottimint/nucleo.py` with `python scripts/generar_docs.py`. Do not edit by hand.

The levels are **cumulative**: Deep includes everything in Basic, and Extreme includes everything in Deep.
Before applying any of them a **Windows restore point** is created and verified; if it cannot be created, **nothing is modified**.

## Basic - General cleanup

**Ideal for:** Any slow PC, low on space, or that hasn't been cleaned in a long time.

**What it does**

- Deletes Windows and user temporary files.
- Empties browser caches, thumbnails, error reports and already-installed Windows Update downloads.
- Empties the Recycle Bin and the DNS cache.

**Consequences to keep in mind**

- Websites load a bit slower the first time (the cache is rebuilt).
- Whatever is in the Recycle Bin is lost forever.
- No service or program is disabled: the PC works exactly as before, with more free space.

**Reversibility:** There is nothing to restore: these are disposable files that Windows recreates by itself.

### Changes introduced by this level (9)

| Change | Group | Risk | Reversible | Checked by default | What it does | Consequence |
|---|---|---|---|---|---|---|
| **User temporary files**<br>`limp_temp_usuario` | Cleanup | 🟢 low | no | yes | Temporary files of the current user (TEMP folder). | An open program may lose an unsaved temporary draft. Close everything first. |
| **Windows temporary files**<br>`limp_temp_windows` | Cleanup | 🟢 low | no | yes | Temporary files in C:\Windows\Temp. | None. |
| **Browser cache**<br>`limp_navegadores` | Cleanup | 🟢 low | no | yes | Chrome, Edge, Brave and Firefox cache. Passwords and history are not touched. | Websites load a bit slower the first time. Close the browsers first. |
| **Internet cache / thumbnails**<br>`limp_inetcache` | Cleanup | 🟢 low | no | yes | Internet cache and Explorer thumbnails. | Thumbnails are regenerated when you open folders with images. |
| **Error reports and dumps**<br>`limp_errores` | Cleanup | 🟢 low | no | yes | Windows error reports and dumps. | Records of past crashes are lost (they are only useful for diagnosing). |
| **Windows Update cache**<br>`limp_windows_update` | Cleanup | 🟢 low | no | yes | Already-installed Windows Update downloads. | Nothing important: Windows downloads again whatever it needs. |
| **Delivery Optimization cache**<br>`limp_delivery_opt` | Cleanup | 🟢 low | no | yes | Delivery Optimization cache. | None. |
| **Empty the Recycle Bin**<br>`limp_papelera` | Cleanup | 🟠 medium | no | yes | Empties the Recycle Bin. | Whatever is in the Recycle Bin is permanently lost. Make sure you don't need anything in there. |
| **Flush DNS cache**<br>`limp_dns` | Cleanup | 🟢 low | no | yes | Flushes the DNS cache. | None. |

## Deep - Cleanup + remove the extras

**Ideal for:** PC with lots of factory 'bloatware', ads in the Start menu, or slow to boot.

**What it does**

- Everything in the Basic level.
- Uninstalls unnecessary preinstalled apps (Solitaire, News, Weather, Clipchamp, personal Teams, filler games, etc.).
- Turns off suggestions, ads and recommendations in the Start menu and lock screen.
- Disables Microsoft telemetry scheduled tasks.
- Disables known startup programs that aren't needed (Spotify, Teams, Skype, Adobe/Java updaters...).
- Cleans old Windows components (WinSxS).

**Consequences to keep in mind**

- Uninstalled apps disappear; if you want them back you have to download them from the Microsoft Store.
- Programs disabled at startup no longer open on their own (open them by hand when you need them).
- Suggested apps and ads stop appearing in Start.

**Reversibility:** Registry, tasks and startup are restored with one click. Apps are recovered when possible; otherwise, from the Microsoft Store.

### Changes introduced by this level (9)

| Change | Group | Risk | Reversible | Checked by default | What it does | Consequence |
|---|---|---|---|---|---|---|
| **Uninstall unnecessary preinstalled apps**<br>`apps_bloat` | Preinstalled apps | 🟢 low | no | yes | Removes Solitaire, News, Weather, Finance, Sports, Get Help, Tips, Office Hub, Feedback Hub, Mixed Reality, 3D Viewer, Skype, People, Cortana, Clipchamp, personal Teams, Power Automate and third-party games/promos (Candy Crush, TikTok, Netflix, Spotify, Disney, Facebook, Instagram, Amazon...). | The apps disappear from the Start menu. If you want them, download them from the Microsoft Store. |
| **Uninstall Phone Link and Mail/Calendar**<br>`apps_opcionales` | Preinstalled apps | 🟠 medium | no | no | Removes 'Phone Link' and the Windows Mail and Calendar apps. | You won't be able to use Phone Link or the Mail/Calendar app. If you use them, do NOT select this. |
| **Turn off Windows ads and suggestions**<br>`reg_sugerencias` | Ads and suggestions | 🟢 low | yes | yes | Disables the advertising ID, suggested apps, tips, Start menu recommendations and ads in Explorer. | Suggested apps and ads stop appearing in Start/lock screen. Applies to the current user. |
| **Disable telemetry scheduled tasks**<br>`tareas_telemetria` | Telemetry | 🟢 low | yes | yes | Disables tasks that collect and send usage data (Compatibility Appraiser, CEIP, Feedback, etc.). | Microsoft receives less usage data. No effect on daily use. |
| **Disable unnecessary startup programs**<br>`inicio_conocidos` | Startup programs | 🟢 low | yes | yes | Disables at boot: Spotify, Discord, Teams, Skype, Adobe/Java updaters, Edge auto-start, CCleaner Monitor, iTunes Helper, Cortana. | Those programs don't open on their own: open them by hand when needed. Check whether you always use Discord/Spotify. |
| **Clean Windows components (WinSxS)**<br>`limp_componentes` | Maintenance | 🟢 low | no | yes | Removes old versions of Windows components (WinSxS). Frees several GB. Slow. | Old updates can no longer be uninstalled. The process takes several minutes. |
| **Verify system files (SFC)**<br>`limp_sfc` | Maintenance | 🟢 low | no | no | Verifies and repairs corrupted Windows files (10-30 min). | None; it just takes time. Use it if the PC has errors or freezes. |
| **Repair Windows image (DISM)**<br>`limp_dism` | Maintenance | 🟢 low | no | no | Repairs the Windows image (useful if SFC couldn't repair). | None; it may take a while and needs internet. |
| **Optimize drive (defragment / TRIM)**<br>`limp_defrag` | Maintenance | 🟢 low | no | no | Defragments if it's a mechanical disk; runs TRIM if it's an SSD. | On an HDD it can take hours; the PC is slower while it runs. |

## Extreme / Gaming - Minimum processes

**Ideal for:** Gaming PCs or machines with little RAM / a mechanical disk where the biggest possible reduction is wanted.

**What it does**

- Everything in the Deep level.
- Disables unnecessary services (telemetry, fax, maps, demo mode, link tracking...).
- Optional depending on the machine: SysMain, Windows Search, print spooler, Bluetooth, Xbox services.
- Stops Store apps from running in the background and removes Widgets/News.
- Game Mode on, background recording (Game DVR) off, minimal visual effects.
- High-performance power plan (desktop PCs only by default).

**Consequences to keep in mind**

- Without the print spooler you can't print; without Bluetooth, wireless headsets/mice don't work; without Xbox services, Game Pass and Microsoft Store games don't work.
- Without Windows Search, finding files from Explorer/Start is slower.
- Some apps (Mail, Alarms) don't update or notify in the background.
- Windows no longer have animations or transparency.
- If you want to use something from the above again, it is restored with one click from the tool.

**Reversibility:** Everything is undone with 'restore' (it stores the original state of every service and setting), and the Windows restore point also exists.

### Changes introduced by this level (16)

| Change | Group | Risk | Reversible | Checked by default | What it does | Consequence |
|---|---|---|---|---|---|---|
| **Windows telemetry to the minimum**<br>`reg_telemetria` | Telemetry | 🟢 low | yes | yes | Sets diagnostic data collection to the minimum allowed and turns off feedback prompts. | Microsoft receives the minimum data. On Home/Pro editions Windows keeps a mandatory basic level. |
| **Telemetry and reporting services**<br>`svc_telemetria` | Services | 🟢 low | yes | yes | Disables 'Connected User Experiences and Telemetry' (DiagTrack), the push router (dmwappushservice) and Error Reporting (WerSvc). | Error reports are not sent to Microsoft. Daily use is not affected. |
| **Services almost nobody uses**<br>`svc_inutiles` | Services | 🟢 low | yes | yes | Disables Fax, Downloaded Maps, Retail Demo, Media Player sharing, Distributed Link Tracking and the Windows Insider Program. | You can't send/receive faxes, use offline maps or get Insider builds. For almost everyone, no effect. |
| **Location service**<br>`svc_geoloc` | Services | 🟢 low | yes | no | Disables the geolocation service. | Weather/maps apps can't detect your location by themselves. |
| **Delivery Optimization on manual**<br>`svc_entrega` | Services | 🟢 low | yes | yes | Sets to manual the service that shares Windows downloads with other PCs on the internet. | Windows Update keeps working; it just stops sharing bandwidth. |
| **SysMain (Superfetch)**<br>`svc_sysmain` | Services (depending on the machine) | 🟠 medium | yes | depends on the machine | Disables program preloading into RAM. Recommended on SSDs; on a mechanical disk it's better to leave it. | On a mechanical disk apps open slower. On an SSD you won't notice. |
| **Windows Search (indexing)**<br>`svc_busqueda` | Services (depending on the machine) | 🟠 medium | yes | depends on the machine | Disables the indexer. Greatly reduces disk usage on mechanical disks. | Searching files from Explorer/Start is much slower. Outlook loses fast search. |
| **Print spooler**<br>`svc_impresion` | Services (depending on the machine) | 🔴 high | yes | depends on the machine | Disables the print service (it also closes a well-known attack surface). | You will NOT be able to print (not even to PDF from some apps) until restored. Only for machines without a printer. |
| **Bluetooth**<br>`svc_bluetooth` | Services (depending on the machine) | 🔴 high | yes | no | Disables the Bluetooth support service. | Bluetooth headsets, mice and keyboards stop working. Only if you don't use them. |
| **Xbox services**<br>`svc_xbox` | Services (depending on the machine) | 🔴 high | yes | no | Disables Xbox authentication, saved games, accessories and networking. | Game Pass, the Xbox app and Microsoft Store games do NOT work. Steam/Epic/Battle.net are not affected. |
| **Block Store apps in the background**<br>`reg_segundo_plano` | Background processes | 🟠 medium | yes | yes | Stops Store apps from running in the background and removes Widgets/News. | Apps like Mail, Alarms or Weather don't update or notify while closed. Widgets disappears. |
| **Game Mode on and no background recording**<br>`reg_gaming` | Gaming | 🟢 low | yes | yes | Turns on Game Mode and turns off Game DVR (automatic background recording). | Win+G no longer records clips automatically. Better performance and fewer processes while gaming. Applies to the current user. |
| **Hardware-accelerated GPU scheduling (HAGS)**<br>`reg_hags` | Gaming | 🟠 medium | yes | no | Turns on HAGS. May improve latency on recent GPUs (NVIDIA 10 series+, AMD RX 5000+). | Requires a reboot. With some drivers/games it causes crashes or worse performance: test it and revert if that happens. |
| **Minimal visual effects**<br>`reg_visual` | Visual effects | 🟢 low | yes | yes | Turns off transparency and animations of windows and the taskbar. | The interface looks more 'flat', without transition effects. You notice it after signing out and back in. |
| **Power plan: High performance**<br>`energia` | Power | 🟠 medium | yes | depends on the machine | Prevents the processor from lowering its frequency to save power. | More power use and heat. On laptops it greatly reduces battery life. |
| **Disable hibernation and fast startup**<br>`hibernacion` | Power | 🟢 low | yes | no | Deletes hiberfil.sys (frees gigabytes = size of the RAM) and disables fast startup. | You can't hibernate and boot may be a few seconds slower. Useful if disk space is short. |

## What it NEVER touches

- Windows Defender and the Firewall (never disabled or modified).
- Windows Update: never disabled; only the downloads that were already installed are cleaned.
- Network and audio services.
- Critical apps: Microsoft Store, Calculator, Photos, Notepad, Terminal, Edge, Windows Security.
- Personal files (documents, photos, desktop).
- The Windows registry beyond the settings listed above (there is no "registry cleaner").
