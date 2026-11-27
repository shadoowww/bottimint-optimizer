#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
instalador.py - Módulo de instalación de software esencial (usa winget).

* Catálogo corto y curado, por categorías (Navegadores, Esenciales, Utilidades, Desarrollo, Gaming, Runtimes).
* Perfiles listos: oficina, gamer, herramientas (se pueden combinar y ajustar).
* Todo se instala con winget (fuente oficial "winget"), en silencio, con ID exacto.
* Detecta qué ya está instalado, verifica que cada ID exista y deja un informe.

Uso (consola, como administrador):
    python -m bottimint programas catalogo
    python -m bottimint programas perfiles
    python -m bottimint programas plan --perfil gamer
    python -m bottimint programas instalar --perfil oficina [--ids Valve.Steam,Discord.Discord] [--si]
    python -m bottimint programas verificar            (comprueba que los IDs del catálogo existan en winget)
    python -m bottimint programas actualizar           (actualiza todo lo instalado con winget)
    python -m bottimint programas winget               (comprueba/repara la instalación de winget)

Requisitos: Windows 10 (1809+) o Windows 11 con "Instalador de aplicaciones" (winget).
"""
import argparse
import datetime
import json
import re
import shutil
import os
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from . import confiables
from . import limpieza as base


@dataclass(frozen=True)
class Programa:
    id: str
    nombre: str
    categoria: str
    descripcion: str
    nota: str = ""


C_NAV, C_ESE, C_UTI, C_DEV, C_GAM, C_RUN = "Navegadores", "Esenciales", "Utilidades", "Desarrollo", "Gaming", "Runtimes"
LIC = "Uso gratuito solo personal: para uso comercial/empresas requiere licencia."

CATALOGO: List[Programa] = [
    # Navegadores
    Programa("Google.Chrome", "Google Chrome", C_NAV, "Navegador de Google."),
    Programa("Mozilla.Firefox", "Mozilla Firefox", C_NAV, "Navegador de Mozilla, enfocado en privacidad."),
    Programa("Brave.Brave", "Brave", C_NAV, "Navegador con bloqueo de anuncios incluido."),
    Programa("Microsoft.Edge", "Microsoft Edge", C_NAV, "Viene con Windows; sirve para reinstalarlo/actualizarlo."),
    # Esenciales
    Programa("7zip.7zip", "7-Zip", C_ESE, "Compresor/descompresor de archivos (zip, rar, 7z...)."),
    Programa("VideoLAN.VLC", "VLC", C_ESE, "Reproductor de video y audio que lee todo."),
    Programa("Notepad++.Notepad++", "Notepad++", C_ESE, "Editor de texto avanzado."),
    Programa("TheDocumentFoundation.LibreOffice", "LibreOffice", C_ESE, "Suite de oficina gratuita (Word/Excel/PowerPoint compatibles)."),
    Programa("Adobe.Acrobat.Reader.64-bit", "Adobe Acrobat Reader", C_ESE, "Lector de PDF de Adobe."),
    Programa("SumatraPDF.SumatraPDF", "SumatraPDF", C_ESE, "Lector de PDF liviano y rápido (alternativa a Adobe)."),
    Programa("WhatsApp.WhatsApp", "WhatsApp", C_ESE, "WhatsApp de escritorio."),
    Programa("Zoom.Zoom", "Zoom", C_ESE, "Videollamadas y reuniones."),
    Programa("Telegram.TelegramDesktop", "Telegram", C_ESE, "Mensajería Telegram de escritorio."),
    Programa("Discord.Discord", "Discord", C_ESE, "Chat de voz y texto (también muy usado en gaming)."),
    # Utilidades
    Programa("AnyDeskSoftwareGmbH.AnyDesk", "AnyDesk", C_UTI, "Escritorio remoto para dar soporte a distancia.", LIC),
    Programa("TeamViewer.TeamViewer", "TeamViewer", C_UTI, "Escritorio remoto para soporte a distancia.", LIC),
    Programa("voidtools.Everything", "Everything", C_UTI, "Búsqueda instantánea de archivos."),
    Programa("Microsoft.PowerToys", "PowerToys", C_UTI, "Utilidades avanzadas de Microsoft para Windows."),
    Programa("WinDirStat.WinDirStat", "WinDirStat", C_UTI, "Muestra qué ocupa espacio en el disco."),
    Programa("CrystalDewWorld.CrystalDiskInfo", "CrystalDiskInfo", C_UTI, "Estado de salud de discos (SMART)."),
    Programa("REALiX.HWiNFO", "HWiNFO", C_UTI, "Información y sensores de hardware (temperaturas, etc.)."),
    Programa("Rufus.Rufus", "Rufus", C_UTI, "Crea pendrives booteables (instalar Windows)."),
    Programa("Oracle.VirtualBox", "VirtualBox", C_UTI, "Máquinas virtuales."),
    # Desarrollo
    Programa("Python.Python.3.13", "Python 3.13", C_DEV, "Lenguaje Python."),
    Programa("Git.Git", "Git", C_DEV, "Control de versiones."),
    Programa("Microsoft.VisualStudioCode", "Visual Studio Code", C_DEV, "Editor de código."),
    Programa("OpenJS.NodeJS.LTS", "Node.js LTS", C_DEV, "Entorno de ejecución JavaScript (versión estable)."),
    # Gaming
    Programa("Valve.Steam", "Steam", C_GAM, "Tienda y launcher de Valve."),
    Programa("EpicGames.EpicGamesLauncher", "Epic Games Launcher", C_GAM, "Tienda y launcher de Epic (juegos gratis semanales)."),
    Programa("Ubisoft.Connect", "Ubisoft Connect", C_GAM, "Launcher de juegos Ubisoft."),
    Programa("ElectronicArts.EADesktop", "EA app", C_GAM, "Launcher de juegos de Electronic Arts."),
    Programa("GOG.Galaxy", "GOG Galaxy", C_GAM, "Launcher de GOG (juegos sin DRM)."),
    Programa("Blizzard.BattleNet", "Battle.net", C_GAM, "Launcher de juegos Blizzard."),
    Programa("OBSProject.OBSStudio", "OBS Studio", C_GAM, "Grabación y streaming de pantalla."),
    # Runtimes (muchos juegos y programas los piden)
    Programa("Microsoft.VCRedist.2015+.x64", "Visual C++ 2015-2022 (x64)", C_RUN, "Librerías que piden casi todos los juegos y programas."),
    Programa("Microsoft.VCRedist.2015+.x86", "Visual C++ 2015-2022 (x86)", C_RUN, "Versión de 32 bits (programas viejos)."),
    Programa("Microsoft.VCRedist.2013.x64", "Visual C++ 2013 (x64)", C_RUN, "Juegos y programas de 2013-2015."),
    Programa("Microsoft.VCRedist.2013.x86", "Visual C++ 2013 (x86)", C_RUN, "Versión de 32 bits."),
    Programa("Microsoft.DotNet.DesktopRuntime.8", ".NET Desktop Runtime 8", C_RUN, "Necesario para apps de escritorio hechas en .NET 8."),
    Programa("Microsoft.DotNet.DesktopRuntime.9", ".NET Desktop Runtime 9", C_RUN, "Necesario para apps de escritorio hechas en .NET 9."),
    Programa("Microsoft.DirectX", "DirectX (runtime legacy)", C_RUN, "Librerías DirectX antiguas que piden algunos juegos viejos."),
]
POR_ID: Dict[str, Programa] = {p.id: p for p in CATALOGO}

_RUNTIMES = ["Microsoft.VCRedist.2015+.x64", "Microsoft.VCRedist.2015+.x86", "Microsoft.VCRedist.2013.x64",
             "Microsoft.VCRedist.2013.x86", "Microsoft.DotNet.DesktopRuntime.8", "Microsoft.DotNet.DesktopRuntime.9",
             "Microsoft.DirectX"]

PERFILES: Dict[str, dict] = {
    "oficina": {"titulo": "PC de oficina / hogar", "descripcion": "Lo básico para trabajar y navegar.",
                "ids": ["Google.Chrome", "7zip.7zip", "VideoLAN.VLC", "TheDocumentFoundation.LibreOffice",
                        "SumatraPDF.SumatraPDF", "WhatsApp.WhatsApp", "Zoom.Zoom", "AnyDeskSoftwareGmbH.AnyDesk"]},
    "gamer": {"titulo": "PC gamer", "descripcion": "Launchers, comunicación, grabación y todos los runtimes que piden los juegos.",
              "ids": ["Google.Chrome", "7zip.7zip", "VideoLAN.VLC", "Discord.Discord", "Valve.Steam",
                      "EpicGames.EpicGamesLauncher", "Ubisoft.Connect", "ElectronicArts.EADesktop", "OBSProject.OBSStudio"] + _RUNTIMES},
    "herramientas": {"titulo": "Herramientas de sistema", "descripcion": "Utilidades de diagnóstico, edición y desarrollo.",
                "ids": ["7zip.7zip", "Notepad++.Notepad++", "AnyDeskSoftwareGmbH.AnyDesk", "voidtools.Everything",
                        "WinDirStat.WinDirStat", "CrystalDewWorld.CrystalDiskInfo", "REALiX.HWiNFO", "Rufus.Rufus",
                        "Microsoft.PowerToys", "Python.Python.3.13", "Git.Git", "Microsoft.VisualStudioCode"]},
}

# códigos de salida de winget / instaladores
OK = {0, 3010}                                        # 3010 = éxito, requiere reinicio
YA_INSTALADO = {0x8A15002B, 0x8A150061, 0x8A15010D}   # sin actualización aplicable / ya instalado
NO_EXISTE = {0x8A150014, 0x8A150010}                  # paquete no encontrado


# Un ID de winget válido nunca empieza con "-" ni tiene espacios/metacaracteres: así no se puede colar una opción.
RE_ID_WINGET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}\Z")


def id_valido(id_: str) -> bool:
    return isinstance(id_, str) and RE_ID_WINGET.match(id_) is not None


def _cod(c: int) -> int:
    return c & 0xFFFFFFFF


# Instala «Instalador de aplicaciones» (winget) desde los servidores oficiales de Microsoft. Solo URLs fijas (nada del
# usuario se mezcla con el script). Antes de instalar se exige firma válida de Microsoft en los tres archivos; Windows
# vuelve a verificar la firma al instalar y después se comprueba el editor del paquete instalado.
SCRIPT_INSTALAR_WINGET = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$arq = switch ($env:PROCESSOR_ARCHITECTURE) { 'ARM64' { 'arm64' } 'x86' { 'x86' } default { 'x64' } }
$dir = Join-Path ([IO.Path]::GetTempPath()) ('bottimint_winget_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $dir | Out-Null
try {
  $vc = Join-Path $dir 'vclibs.appx'; $xaml = Join-Path $dir 'xaml.appx'; $wg = Join-Path $dir 'winget.msixbundle'
  Invoke-WebRequest -UseBasicParsing -Uri "https://aka.ms/Microsoft.VCLibs.$arq.14.00.Desktop.appx" -OutFile $vc
  Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/microsoft/microsoft-ui-xaml/releases/download/v2.8.6/Microsoft.UI.Xaml.2.8.$arq.appx" -OutFile $xaml
  Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/microsoft/winget-cli/releases/latest/download/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle' -OutFile $wg
  # ANTES de instalar nada: los tres archivos deben tener firma valida y de Microsoft
  foreach ($f in @($wg, $vc, $xaml)) {
    $firma = Get-AuthenticodeSignature -LiteralPath $f
    if ($firma.Status -ne 'Valid' -or $firma.SignerCertificate.Subject -notmatch '(^|, )O=Microsoft Corporation(,|$)') {
      throw ('No se instala: ' + (Split-Path $f -Leaf) + ' no tiene una firma valida de Microsoft (' + $firma.Status + ')')
    }
  }
  Add-AppxPackage -Path $wg -DependencyPath $vc, $xaml
  $p = Get-AppxPackage -Name Microsoft.DesktopAppInstaller
  if (-not $p -or $p.Publisher -notlike 'CN=Microsoft Corporation*') { throw 'El paquete instalado no es de Microsoft' }
  Write-Output 'winget instalado.'
} finally { Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue }
"""


