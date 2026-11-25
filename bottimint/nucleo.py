#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nucleo.py - Motor de optimización por niveles (sin interfaz gráfica).

Niveles (acumulativos: cada uno incluye al anterior):
  basico   -> Limpieza general (archivos temporales, cachés, papelera, DNS).
  profundo -> + apps preinstaladas, publicidad/sugerencias, telemetría programada, inicio, WinSxS.
  extremo  -> + servicios, procesos en segundo plano, efectos visuales, energía, ajustes gaming.

Garantías:
  * ANTES de cualquier cambio se crea un punto de restauración y se VERIFICA que exista.
    Si no se puede crear, no se toca nada.
  * Cada cambio del registro / servicios / tareas / inicio / energía guarda su estado previo en
    C:\\ProgramData\\BottiMint\\sesiones\\<fecha>\\manifest.json y se puede deshacer con `restaurar`.
  * Lo único NO reversible por la herramienta: borrar temporales/papelera (no hay nada que restaurar)
    y desinstalar apps (se intenta re-registrarlas; si no, se reinstalan desde Microsoft Store).
  * No se desactivan Windows Defender, Firewall, Windows Update, red, audio ni servicios críticos.

Uso (consola, como administrador):
    python -m bottimint optimizar niveles
    python -m bottimint optimizar plan --nivel extremo
    python -m bottimint optimizar aplicar --nivel profundo [--sin id1,id2] [--solo id1,id2] [--si]
    python -m bottimint optimizar sesiones
    python -m bottimint optimizar restaurar [--sesion AAAAMMDD_HHMMSS]
    python -m bottimint optimizar restauracion-sistema      (abre "Restaurar sistema" de Windows)