class Winget:
    """Envuelve winget. `run` es inyectable para poder probar sin Windows."""

    def __init__(self, run: Optional[Callable[..., Tuple[int, str]]] = None, base_dir: Optional[str] = None):
        self.run = run or base.ejecutar
        self.base_dir = base_dir or confiables.carpeta_de_datos()

    def disponible(self) -> bool:
        cod, out = self.run(["winget", "--version"], 30)
        return cod == 0 and out.strip().startswith("v")

    def intentar_reparar(self) -> bool:
        """En instalaciones nuevas winget a veces está presente pero sin registrar."""
        self.run(["powershell", "-NoProfile", "-Command",
                  "Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe"], 180)
        return self.disponible()

    def instalar_winget(self, emitir: Callable[[str], None] = print) -> bool:
        """Deja winget funcionando: 1) lo registra si ya venía con Windows; 2) si no, lo descarga de Microsoft."""
        if self.disponible():
            return True
        emitir("Registrando «Instalador de aplicaciones» (winget)...")
        if self.intentar_reparar():
            emitir("winget quedó disponible.")
            return True
        emitir("No estaba en el equipo: descargando desde los servidores oficiales de Microsoft (puede tardar)...")
        cod, out = self.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                             "-Command", SCRIPT_INSTALAR_WINGET], 900)
        if cod != 0 and out:
            emitir(out[-600:])
        ok = self.disponible() or self.intentar_reparar()
        emitir("winget instalado." if ok else "No se pudo instalar winget. Instalá «Instalador de aplicaciones» desde Microsoft Store.")
        return ok

    def instalados(self) -> set:
        """IDs instalados, vía `winget export` (JSON: no depende del idioma de Windows)."""
        # nombre único e impredecible (evita choques entre ejecuciones y ataques por archivo temporal predecible)
        # carpeta privada (permisos solo del usuario) creada con nombre aleatorio: nadie puede pre-crear el archivo
        carpeta_tmp = tempfile.mkdtemp(prefix="bottimint_export_")
        ruta = os.path.join(carpeta_tmp, "export.json")
        ids = set()
        try:
            self.run(["winget", "export", "-o", ruta, "--accept-source-agreements", "--disable-interactivity"], 180)
            with open(ruta, encoding="utf-8-sig") as f:
                data = json.load(f)
            for src in data.get("Sources", []):
                for p in src.get("Packages", []):
                    ids.add(p.get("PackageIdentifier", "").lower())
        except (OSError, ValueError):
            pass
        finally:
            shutil.rmtree(carpeta_tmp, ignore_errors=True)
        return ids

    def existe(self, id_: str) -> bool:
        if not id_valido(id_):
            return False
        cod, _ = self.run(["winget", "show", "--id", id_, "--exact", "--source", "winget",
                           "--accept-source-agreements", "--disable-interactivity"], 60)
        return _cod(cod) == 0

    def instalar(self, id_: str) -> Tuple[str, str]:
        """Devuelve (estado, detalle): ok | reinicio | ya | no_existe | error."""
        if not id_valido(id_):
            return "error", "ID de paquete no válido"
        cod, out = self.run(["winget", "install", "--id", id_, "--exact", "--source", "winget", "--silent",
                             "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"], 1800)
        c = _cod(cod)
        if c == 0:
            return "ok", "instalado"
        if c == 3010:
            return "reinicio", "instalado (requiere reiniciar)"
        if c in YA_INSTALADO:
            return "ya", "ya estaba instalado"
        if c in NO_EXISTE:
            return "no_existe", "no se encontró el paquete en winget"
        return "error", f"winget devolvió el código {c:#x}: {out[-200:].strip()}"

    def actualizar_todo(self) -> Tuple[int, str]:
        return self.run(["winget", "upgrade", "--all", "--silent", "--accept-package-agreements",
                         "--accept-source-agreements", "--disable-interactivity"], 3600)


def ids_de(perfiles: List[str], extra: Optional[List[str]] = None) -> List[str]:
    vistos, res = set(), []
    for pid in [i for p in perfiles for i in PERFILES[p]["ids"]] + list(extra or []):
        if pid not in vistos:
            vistos.add(pid)
            res.append(pid)
    return res


def plan(ids: List[str], wg: Winget) -> List[dict]:
    """Vista previa: qué se instalaría y qué ya está."""
    instalados = wg.instalados()
    res = []
    for i in ids:
        p = POR_ID.get(i) or Programa(i, i, "Otro", "ID personalizado")
        res.append({"id": i, "nombre": p.nombre, "categoria": p.categoria, "descripcion": p.descripcion, "nota": p.nota,
                    "instalado": i.lower() in instalados, "seleccionado": i.lower() not in instalados})
    return res


def instalar_lote(ids: List[str], wg: Winget, emitir: Callable[[str], None] = print,
                  al_terminar: Callable[[str, str], None] = lambda i, e: None) -> List[dict]:
    if not wg.disponible() and not wg.intentar_reparar():
        emitir("ERROR: winget no está disponible. En Windows 10 instalá 'Instalador de aplicaciones' desde Microsoft Store.")
        return []
    instalados = wg.instalados()
    resultados = []
    for n, i in enumerate(ids, 1):
        nombre = POR_ID[i].nombre if i in POR_ID else i
        emitir(f"[{n}/{len(ids)}] {nombre}...")
        if i.lower() in instalados:
            estado, detalle = "ya", "ya estaba instalado"
        elif not wg.existe(i):
            estado, detalle = "no_existe", "no se encontró el paquete en winget (ID cambiado o sin conexión)"
        else:
            estado, detalle = wg.instalar(i)
        emitir(f"   {detalle}")
        resultados.append({"id": i, "nombre": nombre, "estado": estado, "detalle": detalle})
        al_terminar(i, estado)
    _informe(wg, resultados, emitir)
    return resultados