"""
import argparse
import contextlib
import ctypes
import datetime
import fnmatch
import json
import os
import platform
import re
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple

from . import confiables
from . import limpieza as base
from .i18n import tr

try:
    import winreg  # type: ignore
except ImportError:
    winreg = None

REG_SZ, REG_DWORD = 1, 4
ORDEN = ["basico", "profundo", "extremo"]
SVC_KEY = "SYSTEM\\CurrentControlSet\\Services\\"

# ====================================================================
# Descripción de los niveles
# ====================================================================
NIVELES: Dict[str, dict] = {
    "basico": {
        "titulo": "Básico - Limpieza general",
        "para_quien": "Cualquier PC lenta, con poco espacio o que hace tiempo no se limpia.",
        "que_hace": [
            "Borra archivos temporales de Windows y del usuario.",
            "Vacía cachés de navegadores, miniaturas, informes de error y descargas de Windows Update ya instaladas.",
            "Vacía la papelera y la caché DNS.",
        ],
        "consecuencias": [
            "La primera vez que se abren las webs cargan un poco más lento (se rearma la caché).",
            "Lo que está en la papelera se pierde para siempre.",
            "No se desactiva ningún servicio ni programa: la PC funciona igual que antes, con más espacio.",
        ],
        "reversibilidad": "No hay nada que restaurar: son archivos descartables que Windows vuelve a crear solo.",
    },
    "profundo": {
        "titulo": "Profundo - Limpieza + eliminar lo que sobra",
        "para_quien": "PC con mucho 'software basura' de fábrica, publicidad en el menú Inicio o que tarda en arrancar.",
        "que_hace": [
            "Todo lo del nivel Básico.",
            "Desinstala apps preinstaladas innecesarias (Solitario, Noticias, Clima, Clipchamp, Teams personal, juegos de relleno, etc.).",
            "Limpia el menú Inicio: quita apps de relleno (OneNote, To Do, Mapas, Paint 3D, LinkedIn, Copilot...) y la app de Xbox con la Barra de juegos, y desancla todo lo que viene anclado en Inicio.",
            "Apaga sugerencias, publicidad y recomendaciones del menú Inicio y la pantalla de bloqueo.",
            "Desactiva tareas programadas de telemetría de Microsoft.",
            "Deshabilita programas de inicio conocidos que no hacen falta (Spotify, Teams, Skype, actualizadores de Adobe/Java...).",
            "Limpia componentes viejos de Windows (WinSxS).",
        ],
        "consecuencias": [
            "Las apps desinstaladas desaparecen; si las quiere de nuevo hay que bajarlas de Microsoft Store.",
            "Los programas que se deshabilitaron del inicio ya no se abren solos (se abren a mano cuando se necesitan).",
            "Dejan de aparecer apps sugeridas y publicidad en Inicio.",
        ],
        "reversibilidad": "Registro, tareas e inicio se restauran con un clic. Las apps se intentan recuperar; si no, Microsoft Store.",
    },
    "extremo": {
        "titulo": "Extremo / Gaming - Mínimo de procesos",
        "para_quien": "PC de juegos o equipos con poca RAM / disco mecánico donde se busca la mayor reducción posible.",
        "que_hace": [
            "Todo lo del nivel Profundo.",
            "Desactiva servicios innecesarios (telemetría, fax, mapas, modo demo, seguimiento de vínculos...).",
            "Opcionales según el equipo: SysMain, búsqueda de Windows, cola de impresión, Bluetooth, servicios Xbox.",
            "Impide que las apps de la Tienda corran en segundo plano y quita Widgets/Noticias.",
            "Modo Juego activo y grabación en segundo plano (Game DVR) desactivada.",
            "Quita todas las animaciones de Windows y deja el escritorio en negro sólido (sin imagen de fondo), conservando el suavizado de letras (ClearType) para que el texto se vea nítido.",
            "Plan de energía de alto rendimiento (solo PC de escritorio por defecto).",
        ],
        "consecuencias": [
            "Sin cola de impresión no se puede imprimir; sin Bluetooth no andan auriculares/mouse inalámbricos; sin servicios Xbox no andan Game Pass ni juegos de la Tienda de Microsoft.",
            "Sin la búsqueda de Windows, buscar archivos desde el Explorador/Inicio es más lento.",
            "Algunas apps (Correo, Alarmas) no actualizan ni notifican en segundo plano.",
            "Las ventanas ya no tienen animaciones ni transparencias, y el escritorio queda en negro sin imagen de fondo.",
            "Si querés volver a usar algo de lo anterior, se restaura en un clic desde la herramienta.",
        ],
        "reversibilidad": "Todo se deshace con 'restaurar' (guarda el estado original de cada servicio y ajuste) y además existe el punto de restauración de Windows.",
    },
}

# Nombre de la acción "Desanclar de Inicio" en los idiomas más comunes (el shell la muestra traducida)
_PS_DESANCLAR_INICIO = r"""
$pat = '^(Unpin from Start|Desanclar de Inicio|Quitar de Inicio|Desafixar do In.cio|D.tacher de D.marrer|Von Start l.sen|Rimuovi da Start)$'
$n = 0
try {
  $items = (New-Object -ComObject Shell.Application).NameSpace('shell:::{4234d49b-0245-4df3-b780-3893943456e1}').Items()
  foreach ($it in $items) {
    foreach ($v in $it.Verbs()) {
      if (($v.Name -replace '&','') -match $pat) { $v.DoIt(); $n++; break }
    }
  }
} catch { }
Write-Output ('DESANCLADOS=' + $n)
"""

# Apps que NUNCA se tocan (defensa extra, aunque no estén en las listas de borrado)
APPS_PROTEGIDAS = ("Microsoft.WindowsStore", "Microsoft.WindowsCalculator", "Microsoft.Windows.Photos",
                   "Microsoft.WindowsNotepad", "Microsoft.WindowsTerminal", "Microsoft.SecHealthUI",
                   "Microsoft.MicrosoftEdge*", "Microsoft.Windows.ShellExperienceHost", "Microsoft.DesktopAppInstaller",
                   "Microsoft.VCLibs*", "Microsoft.NET*", "Microsoft.UI.Xaml*", "Microsoft.ZuneMusic",
                   "Microsoft.Paint", "Microsoft.ScreenSketch", "Microsoft.WindowsAlarms", "*WebExperience*")


# ====================================================================
# Entorno (todo lo que toca Windows pasa por acá; en pruebas se reemplaza)
# ====================================================================
class Entorno:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or confiables.carpeta_de_datos()
        self._hives = {}
        if winreg:
            self._hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}

    def is_admin(self) -> bool:
        return base.is_admin()

    def pausa(self, s: float) -> None:
        time.sleep(s)

    # --- registro ---
    def reg_get(self, hive: str, path: str, name: str):
        try:
            with winreg.OpenKey(self._hives[hive], path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                v, t = winreg.QueryValueEx(k, name)
                return True, v, t
        except (OSError, AttributeError):
            return False, None, None

    def reg_set(self, hive: str, path: str, name: str, tipo: int, valor) -> None:
        with winreg.CreateKeyEx(self._hives[hive], path, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
            winreg.SetValueEx(k, name, 0, tipo, valor)

    def reg_del(self, hive: str, path: str, name: str) -> None:
        try:
            with winreg.OpenKey(self._hives[hive], path, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
                winreg.DeleteValue(k, name)
        except OSError:
            pass

    # --- ajustes de la interfaz (SystemParametersInfo) y fondo de escritorio ---
    def spi_get(self, accion: int) -> Optional[int]:
        """Lee un ajuste booleano/numérico de la interfaz; None si no se puede (o no es Windows)."""
        if not base.IS_WIN:
            return None
        v = ctypes.c_uint(0)
        try:
            ok = ctypes.windll.user32.SystemParametersInfoW(accion, 0, ctypes.byref(v), 0)  # type: ignore[attr-defined]
        except (OSError, AttributeError):
            return None
        return int(v.value) if ok else None

    def spi_set(self, accion: int, valor: int, via: str = "pv") -> bool:
        """Cambia un ajuste y lo guarda en el perfil (SPIF_UPDATEINIFILE | SPIF_SENDCHANGE).
        `via`: 'pv' = el valor va en pvParam (la mayoría); 'ui' = va en uiParam (suavizado de fuentes)."""
        if not base.IS_WIN:
            return False
        try:
            f = ctypes.windll.user32.SystemParametersInfoW  # type: ignore[attr-defined]
            ok = f(accion, valor, None, 0x3) if via == "ui" else f(accion, 0, ctypes.c_void_p(valor), 0x3)
        except (OSError, AttributeError):
            return False
        return bool(ok)

    def fondo_aplicar(self, ruta: str, color: Tuple[int, int, int]) -> None:
        """Pone el color de escritorio y el fondo (ruta vacía = sin imagen) y lo refresca al instante."""
        if not base.IS_WIN:
            return
        r, g, b = color
        try:
            cols = (ctypes.c_uint32 * 1)(r | (g << 8) | (b << 16))
            ctypes.windll.user32.SetSysColors(1, (ctypes.c_int * 1)(1), cols)  # type: ignore[attr-defined]  # COLOR_BACKGROUND
            ctypes.windll.user32.SystemParametersInfoW(0x14, 0, ruta, 0x3)  # type: ignore[attr-defined]  # SPI_SETDESKWALLPAPER
        except (OSError, AttributeError):
            pass

    # --- comandos ---
    def run(self, cmd: List[str], timeout: Optional[int] = None) -> Tuple[int, str]:
        return base.ejecutar(cmd, timeout)

    def ps(self, script: str, timeout: int = 300) -> Tuple[int, str]:
        return self.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout)

    # --- servicios ---
    def servicio_existe(self, nombre: str) -> bool:
        return self.reg_get("HKLM", SVC_KEY + nombre, "Start")[0]

    def servicio_corriendo(self, nombre: str) -> bool:
        return "RUNNING" in self.run(["sc", "query", nombre])[1]

    # --- tareas programadas ---
    def tarea_estado(self, ruta: str, nombre: str) -> str:
        cod, out = self.ps(f"try {{ (Get-ScheduledTask -TaskPath {ps_str(ruta)} -TaskName {ps_str(nombre)} -ErrorAction Stop).State }} catch {{ 'NOEXISTE' }}")
        return out.strip().splitlines()[-1].strip() if out.strip() else "NOEXISTE"

    def tareas_estado(self, tareas: List[Tuple[str, str]]) -> Dict[Tuple[str, str], str]:
        """Estado de varias tareas con UN solo PowerShell (antes se lanzaba uno por tarea, ~1 s cada uno).
        Se listan todas y se filtra en Python, así no se interpola nada en el script. Si el listado falla o no se
        puede leer, se consulta tarea por tarea como antes."""
        cod, out = self.ps("Get-ScheduledTask | ForEach-Object { [pscustomobject]@{ p = $_.TaskPath; n = $_.TaskName; "
                           "s = [string]$_.State } } | ConvertTo-Json -Compress", 120)
        try:
            datos = json.loads(out)
            datos = [datos] if isinstance(datos, dict) else list(datos)
            existentes = {(str(d["p"]).lower(), str(d["n"]).lower()): str(d["s"]) for d in datos}
        except (ValueError, TypeError, KeyError):
            return {(r, n): self.tarea_estado(r, n) for r, n in tareas}
        return {(r, n): existentes.get((r.lower(), n.lower()), "NOEXISTE") for r, n in tareas}

    @contextlib.contextmanager
    def lecturas_en_cache(self):
        """Dentro del bloque, listar_appx() consulta a Windows una sola vez (varios cambios piden la misma lista).
        Solo para consultas en solo lectura, como plan(): al aplicar cambios la lista deja de ser válida."""
        if "listar_appx" in self.__dict__:  # ya hay una caché activa (uso anidado)
            yield
            return
        original, memo = self.listar_appx, []

        def con_cache() -> List[dict]:
            if not memo:
                memo.append(original())
            return list(memo[0])
        self.listar_appx = con_cache
        try:
            yield
        finally:
            del self.listar_appx

    def tarea_set(self, ruta: str, nombre: str, habilitar: bool) -> bool:
        cmd = "Enable-ScheduledTask" if habilitar else "Disable-ScheduledTask"
        return self.ps(f"{cmd} -TaskPath {ps_str(ruta)} -TaskName {ps_str(nombre)} | Out-Null")[0] == 0

    # --- apps de la Tienda ---
    def listar_appx(self) -> List[dict]:
        cod, out = self.ps("Get-AppxPackage | Select-Object Name,PackageFullName,InstallLocation | ConvertTo-Json -Compress", 180)
        try:
            datos = json.loads(out)
        except ValueError:
            return []
        return [datos] if isinstance(datos, dict) else datos

    def quitar_appx(self, full: str) -> bool:
        return _RE_APPX.match(full or "") is not None and self.ps(f"Remove-AppxPackage -Package {ps_str(full)}", 180)[0] == 0

    def desanclar_inicio(self) -> int:
        """Quita todos los anclados (mosaicos) del menú Inicio del usuario actual con la acción 'Desanclar de Inicio'
        de cada app. Windows 10 y 11. Devuelve cuántos se quitaron (el nombre de la acción depende del idioma)."""
        cod, out = self.ps(_PS_DESANCLAR_INICIO, 300)
        m = re.search(r"DESANCLADOS=(\d+)", out or "")
        return int(m.group(1)) if m else 0

    def onedrive_instalado(self) -> bool:
        """OneDrive es un programa de escritorio (no una app de la Tienda): se busca su ejecutable."""
        rutas = [os.path.join(raiz, *sub) for raiz, sub in
                 ((confiables.carpeta("localappdata"), ("Microsoft", "OneDrive", "OneDrive.exe")),
                  (confiables.carpeta("programfiles"), ("Microsoft OneDrive", "OneDrive.exe")),
                  (confiables.carpeta("programfilesx86"), ("Microsoft OneDrive", "OneDrive.exe"))) if raiz]
        return any(os.path.isfile(r) for r in rutas)

    def onedrive_setup(self) -> Optional[str]:
        """Instalador/desinstalador que trae Windows (queda en el sistema aunque se desinstale OneDrive)."""
        raiz = confiables.windows_dir()
        for sub in ("SysWOW64", "System32"):
            r = os.path.join(raiz, sub, "OneDriveSetup.exe")
            if raiz and os.path.isfile(r):
                return r
        return None

    def registrar_appx(self, ubicacion: str) -> bool:
        return _loc_appx_valida(ubicacion) and self.ps(f"Add-AppxPackage -DisableDevelopmentMode -Register {ps_str(ubicacion + chr(92) + 'AppxManifest.xml')}", 180)[0] == 0

    # --- inicio ---
    def listar_inicio(self):
        return base.listar_inicio()

    def set_inicio(self, entrada, habilitar: bool) -> None:
        base.cambiar_inicio(entrada, habilitar)

    # --- detección del equipo ---
    def detectar_equipo(self) -> dict:
        eq = {"media": None, "bateria": False, "impresoras": 0, "ram_gb": None, "windows": platform.version()}
        script = ("$d = try { (Get-Partition -DriveLetter ($env:SystemDrive[0]) | Get-Disk).Number } catch { $null };"
                  "$m = if ($d -ne $null) { (Get-PhysicalDisk | Where-Object { $_.DeviceId -eq \"$d\" } | Select-Object -First 1).MediaType } else { $null };"
                  "[pscustomobject]@{ media=\"$m\"; bateria=(@(Get-CimInstance Win32_Battery).Count);"
                  "impresoras=(@(Get-Printer | Where-Object { $_.Name -notmatch 'PDF|XPS|OneNote|Fax' }).Count);"
                  "ram=[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1) } | ConvertTo-Json -Compress")
        cod, out = self.ps(script, 60)
        try:
            d = json.loads(out)
            eq.update(media=d.get("media") or None, bateria=bool(d.get("bateria")),
                      impresoras=int(d.get("impresoras") or 0), ram_gb=d.get("ram"))
        except (ValueError, AttributeError):
            pass
        return eq



# ====================================================================
# Seguridad: validación de lo que viene de un manifiesto (puede estar manipulado)
# ====================================================================
_RE_NOMBRE = re.compile(r"^[A-Za-z0-9 ._\-]{1,128}$")          # servicios, tareas
_RE_APPX = re.compile(r"^[A-Za-z0-9._\-]{1,200}$")              # PackageFullName
_RE_GUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")


def ps_str(valor: str) -> str:
    """Literal de PowerShell entre comillas simples, con las comillas internas duplicadas (anti-inyección)."""
    return "'" + str(valor).replace("'", "''") + "'"


def _loc_appx_valida(loc: str) -> bool:
    """Una app de la Tienda solo se registra desde ...\\WindowsApps\\<paquete> (nada de rutas arbitrarias)."""
    if not loc or any(c in loc for c in "\"'`$;&|\n\r<>"):
        return False
    pf = confiables.carpeta("programfiles") or r"C:\Program Files"
    raiz = os.path.normcase(os.path.join(pf, "WindowsApps")) + os.sep
    return os.path.normcase(os.path.abspath(loc)).startswith(raiz)

# ====================================================================
# Tipos de cambio
# ====================================================================
class Cambio:
    reversible = True

    def __init__(self, id: str, nivel: str, grupo: str, titulo: str, que_hace: str, consecuencia: str,
                 riesgo: str = "bajo", defecto=True):
        self.id, self.nivel, self.grupo, self.titulo = id, nivel, grupo, titulo
        self.que_hace, self.consecuencia, self.riesgo = que_hace, consecuencia, riesgo
        self._defecto = defecto

    def defecto(self, equipo: dict) -> bool:
        return self._defecto(equipo) if callable(self._defecto) else bool(self._defecto)

    def aplica(self, env: Entorno) -> Tuple[bool, str]:
        return True, ""

    def aplicar(self, env: Entorno, emitir: Callable[[str], None], estado: dict) -> str:
        raise NotImplementedError

    def revertir(self, env: Entorno, estado: dict) -> str:
        return "Nada para restaurar."


class CambioLimpieza(Cambio):
    """Envuelve una tarea de limpieza de limpieza.py. No es reversible (son archivos descartables)."""
    reversible = False

    def __init__(self, clave: str, nivel: str, que_hace: str, consecuencia: str, riesgo="bajo", defecto=True,
                 titulo: Optional[str] = None, grupo: str = "Limpieza"):
        self.tarea = base.TAREAS_POR_CLAVE[clave]
        super().__init__("limp_" + clave, nivel, grupo, titulo or self.tarea.titulo, que_hace, consecuencia, riesgo, defecto)

    def aplicar(self, env, emitir, estado):
        t = self.tarea
        liberado, msg = 0, ""
        if t.antes:
            t.antes(None)
        try:
            if t.rutas:
                lib, omit = base.limpiar_rutas(base.expandir(t.rutas()))
                liberado += lib
                if omit:
                    msg = f" ({omit} archivos en uso omitidos)"
            if t.limpieza_extra:
                liberado += t.limpieza_extra(None)
            if t.accion:
                msg = " " + t.accion(None)
        finally:
            if t.despues:
                t.despues(None)
        estado["liberado"] = liberado
        return (f"{base.fmt_bytes(liberado)} liberados" if t.es_limpieza and not t.accion else "listo") + msg


class CambioRegistro(Cambio):
    def __init__(self, id, nivel, grupo, titulo, que_hace, consecuencia, valores, riesgo="bajo", defecto=True):
        super().__init__(id, nivel, grupo, titulo, que_hace, consecuencia, riesgo, defecto)
        self.valores = valores  # [(hive, path, name, tipo, valor)]

    def aplicar(self, env, emitir, estado):
        previos = estado.setdefault("valores", [])
        for hive, path, name, tipo, valor in self.valores:
            ex, v, t = env.reg_get(hive, path, name)
            previos.append({"hive": hive, "path": path, "name": name, "existe": ex,
                            "valor": v if isinstance(v, (int, str, type(None))) else None, "tipo": t})
            env.reg_set(hive, path, name, tipo, valor)
        return f"{len(self.valores)} ajustes aplicados"

    def revertir(self, env, estado):
        n, permitidos = 0, {(h, pa.lower(), na.lower()) for h, pa, na, _t, _v in self.valores}
        for p in reversed(estado.get("valores", [])):
            if (p.get("hive"), str(p.get("path", "")).lower(), str(p.get("name", "")).lower()) not in permitidos:
                continue  # el manifiesto pide tocar algo que este cambio nunca toca: se ignora
            if p["existe"] and p["valor"] is not None:
                env.reg_set(p["hive"], p["path"], p["name"], p["tipo"], p["valor"])
            elif not p["existe"]:
                env.reg_del(p["hive"], p["path"], p["name"])
            n += 1
        return f"{n} ajustes restaurados"


# Ajustes de interfaz que se cambian con SystemParametersInfo (se aplican al instante y quedan guardados).
# (clave, SPI_GET, SPI_SET, vía del valor, valor deseado). Los dos últimos NO apagan nada: dejan ACTIVO el suavizado
# de letras (ClearType) para que, sin animaciones, el texto siga viéndose nítido.
SPI_AJUSTES = [
    ("efectos_ui", 0x103E, 0x103F, "pv", 0),
    ("menu_anim", 0x1002, 0x1003, "pv", 0),
    ("menu_fade", 0x1012, 0x1013, "pv", 0),
    ("combo_anim", 0x1004, 0x1005, "pv", 0),
    ("lista_suave", 0x1006, 0x1007, "pv", 0),
    ("seleccion_fade", 0x1014, 0x1015, "pv", 0),
    ("tooltip_anim", 0x1016, 0x1017, "pv", 0),
    ("tooltip_fade", 0x1018, 0x1019, "pv", 0),
    ("sombra_cursor", 0x101A, 0x101B, "pv", 0),
    ("anim_cliente", 0x1042, 0x1043, "pv", 0),
    ("suavizado_letras", 0x004A, 0x004B, "ui", 1),
    ("cleartype", 0x200A, 0x200B, "pv", 2),
]
_SPI_POR_CLAVE = {a[0]: a for a in SPI_AJUSTES}
_RE_RUTA_FONDO = re.compile(r"^(?:[A-Za-z]:\\[^<>\"|?*\x00-\x1f]{0,240})?$")  # "" (sin imagen) o ruta local de unidad
_RE_COLOR = re.compile(r"^(\d{1,3}) (\d{1,3}) (\d{1,3})$")


class CambioAnimaciones(Cambio):
    """Quita animaciones y desvanecimientos de Windows y deja activo el suavizado de letras."""

    def aplica(self, env):
        ok = env.spi_get(0x103E) is not None
        return ok, "" if ok else "no se pueden leer los efectos de la interfaz en este equipo"

    def aplicar(self, env, emitir, estado):
        previos = estado.setdefault("spi", [])
        hechos = 0
        for clave, get, set_, via, deseado in SPI_AJUSTES:
            v = env.spi_get(get)
            if v is None:
                continue
            previos.append({"clave": clave, "valor": int(v)})
            if v != deseado and env.spi_set(set_, deseado, via):
                hechos += 1
        return f"{hechos} efectos ajustados"

    def revertir(self, env, estado):
        n = 0
        for p in reversed(estado.get("spi", [])):
            a = _SPI_POR_CLAVE.get(p.get("clave"))
            if not a or p.get("valor") not in (0, 1, 2):
                continue  # el manifiesto pide algo que este cambio nunca toca: se ignora
            if env.spi_set(a[2], int(p["valor"]), a[3]):
                n += 1
        return f"{n} efectos restaurados"


class CambioFondoNegro(CambioRegistro):
    """Escritorio en negro sólido, sin imagen de fondo. Reversible: devuelve la imagen y el color originales."""

    def aplicar(self, env, emitir, estado):
        super().aplicar(env, emitir, estado)
        env.fondo_aplicar("", (0, 0, 0))
        return "Fondo de escritorio en negro sólido"

    def revertir(self, env, estado):
        r = super().revertir(env, estado)
        ex, ruta, _ = env.reg_get("HKCU", r"Control Panel\Desktop", "WallPaper")
        ruta = ruta if ex and isinstance(ruta, str) and _RE_RUTA_FONDO.match(ruta) else ""
        ex2, col, _ = env.reg_get("HKCU", r"Control Panel\Colors", "Background")
        m = _RE_COLOR.match(col) if ex2 and isinstance(col, str) else None
        color = tuple(min(int(x), 255) for x in m.groups()) if m else (0, 0, 0)
        env.fondo_aplicar(ruta, color)  # type: ignore[arg-type]
        return r + " (fondo original restaurado)"


class CambioServicios(Cambio):
    def __init__(self, id, nivel, grupo, titulo, que_hace, consecuencia, servicios, modo="disabled", riesgo="medio", defecto=True):
        super().__init__(id, nivel, grupo, titulo, que_hace, consecuencia, riesgo, defecto)
        self.servicios, self.modo = servicios, modo

    def aplica(self, env):
        presentes = [s for s in self.servicios if env.servicio_existe(s)]
        return bool(presentes), (f"servicios: {', '.join(presentes)}" if presentes else "no hay servicios para ajustar")

    def aplicar(self, env, emitir, estado):
        previos = estado.setdefault("servicios", [])
        destino = 4 if self.modo == "disabled" else 3
        hechos = 0
        for s in self.servicios:
            ex, start, _ = env.reg_get("HKLM", SVC_KEY + s, "Start")
            if not ex:
                continue
            corriendo = env.servicio_corriendo(s)
            reg = {"nombre": s, "start": start, "corriendo": corriendo}
            try:
                env.reg_set("HKLM", SVC_KEY + s, "Start", REG_DWORD, destino)
                previos.append(reg)
                hechos += 1
                if corriendo and self.modo == "disabled":
                    env.run(["sc", "stop", s], 30)
            except OSError as ex_:
                emitir(f"   no se pudo modificar el servicio {s}: {ex_}")
        return f"{hechos} servicios ajustados"

    def revertir(self, env, estado):
        n = 0
        for r in reversed(estado.get("servicios", [])):
            if r.get("nombre") not in self.servicios or not _RE_NOMBRE.match(r["nombre"]) or r.get("start") not in (0, 1, 2, 3, 4):
                continue
            env.reg_set("HKLM", SVC_KEY + r["nombre"], "Start", REG_DWORD, r["start"])
            if r["corriendo"] and r["start"] != 4:
                env.run(["sc", "start", r["nombre"]], 30)
            n += 1
        return f"{n} servicios restaurados"


class CambioTareas(Cambio):
    def __init__(self, id, nivel, grupo, titulo, que_hace, consecuencia, tareas, riesgo="bajo", defecto=True):
        super().__init__(id, nivel, grupo, titulo, que_hace, consecuencia, riesgo, defecto)
        self.tareas = tareas  # [(ruta, nombre)]

    def aplica(self, env):
        estados = env.tareas_estado(self.tareas)
        n = sum(1 for k in self.tareas if estados[k] not in ("NOEXISTE", "Disabled"))
        return n > 0, f"{n} tareas activas"

    def aplicar(self, env, emitir, estado):
        previas = estado.setdefault("tareas", [])
        estados = env.tareas_estado(self.tareas)
        for ruta, nombre in self.tareas:
            if estados[(ruta, nombre)] in ("NOEXISTE", "Disabled"):
                continue
            if env.tarea_set(ruta, nombre, False):
                previas.append({"ruta": ruta, "nombre": nombre})
        return f"{len(previas)} tareas deshabilitadas"

    def revertir(self, env, estado):
        n = 0
        for t in reversed(estado.get("tareas", [])):
            if (t.get("ruta"), t.get("nombre")) not in set(self.tareas):
                continue
            env.tarea_set(t["ruta"], t["nombre"], True)
            n += 1
        return f"{n} tareas habilitadas"


class CambioApps(Cambio):
    reversible = False  # se intenta, pero no se puede garantizar

    def __init__(self, id, nivel, grupo, titulo, que_hace, consecuencia, patrones, riesgo="bajo", defecto=True):
        super().__init__(id, nivel, grupo, titulo, que_hace, consecuencia, riesgo, defecto)
        self.patrones = patrones

    def _coinciden(self, env):
        out = []
        for p in env.listar_appx():
            nombre = p.get("Name", "")
            if any(fnmatch.fnmatch(nombre.lower(), pat.lower()) for pat in self.patrones) and \
               not any(fnmatch.fnmatch(nombre.lower(), prot.lower()) for prot in APPS_PROTEGIDAS):
                out.append(p)
        return out

    def aplica(self, env):
        c = self._coinciden(env)
        return bool(c), (f"{len(c)} apps: " + ", ".join(sorted({p['Name'] for p in c}))) if c else "no hay apps de la lista"

    def aplicar(self, env, emitir, estado):
        quitadas = estado.setdefault("apps", [])
        fallos = []
        for p in self._coinciden(env):
            if env.quitar_appx(p["PackageFullName"]):
                quitadas.append({"Name": p["Name"], "full": p["PackageFullName"], "loc": p.get("InstallLocation")})
            else:
                fallos.append(p["Name"])
        if fallos and not quitadas:
            raise RuntimeError("Windows no permitió quitar: " + ", ".join(sorted(set(fallos))))
        extra = ("; no se pudieron quitar: " + ", ".join(sorted(set(fallos)))) if fallos else ""
        return f"{len(quitadas)} apps desinstaladas{extra}"

    def revertir(self, env, estado):
        ok, manual = 0, []
        for a in estado.get("apps", []):
            if not _RE_APPX.match(str(a.get("Name", ""))):
                continue
            if a.get("loc") and env.registrar_appx(a["loc"]):
                ok += 1
            else:
                manual.append(a["Name"])
        return f"{ok} apps recuperadas" + (f"; reinstalar desde Microsoft Store: {', '.join(manual)}" if manual else "")


class CambioOneDrive(CambioRegistro):
    """Desinstala OneDrive con el desinstalador de Windows y evita que vuelva. No borra la carpeta ni la nube."""
    _CARPETAS = ("Personal", "Desktop", "My Pictures")

    def aplica(self, env):
        if not env.onedrive_instalado():
            return False, "OneDrive no está instalado"
        if not env.onedrive_setup():
            return False, "no se encontró el desinstalador de OneDrive de Windows"
        for nombre in self._CARPETAS:
            ex, v, _t = env.reg_get("HKCU", W + r"\Explorer\User Shell Folders", nombre)
            if ex and isinstance(v, str) and "onedrive" in v.lower():
                return False, "tu Escritorio/Documentos/Imágenes se guardan en OneDrive: no se desinstala"
        return True, ""

    def aplicar(self, env, emitir, estado):
        setup = env.onedrive_setup()
        if not setup:
            raise RuntimeError("no se encontró el desinstalador de OneDrive")
        env.run(["taskkill", "/f", "/im", "OneDrive.exe"], 30)
        env.pausa(2)
        cod, _out = env.run([setup, "/uninstall"], 300)
        if cod != 0:
            raise RuntimeError(f"el desinstalador de OneDrive falló (código {cod})")
        estado["onedrive"] = True
        super().aplicar(env, emitir, estado)
        return "OneDrive desinstalado"

    def revertir(self, env, estado):
        r = super().revertir(env, estado)  # primero se quita la política que lo bloquea
        if estado.get("onedrive"):
            setup = env.onedrive_setup()  # se usa el de Windows, nunca una ruta del manifiesto
            if setup:
                env.run([setup], 600)
                return r + "; OneDrive reinstalado"
            return r + "; reinstalar OneDrive desde microsoft.com/onedrive"
        return r


class CambioPinesInicio(Cambio):
    """Deja el menú Inicio sin anclados. No se puede restaurar el orden anterior (el usuario ancla lo que quiera)."""
    reversible = False

    def aplicar(self, env, emitir, estado):
        n = env.desanclar_inicio()
        return f"{n} elementos desanclados"

    def revertir(self, env, estado):
        return "Nada para restaurar: volvé a anclar a mano lo que quieras."


class CambioInicio(Cambio):
    def __init__(self, id, nivel, grupo, titulo, que_hace, consecuencia, patrones, riesgo="bajo", defecto=True):
        super().__init__(id, nivel, grupo, titulo, que_hace, consecuencia, riesgo, defecto)
        self.patrones = [p.lower() for p in patrones]

    def _coinciden(self, env):
        return [e for e in env.listar_inicio() if e.habilitado and
                any(p in e.nombre.lower() or p in e.comando.lower() for p in self.patrones)]

    def aplica(self, env):
        c = self._coinciden(env)
        return bool(c), (", ".join(e.nombre for e in c) if c else "ninguno de la lista está activo")

    def aplicar(self, env, emitir, estado):
        hechos = estado.setdefault("inicio", [])
        for e in self._coinciden(env):
            try:
                env.set_inicio(e, False)
                hechos.append({"nombre": e.nombre, "origen": e.origen})
            except OSError as ex:
                emitir(f"   no se pudo deshabilitar {e.nombre}: {ex}")
        return f"{len(hechos)} programas de inicio deshabilitados"

    def revertir(self, env, estado):
        n = 0
        actuales = env.listar_inicio()
        for h in reversed(estado.get("inicio", [])):
            for e in actuales:
                if e.nombre == h["nombre"] and e.origen == h["origen"]:
                    env.set_inicio(e, True)
                    n += 1
        return f"{n} programas de inicio habilitados"


class CambioEnergia(Cambio):
    def aplicar(self, env, emitir, estado):
        cod, out = env.run(["powercfg", "/getactivescheme"])
        m = re.search(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", out)
        if m:
            estado["guid"] = m.group(0)
        env.run(["powercfg", "/setactive", "SCHEME_MIN"])
        return "Plan de energía: Alto rendimiento"

    def revertir(self, env, estado):
        if estado.get("guid") and _RE_GUID.match(str(estado["guid"])):
            env.run(["powercfg", "/setactive", estado["guid"]])
            return "Plan de energía original restaurado"
        return "No se había guardado el plan original; elegilo en Opciones de energía"


class CambioHibernacion(Cambio):
    def aplica(self, env):
        ex, v, _ = env.reg_get("HKLM", r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled")
        return bool(ex and v == 1), "hibernación activa" if ex and v == 1 else "ya está desactivada"

    def aplicar(self, env, emitir, estado):
        estado["estaba"] = True
        env.run(["powercfg", "/h", "off"])
        return "Hibernación desactivada"

    def revertir(self, env, estado):
        if estado.get("estaba"):
            env.run(["powercfg", "/h", "on"])
        return "Hibernación reactivada"


# ====================================================================
# Catálogo de cambios
# ====================================================================
W = r"Software\Microsoft\Windows\CurrentVersion"
CDM = W + r"\ContentDeliveryManager"


def _catalogo() -> List[Cambio]:
    c: List[Cambio] = []

    # ---------------- BÁSICO ----------------
    c += [
        CambioLimpieza("temp_usuario", "basico", "Archivos temporales del usuario actual (carpeta TEMP).",
                       "Un programa abierto puede perder un borrador temporal no guardado. Cerrar todo antes."),
        CambioLimpieza("temp_windows", "basico", "Archivos temporales de C:\\Windows\\Temp.", "Ninguna."),
        CambioLimpieza("navegadores", "basico", "Caché de Chrome, Edge, Brave y Firefox. No toca contraseñas ni historial.",
                       "Las webs cargan un poco más lento la primera vez. Cerrar los navegadores antes."),
        CambioLimpieza("inetcache", "basico", "Caché de Internet y miniaturas del Explorador.",
                       "Las miniaturas se regeneran al abrir carpetas con imágenes."),
        CambioLimpieza("errores", "basico", "Informes y volcados de error de Windows.",
                       "Se pierden registros de cuelgues pasados (solo sirven para diagnosticar)."),
        CambioLimpieza("windows_update", "basico", "Descargas de Windows Update ya instaladas.",
                       "Ninguna importante: Windows vuelve a bajar lo que necesite."),
        CambioLimpieza("delivery_opt", "basico", "Caché de Optimización de entrega.", "Ninguna."),
        CambioLimpieza("papelera", "basico", "Vacía la papelera de reciclaje.",
                       "Lo que está en la papelera se pierde definitivamente. Confirmá que no necesitás nada de ahí.", riesgo="medio"),
        CambioLimpieza("dns", "basico", "Vacía la caché DNS.", "Ninguna.", titulo="Vaciar caché DNS"),
    ]

    # ---------------- PROFUNDO ----------------
    c += [
        CambioApps("apps_bloat", "profundo", "Apps preinstaladas", "Desinstalar apps preinstaladas innecesarias",
                   "Quita Solitario, Noticias, Clima, Finanzas, Deportes, Obtener ayuda, Sugerencias, Office Hub, Feedback Hub, "
                   "Mixed Reality, 3D Viewer, Skype, People, Cortana, Clipchamp, Teams personal, Power Automate y juegos/promos "
                   "de terceros (Candy Crush, TikTok, Netflix, Spotify, Disney, Facebook, Instagram, Amazon...).",
                   "Las apps desaparecen del menú Inicio. Si las querés, se bajan de Microsoft Store.",
                   ["Microsoft.MicrosoftSolitaireCollection", "Microsoft.BingNews", "Microsoft.BingWeather", "Microsoft.BingFinance",
                    "Microsoft.BingSports", "Microsoft.GetHelp", "Microsoft.Getstarted", "Microsoft.MicrosoftOfficeHub",
                    "Microsoft.WindowsFeedbackHub", "Microsoft.MixedReality.Portal", "Microsoft.Microsoft3DViewer",
                    "Microsoft.Print3D", "Microsoft.SkypeApp", "Microsoft.OneConnect", "Microsoft.People",
                    "Microsoft.549981C3F5F10", "Clipchamp.Clipchamp", "MicrosoftTeams", "Microsoft.PowerAutomateDesktop",
                    "Microsoft.ZuneVideo", "*king.com*", "*CandyCrush*", "*TikTok*", "*Netflix*", "*SpotifyAB*", "*Disney*",
                    "*Facebook*", "*Instagram*", "*AmazonPrimeVideo*", "*Twitter*"], riesgo="bajo"),
        CambioApps("apps_opcionales", "profundo", "Apps preinstaladas", "Desinstalar Vincular con el móvil y Correo/Calendario",
                   "Quita 'Vincular con el móvil' (Phone Link) y las apps Correo y Calendario de Windows.",
                   "No se podrá usar Phone Link ni la app de Correo/Calendario. Si las usás, NO marcar.",
                   ["Microsoft.YourPhone", "microsoft.windowscommunicationsapps"], riesgo="medio", defecto=False),
        CambioApps("apps_inicio", "profundo", "Apps preinstaladas", "Limpiar el menú Inicio de apps de relleno",
                   "Quita OneNote, To Do, Mapas, Grabadora de voz, Paint 3D, LinkedIn, Copilot y Dev Home (y sus mosaicos del menú Inicio).",
                   "Desaparecen del menú Inicio. Si querés alguna, se baja de Microsoft Store. Calculadora, Fotos, Reloj, Edge y Store NO se tocan.",
                   ["Microsoft.Office.OneNote", "Microsoft.Todos", "Microsoft.WindowsMaps", "Microsoft.WindowsSoundRecorder",
                    "Microsoft.MSPaint", "*LinkedIn*", "Microsoft.Copilot", "Microsoft.Windows.Ai.Copilot.Provider",
                    "Microsoft.Windows.DevHome", "Microsoft.MicrosoftJournal"], riesgo="bajo"),
        CambioRegistro("reg_copilot", "profundo", "Apps preinstaladas", "Apagar Copilot y quitar su botón",
                       "Desactiva Copilot de Windows por política (todos los usuarios) y oculta su botón de la barra de tareas. "
                       "Complementa la desinstalación de la app Copilot, que a veces Windows vuelve a instalar.",
                       "Copilot deja de abrirse (también con Win+C) y su botón desaparece de la barra de tareas. Si lo usás, NO marcar.",
                       [("HKCU", r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", REG_DWORD, 1),
                        ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", REG_DWORD, 1),
                        ("HKCU", W + r"\Explorer\Advanced", "ShowCopilotButton", REG_DWORD, 0)]),
        CambioOneDrive("onedrive", "profundo", "Apps preinstaladas", "Desinstalar OneDrive",
                       "Cierra y desinstala OneDrive (no es una app de la Tienda, por eso las otras limpiezas no lo tocan) y evita que "
                       "vuelva a instalarse. No borra tu carpeta OneDrive ni lo que hay en la nube.",
                       "Dejás de sincronizar con la nube. Los archivos 'solo en línea' dejan de estar disponibles en esta PC (siguen en la nube). "
                       "Si usás OneDrive, NO marcar.",
                       [("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\OneDrive", "DisableFileSyncNGSC", REG_DWORD, 1)],
                       riesgo="medio", defecto=False),
        CambioApps("apps_xbox", "profundo", "Apps preinstaladas", "Quitar la app de Xbox y la Barra de juegos del menú Inicio",
                   "Desinstala la app Xbox y la Barra de juegos (Xbox Game Bar). No toca el inicio de sesión de Xbox que usan algunos juegos de la Tienda.",
                   "No funcionan la app de Xbox ni Win+G; Win+G puede mostrar un aviso pidiendo una app. Steam/Epic/Battle.net no se afectan. Si usás Game Pass, NO marcar.",
                   ["Microsoft.XboxApp", "Microsoft.GamingApp", "Microsoft.XboxGamingOverlay", "Microsoft.XboxGameOverlay",
                    "Microsoft.XboxSpeechToTextOverlay"], riesgo="medio"),
        CambioApps("apps_extra", "profundo", "Apps preinstaladas", "Desinstalar Cámara, Notas adhesivas y Outlook nuevo",
                   "Quita las apps Cámara, Notas adhesivas (Sticky Notes) y el nuevo Outlook para Windows.",
                   "No se podrá usar la cámara desde la app Cámara ni las notas adhesivas. Si las usás, NO marcar.",
                   ["Microsoft.WindowsCamera", "Microsoft.MicrosoftStickyNotes", "Microsoft.OutlookForWindows"],
                   riesgo="medio", defecto=False),
        CambioPinesInicio("inicio_pines", "profundo", "Menú Inicio", "Desanclar todo del menú Inicio",
                          "Quita todos los mosaicos y anclados del menú Inicio (Edge, Fotos, Tienda, Calculadora, etc.) para que quede vacío. "
                          "Después anclás solo lo que quieras.",
                          "El menú Inicio queda vacío. Las apps siguen instaladas y se encuentran en «Todas las aplicaciones» o buscando. "
                          "No se puede restaurar el orden anterior.",
                          riesgo="bajo"),
        CambioRegistro("reg_sugerencias", "profundo", "Publicidad y sugerencias", "Apagar publicidad y sugerencias de Windows",
                       "Desactiva el ID de publicidad, apps sugeridas, consejos, recomendaciones del menú Inicio y anuncios en el Explorador.",
                       "Dejan de aparecer apps sugeridas y publicidad en Inicio/bloqueo. Aplica al usuario actual.",
                       [("HKCU", W + r"\AdvertisingInfo", "Enabled", REG_DWORD, 0)] +
                       [("HKCU", CDM, n, REG_DWORD, 0) for n in
                        ("SubscribedContent-338388Enabled", "SubscribedContent-338389Enabled", "SubscribedContent-353694Enabled",
                         "SubscribedContent-353696Enabled", "SubscribedContent-338393Enabled", "SubscribedContent-310093Enabled",
                         "SystemPaneSuggestionsEnabled", "SoftLandingEnabled", "SilentInstalledAppsEnabled", "ContentDeliveryAllowed",
                         "OemPreInstalledAppsEnabled", "PreInstalledAppsEnabled", "RotatingLockScreenOverlayEnabled")] +
                       [("HKCU", W + r"\Explorer\Advanced", "ShowSyncProviderNotifications", REG_DWORD, 0),
                        ("HKCU", W + r"\Explorer\Advanced", "Start_IrisRecommendations", REG_DWORD, 0)]),
        CambioTareas("tareas_telemetria", "profundo", "Telemetría", "Desactivar tareas programadas de telemetría",
                     "Deshabilita tareas que recopilan y envían datos de uso (Compatibility Appraiser, CEIP, Feedback, etc.).",
                     "Microsoft recibe menos datos de uso. Sin efecto en el funcionamiento diario.",
                     [("\\Microsoft\\Windows\\Application Experience\\", "Microsoft Compatibility Appraiser"),
                      ("\\Microsoft\\Windows\\Application Experience\\", "ProgramDataUpdater"),
                      ("\\Microsoft\\Windows\\Customer Experience Improvement Program\\", "Consolidator"),
                      ("\\Microsoft\\Windows\\Customer Experience Improvement Program\\", "UsbCeip"),
                      ("\\Microsoft\\Windows\\Feedback\\Siuf\\", "DmClient"),
                      ("\\Microsoft\\Windows\\Feedback\\Siuf\\", "DmClientOnScenarioDownload"),
                      ("\\Microsoft\\Windows\\Windows Error Reporting\\", "QueueReporting"),
                      ("\\Microsoft\\Windows\\DiskDiagnostic\\", "Microsoft-Windows-DiskDiagnosticDataCollector")]),
        CambioInicio("inicio_conocidos", "profundo", "Programas de inicio", "Deshabilitar programas de inicio innecesarios",
                     "Deshabilita al arranque: OneDrive, Edge y Chrome (precarga), Spotify, Discord, Teams, Skype, OneNote, Phone Link, "
                     "Xbox, Copilot, actualizadores de Adobe/Java, CCleaner Monitor, iTunes Helper, Cortana. Deja lo básico: antivirus, audio, red y drivers.",
                     "Esos programas no se abren solos: se abren a mano cuando se necesitan (Edge y Chrome funcionan igual, solo dejan de precargarse). "
                     "Revisá si usás Discord/Spotify siempre.",
                     ["spotify", "discord", "teams", "skype", "adobe", "ccxprocess", "acrobat", "sunjavaupdate", "jusched",
                      "microsoftedgeautolaunch", "msedge", "googlechromeautolaunch", "onedrive", "ccleaner", "ituneshelper",
                      "cortana", "onenote", "yourphone", "phoneexperience", "xbox", "gamebar", "copilot"], riesgo="bajo"),
        CambioLimpieza("componentes", "profundo", "Elimina versiones viejas de componentes de Windows (WinSxS). Libera varios GB. Lento.",
                       "Ya no se pueden desinstalar actualizaciones antiguas. El proceso tarda varios minutos.", riesgo="bajo",
                       grupo="Mantenimiento"),
        CambioLimpieza("sfc", "profundo", "Verifica y repara archivos dañados de Windows (10-30 min).",
                       "Ninguna; solo tarda. Úsalo si la PC tiene errores o cuelgues.", defecto=False, grupo="Mantenimiento"),
        CambioLimpieza("dism", "profundo", "Repara la imagen de Windows (útil si SFC no pudo reparar).",
                       "Ninguna; puede tardar y necesita internet.", defecto=False, grupo="Mantenimiento"),
        CambioLimpieza("defrag", "profundo", "Desfragmenta si es disco mecánico; hace TRIM si es SSD.",
                       "En HDD puede tardar horas; la PC va más lenta mientras corre.", defecto=False, grupo="Mantenimiento"),
    ]

    # ---------------- EXTREMO ----------------
    c += [
        CambioRegistro("reg_telemetria", "extremo", "Telemetría", "Telemetría de Windows al mínimo",
                       "Pone la recolección de diagnóstico al mínimo permitido y apaga avisos de comentarios.",
                       "Microsoft recibe el mínimo de datos. En ediciones Home/Pro Windows mantiene un nivel básico obligatorio.",
                       [("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", REG_DWORD, 0),
                        ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "DoNotShowFeedbackNotifications", REG_DWORD, 1)]),
        CambioServicios("svc_telemetria", "extremo", "Servicios", "Servicios de telemetría y reportes",
                        "Deshabilita 'Experiencias del usuario y telemetría' (DiagTrack), enrutador push (dmwappushservice) y Informe de errores (WerSvc).",
                        "No se envían informes de errores a Microsoft. No afecta el uso diario.",
                        ["DiagTrack", "dmwappushservice", "WerSvc"], riesgo="bajo"),
        CambioServicios("svc_inutiles", "extremo", "Servicios", "Servicios que casi nadie usa",
                        "Deshabilita Fax, Mapas descargados, Modo demo de tienda, Uso compartido de Media Player, Seguimiento de vínculos "
                        "distribuidos y Programa Windows Insider.",
                        "No se puede enviar/recibir fax, ni usar mapas sin conexión, ni recibir builds Insider. Para casi todos, sin efecto.",
                        ["Fax", "MapsBroker", "RetailDemo", "WMPNetworkSvc", "TrkWks", "wisvc"], riesgo="bajo"),
        CambioServicios("svc_geoloc", "extremo", "Servicios", "Servicio de ubicación",
                        "Deshabilita el servicio de geolocalización.",
                        "Las apps de clima/mapas no detectan la ubicación solas.", ["lfsvc"], riesgo="bajo", defecto=False),
        CambioServicios("svc_entrega", "extremo", "Servicios", "Optimización de entrega en manual",
                        "Pasa a manual el servicio que comparte descargas de Windows con otras PCs de internet.",
                        "Windows Update sigue funcionando; solo deja de compartir ancho de banda.", ["DoSvc"], modo="manual", riesgo="bajo"),
        CambioServicios("svc_sysmain", "extremo", "Servicios (según equipo)", "SysMain (Superfetch)",
                        "Deshabilita la precarga de programas en RAM. Recomendado en SSD; en disco mecánico conviene dejarlo.",
                        "En disco mecánico las apps abren más lento. En SSD no se nota.", ["SysMain"], riesgo="medio",
                        defecto=lambda e: e.get("media") == "SSD"),
        CambioServicios("svc_busqueda", "extremo", "Servicios (según equipo)", "Búsqueda de Windows (indexación)",
                        "Deshabilita el indexador. Reduce mucho el uso de disco en discos mecánicos.",
                        "Buscar archivos desde el Explorador/Inicio es mucho más lento. Outlook pierde la búsqueda rápida.", ["WSearch"],
                        riesgo="medio", defecto=lambda e: e.get("media") == "HDD"),
        CambioServicios("svc_impresion", "extremo", "Servicios (según equipo)", "Cola de impresión",
                        "Deshabilita el servicio de impresión (también cierra una puerta de ataques conocida).",
                        "NO se podrá imprimir (ni a PDF desde algunas apps) hasta restaurar. Solo para equipos sin impresora.",
                        ["Spooler"], riesgo="alto", defecto=lambda e: e.get("impresoras", 1) == 0),
        CambioServicios("svc_bluetooth", "extremo", "Servicios (según equipo)", "Bluetooth",
                        "Deshabilita el servicio de soporte Bluetooth.",
                        "Dejan de funcionar auriculares, mouse y teclados Bluetooth. Solo si no los usás.",
                        ["bthserv"], riesgo="alto", defecto=False),
        CambioServicios("svc_xbox", "extremo", "Servicios (según equipo)", "Servicios de Xbox",
                        "Deshabilita autenticación, partidas guardadas, accesorios y red de Xbox.",
                        "NO funcionan Game Pass, app de Xbox ni juegos de Microsoft Store. Steam/Epic/Battle.net no se afectan.",
                        ["XblAuthManager", "XblGameSave", "XboxGipSvc", "XboxNetApiSvc"], riesgo="alto", defecto=False),
        CambioRegistro("reg_segundo_plano", "extremo", "Procesos en segundo plano", "Bloquear apps de la Tienda en segundo plano",
                       "Impide que las apps de la Tienda corran en segundo plano y quita Widgets/Noticias.",
                       "Apps como Correo, Alarmas o Clima no actualizan ni notifican con la app cerrada. Widgets desaparece.",
                       [("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground", REG_DWORD, 2),
                        ("HKLM", r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", REG_DWORD, 0),
                        ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Feeds", "EnableFeeds", REG_DWORD, 0)], riesgo="medio"),
        CambioRegistro("reg_gaming", "extremo", "Gaming", "Modo Juego activo y sin grabación en segundo plano",
                       "Activa el Modo Juego y apaga Game DVR (grabación automática en segundo plano).",
                       "Win+G ya no graba clips automáticamente. Mejor rendimiento y menos procesos al jugar. Aplica al usuario actual.",
                       [("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", REG_DWORD, 1),
                        ("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", REG_DWORD, 1),
                        ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", REG_DWORD, 0),
                        ("HKCU", W + r"\GameDVR", "AppCaptureEnabled", REG_DWORD, 0)]),
        CambioRegistro("reg_hags", "extremo", "Gaming", "Programación de GPU acelerada por hardware (HAGS)",
                       "Activa HAGS. Puede mejorar latencia en GPUs recientes (NVIDIA serie 10+, AMD RX 5000+).",
                       "Requiere reiniciar. En algunos drivers/juegos causa cuelgues o peor rendimiento: probar y revertir si pasa.",
                       [("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", REG_DWORD, 2)],
                       riesgo="medio", defecto=False),
        CambioRegistro("reg_visual", "extremo", "Efectos visuales", "Efectos visuales mínimos",
                       "Apaga transparencias, animaciones de ventanas y de la barra de tareas, la vista previa de ventanas (Aero Peek) y el retraso de los menús.",
                       "La interfaz se ve más 'plana', sin efectos de transición. Se nota al cerrar sesión y volver a entrar.",
                       [("HKCU", W + r"\Themes\Personalize", "EnableTransparency", REG_DWORD, 0),
                        ("HKCU", r"Control Panel\Desktop\WindowMetrics", "MinAnimate", REG_SZ, "0"),
                        ("HKCU", W + r"\Explorer\Advanced", "TaskbarAnimations", REG_DWORD, 0),
                        ("HKCU", W + r"\Explorer\Advanced", "ListviewAlphaSelect", REG_DWORD, 0),
                        ("HKCU", W + r"\Explorer\VisualEffects", "VisualFXSetting", REG_DWORD, 3),
                        ("HKCU", r"Software\Microsoft\Windows\DWM", "EnableAeroPeek", REG_DWORD, 0),
                        ("HKCU", r"Control Panel\Desktop", "MenuShowDelay", REG_SZ, "0")]),
        CambioAnimaciones("anim_ui", "extremo", "Efectos visuales", "Quitar todas las animaciones de Windows",
                          "Apaga animaciones y desvanecimientos de menús, ventanas, listas y cuadros de ayuda, y deja activo el suavizado de letras (ClearType) para que el texto siga nítido.",
                          "La interfaz responde al instante pero se ve más 'seca'. Se aplica en el momento, sin reiniciar."),
        CambioFondoNegro("fondo_negro", "extremo", "Efectos visuales", "Fondo de escritorio negro sólido",
                         "Quita la imagen de fondo y deja el escritorio en negro sólido: nada que dibujar ni mantener en memoria.",
                         "Perdés el fondo de pantalla actual (al restaurar vuelve el original). Los iconos del escritorio se siguen viendo igual.",
                         [("HKCU", r"Control Panel\Desktop", "WallPaper", REG_SZ, ""),
                          ("HKCU", r"Control Panel\Colors", "Background", REG_SZ, "0 0 0"),
                          ("HKCU", W + r"\Explorer\Wallpapers", "BackgroundType", REG_DWORD, 1)]),
        CambioEnergia("energia", "extremo", "Energía", "Plan de energía: Alto rendimiento",
                      "Evita que el procesador baje de frecuencia para ahorrar energía.",
                      "Más consumo y calor. En notebooks reduce mucho la autonomía de la batería.",
                      riesgo="medio", defecto=lambda e: not e.get("bateria", False)),
        CambioHibernacion("hibernacion", "extremo", "Energía", "Desactivar hibernación e inicio rápido",
                          "Elimina hiberfil.sys (libera gigas = tamaño de la RAM) y desactiva el inicio rápido.",
                          "No se puede hibernar y el arranque puede ser unos segundos más lento. Útil si falta espacio en disco.",
                          riesgo="bajo", defecto=False),
    ]
    return c


CATALOGO: List[Cambio] = _catalogo()
POR_ID: Dict[str, Cambio] = {x.id: x for x in CATALOGO}


# ====================================================================
# Punto de restauración (obligatorio)
# ====================================================================
def crear_punto_restauracion(env: Entorno, descripcion: str, emitir: Callable[[str], None]) -> bool:
    emitir("Creando punto de restauración (puede tardar un minuto)...")
    env.ps("Enable-ComputerRestore -Drive ($env:SystemDrive + '\\')")
    clave = ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore", "SystemRestorePointCreationFrequency")
    ex, val, _t = env.reg_get(*clave)
    env.reg_set(*clave, REG_DWORD, 0)  # permite crear más de uno cada 24 h
    try:
        env.ps(f"Checkpoint-Computer -Description '{descripcion}' -RestorePointType MODIFY_SETTINGS", 300)
        env.pausa(2)
        cod, out = env.ps(f"@(Get-ComputerRestorePoint | Where-Object {{ $_.Description -eq '{descripcion}' }}).Count", 60)
        try:
            return int(out.strip().splitlines()[-1]) >= 1
        except (ValueError, IndexError):
            return False
    finally:
        if ex:
            env.reg_set(*clave, REG_DWORD, val)
        else:
            env.reg_del(*clave)


# ====================================================================
# Plan, aplicar, restaurar
# ====================================================================
def cambios_del_nivel(nivel: str) -> List[Cambio]:
    tope = ORDEN.index(nivel)
    return [c for c in CATALOGO if ORDEN.index(c.nivel) <= tope]


def plan(nivel: str, env: Entorno, equipo: Optional[dict] = None) -> List[dict]:
    """Vista previa: qué haría cada cambio EN ESTE equipo, sin modificar nada."""
    equipo = equipo if equipo is not None else env.detectar_equipo()
    res = []
    with env.lecturas_en_cache():  # las 5 apps consultan la misma lista de paquetes: se pide una sola vez
        for c in cambios_del_nivel(nivel):
            try:
                aplica, detalle = c.aplica(env)
            except Exception as ex:
                aplica, detalle = False, f"no se pudo evaluar: {ex}"
            res.append({"id": c.id, "nivel": c.nivel, "grupo": c.grupo, "titulo": c.titulo, "que_hace": c.que_hace,
                        "consecuencia": c.consecuencia, "riesgo": c.riesgo, "reversible": c.reversible,
                        "aplica": aplica, "detalle": detalle, "seleccionado": aplica and c.defecto(equipo)})
    return res


def _guardar(ruta: str, manifest: dict) -> None:
    """Escritura atómica: si se corta la luz a mitad, el manifiesto anterior queda intacto."""
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ruta)


_RE_SESION = re.compile(r"^\d{8}_\d{6}$")


def _leer_manifest(ruta: str) -> Optional[dict]:
    """Lee un manifiesto y descarta lo que no tenga forma válida (puede haber sido manipulado)."""
    try:
        with open(ruta, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(m, dict) or not isinstance(m.get("cambios"), list) or m.get("nivel") not in NIVELES:
        return None
    if not all(isinstance(c, dict) and isinstance(c.get("id"), str) for c in m["cambios"]):
        return None
    return m


def aplicar(nivel: str, env: Entorno, ids: Optional[List[str]] = None, emitir: Callable[[str], None] = print,
            equipo: Optional[dict] = None) -> Optional[str]:
    """Aplica un nivel. Devuelve el id de sesión o None si se abortó."""
    if not env.is_admin():
        emitir("ERROR: hay que ejecutar como administrador.")
        return None
    equipo = equipo if equipo is not None else env.detectar_equipo()
    elegidos = [p for p in plan(nivel, env, equipo) if (p["id"] in ids if ids is not None else p["seleccionado"])]
    if not elegidos:
        emitir("No hay cambios para aplicar.")
        return None

    sesion = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    desc = f"BottiMint {sesion} {nivel}"
    antes = base.info_sistema()
    if not crear_punto_restauracion(env, desc, emitir):
        emitir("ABORTADO: no se pudo crear/verificar el punto de restauración. NO se modificó nada.")
        emitir("Revisá que la Protección del sistema esté habilitada para la unidad C: y que haya espacio.")
        return None
    emitir(f"Punto de restauración creado: '{desc}'")

    base.preparar_dir_datos(env.base_dir)
    carpeta = os.path.join(env.base_dir, "sesiones", sesion)
    os.makedirs(carpeta, exist_ok=True)
    ruta_manifest = os.path.join(carpeta, "manifest.json")
    manifest = {"sesion": sesion, "nivel": nivel, "punto_restauracion": desc, "equipo": equipo,
                "inicio": datetime.datetime.now().isoformat(timespec="seconds"), "cambios": [], "restaurada": False}
    _guardar(ruta_manifest, manifest)

    for p in elegidos:
        c = POR_ID[p["id"]]
        emitir(f"→ {c.titulo}...")
        estado: dict = {}
        entrada = {"id": c.id, "titulo": c.titulo, "consecuencia": c.consecuencia, "reversible": c.reversible,
                   "estado": estado, "ok": True, "resultado": ""}
        try:
            entrada["resultado"] = c.aplicar(env, emitir, estado)
        except Exception as ex:
            entrada["ok"], entrada["resultado"] = False, f"ERROR: {ex}"
        emitir("   " + entrada["resultado"])
        manifest["cambios"].append(entrada)
        _guardar(ruta_manifest, manifest)  # se guarda tras CADA cambio

    manifest["fin"] = datetime.datetime.now().isoformat(timespec="seconds")
    _guardar(ruta_manifest, manifest)
    despues = base.info_sistema()
    _informe(carpeta, manifest, antes, despues, emitir)
    emitir(f"Listo. Sesión {sesion}. Para deshacer: restaurar --sesion {sesion}")
    return sesion


def _informe(carpeta: str, manifest: dict, antes: dict, despues: dict, emitir) -> None:
    L = [tr("BottiMint - INFORME DE OPTIMIZACIÓN"), "=" * 56,
         tr("Fecha: {f}", f=manifest["inicio"]),
         tr("Nivel aplicado: {n}", n=tr(NIVELES[manifest["nivel"]]["titulo"])),
         tr("Punto de restauración de Windows: {p}", p=manifest["punto_restauracion"]), "",
         tr("Espacio libre: {a} -> {d}", a=base.fmt_bytes(antes.get("_libre_bytes", 0)), d=base.fmt_bytes(despues.get("_libre_bytes", 0))),
         tr("Programas de inicio activos: {a} -> {d}", a=antes.get("Programas de inicio activos", "?"), d=despues.get("Programas de inicio activos", "?")),
         "", tr("CAMBIOS REALIZADOS (y qué implican)")]
    for c in manifest["cambios"]:
        L.append(f"  [{'OK' if c['ok'] else tr('FALLÓ')}] {tr(c['titulo'])}: {tr(c['resultado'])}")
        L.append("        " + tr("Consecuencia: {x}", x=tr(c["consecuencia"])))
    L += ["", tr("CÓMO VOLVER ATRÁS"), "  " + tr("- Con esta herramienta: restaurar --sesion {s}", s=manifest["sesion"]),
          "  " + tr("- O desde Windows: Restaurar sistema -> punto indicado arriba.")]
    texto = "\n".join(L)
    with open(os.path.join(carpeta, "informe.txt"), "w", encoding="utf-8") as f:
        f.write(texto)
    escritorio = confiables.carpeta("desktop")
    if os.path.isdir(escritorio):
        try:
            with open(os.path.join(escritorio, f"Informe_optimizacion_{manifest['sesion']}.txt"), "w", encoding="utf-8") as f:
                f.write(texto)
        except OSError:
            pass


def listar_sesiones(env: Entorno) -> List[dict]:
    raiz = os.path.join(env.base_dir, "sesiones")
    res = []
    if os.path.isdir(raiz):
        for n in sorted(os.listdir(raiz)):
            ruta = os.path.join(raiz, n, "manifest.json")
            m = _leer_manifest(ruta) if _RE_SESION.match(n) and os.path.isfile(ruta) else None
            if m:
                res.append({"sesion": n, "nivel": m.get("nivel"), "restaurada": m.get("restaurada"), "cambios": len(m.get("cambios", []))})
    return res


def restaurar(env: Entorno, sesion: Optional[str] = None, emitir: Callable[[str], None] = print) -> bool:
    """Deshace una sesión (por defecto, la última no restaurada), en orden inverso."""
    if not env.is_admin():
        emitir("ERROR: hay que ejecutar como administrador.")
        return False
    pendientes = [s for s in listar_sesiones(env) if not s["restaurada"]]
    if sesion is None:
        if not pendientes:
            emitir("No hay sesiones para restaurar.")
            return False
        sesion = pendientes[-1]["sesion"]
    if not _RE_SESION.match(str(sesion)):
        emitir("Identificador de sesión inválido.")
        return False
    ruta = os.path.join(env.base_dir, "sesiones", sesion, "manifest.json")
    manifest = _leer_manifest(ruta) if os.path.isfile(ruta) else None
    if manifest is None:
        emitir(f"No existe la sesión {sesion} o su manifiesto no es válido.")
        return False
    emitir(f"Restaurando sesión {sesion} (nivel {manifest['nivel']})...")
    for entrada in reversed(manifest["cambios"]):
        c = POR_ID.get(entrada["id"])
        if not c or not entrada.get("estado"):
            continue
        if not c.reversible and not isinstance(c, CambioApps):
            continue
        try:
            emitir(f"← {entrada['titulo']}: {c.revertir(env, entrada['estado'])}")
        except Exception as ex:
            emitir(f"← {entrada['titulo']}: ERROR al restaurar ({ex})")
    manifest["restaurada"] = True
    _guardar(ruta, manifest)
    emitir("Restauración terminada. Conviene reiniciar la PC.")
    emitir("Los archivos temporales borrados no se restauran (son descartables).")
    return True


# ====================================================================
# CLI
# ====================================================================
def resumen_nivel(nivel: str) -> str:
    n = NIVELES[nivel]
    L = [tr(n["titulo"]), "", tr("Ideal para: {x}", x=tr(n["para_quien"])), "", tr("Qué hace:")]
    L += [f"  • {tr(x)}" for x in n["que_hace"]]
    L += ["", tr("Consecuencias a tener en cuenta:")] + [f"  ! {tr(x)}" for x in n["consecuencias"]]
    L += ["", tr("Reversibilidad:") + " " + tr(n["reversibilidad"])]
    return "\n".join(L)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="BottiMint por niveles")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("niveles", help="explica los 3 niveles")
    p = sub.add_parser("plan", help="vista previa de un nivel en este equipo")
    p.add_argument("--nivel", choices=ORDEN, required=True)
    p = sub.add_parser("aplicar", help="aplica un nivel (crea punto de restauración antes)")
    p.add_argument("--nivel", choices=ORDEN, required=True)
    p.add_argument("--sin", default="", help="ids a excluir, separados por coma")
    p.add_argument("--solo", default="", help="aplicar únicamente estos ids")
    p.add_argument("--si", action="store_true", help="no pedir confirmación")
    sub.add_parser("sesiones", help="lista las sesiones guardadas")
    p = sub.add_parser("restaurar", help="deshace una sesión")
    p.add_argument("--sesion")
    sub.add_parser("restauracion-sistema", help="abre Restaurar sistema de Windows")
    a = ap.parse_args()
    env = Entorno()

    if a.cmd == "niveles":
        for n in ORDEN:
            print(resumen_nivel(n) + "\n" + "-" * 60)
    elif a.cmd == "plan":
        print(resumen_nivel(a.nivel) + "\n")
        for x in plan(a.nivel, env):
            marca = "[x]" if x["seleccionado"] else ("[ ]" if x["aplica"] else "[-]")
            print(f"{marca} {x['id']:<18} {x['titulo']}  (riesgo {x['riesgo']})")
            print(f"      {x['consecuencia']}")
            if x["detalle"]:
                print(f"      · {x['detalle']}")
    elif a.cmd == "aplicar":
        print(resumen_nivel(a.nivel) + "\n")
        if not a.si and input("¿Entendés las consecuencias y querés continuar? (s/N) ").strip().lower() != "s":
            print("Cancelado.")
            return
        ids = None
        if a.solo:
            ids = a.solo.split(",")
        elif a.sin:
            excl = set(a.sin.split(","))
            ids = [x["id"] for x in plan(a.nivel, env) if x["seleccionado"] and x["id"] not in excl]
        aplicar(a.nivel, env, ids)
    elif a.cmd == "sesiones":
        for s in listar_sesiones(env):
            print(f"{s['sesion']}  nivel={s['nivel']}  cambios={s['cambios']}  {'(restaurada)' if s['restaurada'] else ''}")
    elif a.cmd == "restaurar":
        restaurar(env, a.sesion)
    elif a.cmd == "restauracion-sistema":
        env.run(["rstrui.exe"])
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