def _informe(wg: Winget, resultados: List[dict], emitir) -> None:
    ahora = datetime.datetime.now()
    marca = {"ok": "OK", "reinicio": "OK (reiniciar)", "ya": "YA ESTABA", "no_existe": "NO ENCONTRADO", "error": "ERROR"}
    L = ["BottiMint - INFORME DE INSTALACIÓN", "=" * 50, f"Fecha: {ahora:%d/%m/%Y %H:%M}", ""]
    L += [f"  [{marca[r['estado']]}] {r['nombre']}: {r['detalle']}" for r in resultados]
    carpeta = os.path.join(wg.base_dir, "instalaciones")
    try:
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, f"instalacion_{ahora:%Y%m%d_%H%M%S}.txt")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("\n".join(L))
        emitir(f"Informe guardado en: {ruta}")
    except OSError:
        pass


def verificar_catalogo(wg: Winget, emitir: Callable[[str], None] = print) -> List[str]:
    """Devuelve los IDs del catálogo que winget NO encuentra."""
    faltan = []
    for p in CATALOGO:
        ok = wg.existe(p.id)
        emitir(f"{'OK ' if ok else 'NO '} {p.id}")
        if not ok:
            faltan.append(p.id)
    return faltan


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Instalador de software esencial (winget)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("catalogo")
    sub.add_parser("perfiles")
    for nombre in ("plan", "instalar"):
        p = sub.add_parser(nombre)
        p.add_argument("--perfil", default="", help="uno o varios separados por coma: " + ", ".join(PERFILES))
        p.add_argument("--ids", default="", help="IDs de winget separados por coma")
        if nombre == "instalar":
            p.add_argument("--si", action="store_true", help="no pedir confirmación")
    sub.add_parser("verificar")
    sub.add_parser("actualizar")
    sub.add_parser("winget")
    a = ap.parse_args()
    wg = Winget()

    if a.cmd == "catalogo":
        cat = ""
        for p in CATALOGO:
            if p.categoria != cat:
                cat = p.categoria
                print(f"\n== {cat} ==")
            print(f"  {p.id:<40} {p.nombre}" + (f"   [{p.nota}]" if p.nota else ""))
    elif a.cmd == "perfiles":
        for k, v in PERFILES.items():
            print(f"{k}: {v['titulo']} - {v['descripcion']}")
            print("   " + ", ".join(POR_ID[i].nombre for i in v["ids"]))
    elif a.cmd in ("plan", "instalar"):
        perfiles = [x for x in a.perfil.split(",") if x]
        malos = [x for x in perfiles if x not in PERFILES]
        if malos:
            sys.exit(f"Perfil desconocido: {', '.join(malos)}. Disponibles: {', '.join(PERFILES)}")
        ids = ids_de(perfiles, [x for x in a.ids.split(",") if x])
        if not ids:
            sys.exit("Indicá --perfil y/o --ids.")
        if not wg.disponible() and not wg.intentar_reparar():
            sys.exit("winget no está disponible en este equipo.")
        pl = plan(ids, wg)
        for x in pl:
            print(f"[{'x' if x['seleccionado'] else '=' }] {x['nombre']:<32} {'(ya instalado)' if x['instalado'] else ''}"
                  + (f"  ! {x['nota']}" if x['nota'] else ""))
        if a.cmd == "instalar":
            pend = [x["id"] for x in pl if x["seleccionado"]]
            if not pend:
                print("Todo ya está instalado.")
            elif a.si or input(f"¿Instalar {len(pend)} programas? (s/N) ").strip().lower() == "s":
                instalar_lote(pend, wg)
    elif a.cmd == "verificar":
        faltan = verificar_catalogo(wg)
        print("\nTodos los IDs existen." if not faltan else f"\nNo encontrados ({len(faltan)}): {', '.join(faltan)}")
    elif a.cmd == "actualizar":
        cod, out = wg.actualizar_todo()
        print(out[-2000:])
    elif a.cmd == "winget":
        print("winget disponible." if wg.disponible() else
              ("winget instalado." if wg.instalar_winget() else "winget NO disponible: instalá 'Instalador de aplicaciones' desde Microsoft Store."))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
