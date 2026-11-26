#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BottiMint - herramienta de limpieza y mantenimiento (Windows 10/11).

Qué hace:
  * Analiza cuánto espacio se puede recuperar ANTES de tocar nada.
  * Limpia temporales, cachés, papelera, volcados de error, caché de Windows Update, etc.
  * Administra programas de inicio (deshabilitar/habilitar, reversible, igual que el Administrador de tareas).
  * Mantenimiento opcional: punto de restauración, SFC, DISM, optimizar unidad, plan de energía.
  * Genera un informe en el Escritorio (antes/después) para guardar o compartir.

Qué NO hace (a propósito): "limpiar el registro", ni desactivar servicios, ni tocar archivos personales.

Este módulo es la base de limpieza que usa el motor por niveles (nucleo.py).
Uso suelto (consola):
    python -m bottimint limpieza --analizar   -> solo muestra cuánto se puede liberar
    python -m bottimint limpieza --limpiar    -> ejecuta las tareas marcadas por defecto
"""
import argparse
import ctypes
import datetime
import glob
import os
import platform
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Optional

try:
    import winreg  # type: ignore
except ImportError:  # no estamos en Windows
    winreg = None

from . import confiables

IS_WIN = os.name == "nt"



# ============================== utilidades ==============================

def fmt_bytes(n: float) -> str:
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unidad == "TB":
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
        n /= 1024
    return f"{n:.1f} TB"


def is_admin() -> bool:
    if not IS_WIN:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    """Reabre el programa pidiendo permisos de administrador (UAC)."""
    params = " ".join(f'"{a}"' for a in sys.argv)
    if getattr(sys, "frozen", False):  # corriendo como .exe
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv[1:]), None, 1)
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


def env(nombre: str) -> str:
    """Valor de una variable de entorno, EXCEPTO las que definen carpetas del sistema (SystemRoot, SystemDrive,
    USERPROFILE, ProgramData, ProgramFiles, LOCALAPPDATA, APPDATA...): esas se piden a Windows (ver confiables.py),
    porque un entorno manipulado no debe poder desproteger carpetas ni redirigir ejecutables."""
    return confiables.variable(nombre)


def join_env(var: str, *partes: str) -> Optional[str]:
    base = env(var)
    return os.path.join(base, *partes) if base else None


def _carpetas_protegidas() -> List[str]:
    """Carpetas dentro de las cuales NUNCA se limpia nada, aunque una variable de entorno (TEMP, etc.) apunte ahí."""
    sr, perfil = confiables.windows_dir(), confiables.carpeta("profile")
    lista = [confiables.carpeta("programfiles"), confiables.carpeta("programfilesx86")]
    for sub in ("System32", "SysWOW64", "WinSxS", "servicing", "Boot", "Fonts", "assembly", "Microsoft.NET"):
        lista.append(os.path.join(sr, sub) if sr else "")
    for sub in ("Documents", "Desktop", "Pictures", "Videos", "Music", "Downloads", "OneDrive", "Contacts", "Favorites"):
        lista.append(os.path.join(perfil, sub) if perfil else "")
    # además, las carpetas personales REALES (pueden estar redirigidas, por ejemplo a OneDrive)
    lista += [confiables.carpeta(k) for k in ("documents", "desktop", "pictures", "videos", "music", "downloads",
                                              "contacts", "favorites")]
    return [x for x in lista if x]


def _es_ruta_peligrosa(p: str) -> bool:
    """Defensa extra: nunca limpiar raíces de disco, el perfil de usuario, carpetas del sistema ni archivos personales.
    Se resuelven los enlaces (realpath) antes de comparar, y se aplica también a rutas que salen de variables de entorno."""
    p = os.path.normcase(os.path.realpath(os.path.abspath(p)))
    if os.path.dirname(p) == p:  # raíz de unidad
        return True
    prohibidas = {os.path.normcase(os.path.realpath(x)) for x in
                  (confiables.carpeta("profile"), confiables.windows_dir(), confiables.unidad_sistema() + "\\",
                   confiables.carpeta("programfiles"), confiables.carpeta("programfilesx86"),
                   confiables.carpeta("programdata"), os.path.expanduser("~")) if x}
    if p in prohibidas:
        return True
    for q in _carpetas_protegidas():
        q = os.path.normcase(os.path.realpath(q))
        if p == q or p.startswith(q.rstrip("\\/") + os.sep):
            return True
    return len([x for x in p.replace("\\", "/").split("/") if x]) < 2


def expandir(rutas: List[Optional[str]]) -> List[str]:
    """Expande comodines, descarta vacíos/duplicados/rutas peligrosas."""
    vistos, salida = set(), []
    for r in rutas:
        if not r:
            continue
        for p in (glob.glob(r) if any(c in r for c in "*?[") else [r]):
            clave = os.path.normcase(os.path.abspath(p))
            if clave in vistos or not os.path.lexists(p) or _es_ruta_peligrosa(p):
                continue
            vistos.add(clave)
            salida.append(p)
    return salida


FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def es_enlace(p: str) -> bool:
    """True si es un enlace simbólico O un punto de reanálisis (junction, montaje...). Nunca se sigue ni se borra su destino."""
    try:
        if os.path.islink(p):
            return True
        return bool(getattr(os.lstat(p), "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True  # ante la duda, se trata como peligroso


def _recorrer(raiz: str):
    """Recorre un árbol SIN entrar jamás a enlaces/junctions (os.walk sí entra a las junctions en Windows).
    Devuelve (archivos, carpetas, enlaces) con rutas completas; las carpetas vienen de la más profunda a la más superficial."""
    archivos, carpetas, enlaces = [], [], []
    pila = [raiz]
    while pila:
        actual = pila.pop()
        try:
            with os.scandir(actual) as it:
                entradas = list(it)
        except OSError:
            continue
        for e in entradas:
            if es_enlace(e.path):
                enlaces.append(e.path)
            elif e.is_dir(follow_symlinks=False):
                carpetas.append(e.path)
                pila.append(e.path)
            else:
                archivos.append(e.path)
    carpetas.sort(key=len, reverse=True)
    return archivos, carpetas, enlaces


def tamano_ruta(p: str) -> int:
    if es_enlace(p):
        return 0
    if os.path.isfile(p):
        try:
            return os.path.getsize(p)
        except OSError:
            return 0
    archivos, _c, _e = _recorrer(p)
    total = 0
    for fp in archivos:
        try:
            total += os.path.getsize(fp)
        except OSError:
            pass
    return total


def tamano_total(rutas: List[str]) -> int:
    return sum(tamano_ruta(p) for p in rutas)


def _borrar_archivo(fp: str) -> int:
    try:
        tam = 0 if es_enlace(fp) else os.path.getsize(fp)
        try:
            os.remove(fp)
        except PermissionError:
            os.chmod(fp, stat.S_IWRITE)
            os.remove(fp)
        return tam
    except OSError:
        return -1  # en uso o sin permiso: se saltea


def _quitar_enlace(p: str) -> None:
    """Borra el enlace en sí (nunca el destino): os.remove para symlinks de archivo, os.rmdir para junctions/symlinks de carpeta."""
    try:
        os.remove(p)
    except OSError:
        try:
            os.rmdir(p)
        except OSError:
            pass


def limpiar_rutas(rutas: List[str]):
    """Borra el CONTENIDO de carpetas (las carpetas raíz se conservan) y archivos sueltos.
    Seguridad: si la raíz o cualquier hijo es un enlace/junction, se elimina el enlace pero NO se toca su destino.
    Devuelve (bytes_liberados, archivos_omitidos)."""
    liberado, omitidos = 0, 0
    for p in rutas:
        if es_enlace(p) and not os.path.isfile(p):
            continue  # una raíz de limpieza que es junction/symlink de carpeta: se ignora por completo
        if os.path.isfile(p) or es_enlace(p):
            r = _borrar_archivo(p)
            if r < 0:
                omitidos += 1
            else:
                liberado += r
            continue
        archivos, carpetas, enlaces = _recorrer(p)
        for fp in archivos:
            r = _borrar_archivo(fp)
            if r < 0:
                omitidos += 1
            else:
                liberado += r
        for lp in enlaces:
            _quitar_enlace(lp)
        for dp in carpetas:
            try:
                os.rmdir(dp)  # solo si quedó vacía
            except OSError:
                pass
    return liberado, omitidos


# ============================== ejecución segura de comandos ==============================

def _dir_sistema() -> str:
    return confiables.system32()


def resolver_exe(nombre: str) -> str:
    """Ruta ABSOLUTA del ejecutable. En Windows, los comandos del sistema se toman de System32 y nunca del
    directorio actual ni del PATH (evita que un powershell.exe/sc.exe plantado en esa carpeta se ejecute con
    privilegios de administrador). Si ya viene con ruta, se respeta.
    SIEMPRE devuelve una ruta absoluta en Windows: si el ejecutable no existe NO se devuelve el nombre desnudo (Windows
    lo buscaría en el directorio actual y en el PATH); la ruta inexistente hace que ejecutar() informe "no se encontró"."""
    if not IS_WIN or os.path.dirname(nombre):
        return nombre
    base_ = nombre.lower()
    if base_.endswith(".exe"):
        base_ = base_[:-4]
    sys32 = _dir_sistema()
    if base_ == "powershell":
        cand = os.path.join(sys32, "WindowsPowerShell", "v1.0", "powershell.exe")
    elif base_ == "winget":
        local = confiables.carpeta("localappdata")
        cand = os.path.join(local, "Microsoft", "WindowsApps", "winget.exe") if local else os.path.join(sys32, "winget.exe")
    else:
        cand = os.path.join(sys32, base_ + ".exe")
    return cand


SID_ADMINISTRADORES, SID_SYSTEM = "*S-1-5-32-544", "*S-1-5-18"


def preparar_dir_datos(ruta: str, con_contenido: bool = True) -> str:
    """Crea la carpeta de datos (sesiones/informes) de forma segura:
    - si existe y es un enlace/junction, se rechaza (alguien pudo plantarla para redirigir escrituras);
    - si somos administrador en Windows, se restringe a SYSTEM y Administradores con icacls, ella Y TODO SU CONTENIDO
      (así un usuario común no puede alterar manifiestos que luego se leen con privilegios, ni siquiera los de una
      carpeta que hubiera creado antes que BottiMint). Si no se puede asegurar, se lanza OSError y no se continúa.
    `con_contenido=False` solo asegura la carpeta (para abrirla desde la interfaz): recorrer el contenido tarda más
    cuantas más sesiones hay y solo hace falta antes de escribir sesiones (aplicar)."""
    if os.path.lexists(ruta) and es_enlace(ruta):
        raise OSError(f"La carpeta de datos es un enlace/junction y no es segura: {ruta}")
    os.makedirs(ruta, exist_ok=True)
    if IS_WIN and is_admin():
        _icacls(ruta, "/setowner", SID_ADMINISTRADORES)
        _icacls(ruta, "/inheritance:r", "/grant:r", f"{SID_SYSTEM}:(OI)(CI)F", f"{SID_ADMINISTRADORES}:(OI)(CI)F")
        if con_contenido:
            _asegurar_contenido(ruta)
    return ruta


def _icacls(ruta: str, *args: str) -> None:
    # /L: actúa sobre el propio enlace, nunca sobre su destino (defensa extra: los enlaces ya se quitan antes)
    cod, salida = ejecutar([os.path.join(_dir_sistema(), "icacls.exe"), ruta, *args, "/L"], 30)
    if cod != 0:
        raise OSError(f"No se pudieron asegurar los permisos de {ruta}: {salida[-200:]}")


def _asegurar_contenido(raiz: str) -> None:
    """Deja todo lo que ya había dentro con dueño Administradores y solo los permisos heredados de la raíz.

    NO se usa `icacls /T`: podría seguir una junction plantada y cambiar permisos en carpetas ajenas. Se recorre de
    arriba hacia abajo y cada carpeta se asegura ANTES de listarla: una vez que es de Administradores, un usuario común
    ya no puede crear nada dentro, así que lo que se lista no puede cambiar mientras se procesa. Los enlaces y los
    archivos con varios nombres (enlaces duros) no los crea BottiMint: se quitan sin tocar su destino."""
    pila = [raiz]
    while pila:
        with os.scandir(pila.pop()) as it:
            entradas = list(it)
        for e in entradas:
            enlace = es_enlace(e.path)
            carpeta = not enlace and e.is_dir(follow_symlinks=False)
            if enlace:
                _quitar_enlace(e.path)
            elif not carpeta and os.lstat(e.path).st_nlink > 1:
                os.remove(e.path)  # quita solo este nombre: cambiarle los permisos afectaría al archivo original
            else:
                _icacls(e.path, "/setowner", SID_ADMINISTRADORES)
                _icacls(e.path, "/reset")
                if carpeta:
                    pila.append(e.path)
                continue
            if os.path.lexists(e.path):
                raise OSError(f"No se pudo quitar un enlace sospechoso de la carpeta de datos: {e.path}")


def ejecutar(cmd: List[str], timeout: Optional[int] = None):
    """Ejecuta un comando sin abrir ventana. Devuelve (codigo, salida)."""
    flags = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW
    cmd = [resolver_exe(cmd[0])] + list(cmd[1:])  # lista de argumentos (nunca una cadena de shell) y ruta absoluta
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=flags)
        salida = (r.stdout or b"").decode("cp850", errors="replace") + (r.stderr or b"").decode("cp850", errors="replace")
        return r.returncode, salida.replace("\x00", "").strip()
    except FileNotFoundError:
        return 127, f"No se encontró el comando: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "Tiempo de espera agotado"


# ============================== papelera ==============================

class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]


def papelera_tamano() -> int:
    if not IS_WIN:
        return 0
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
        return int(info.i64Size)
    return 0


def papelera_vaciar() -> None:
    # SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)


# ============================== tareas ==============================

@dataclass
class Tarea:
    clave: str
    titulo: str
    descripcion: str
    por_defecto: bool = True
    requiere_admin: bool = False
    # Para tareas de limpieza:
    rutas: Optional[Callable[[], List[Optional[str]]]] = None
    antes: Optional[Callable[["Motor"], None]] = None     # p.ej. frenar un servicio
    despues: Optional[Callable[["Motor"], None]] = None   # p.ej. reiniciarlo
    # Para tareas de acción (no miden espacio):
    accion: Optional[Callable[["Motor"], str]] = None
    tamano_extra: Optional[Callable[[], int]] = None
    limpieza_extra: Optional[Callable[["Motor"], int]] = None
    es_limpieza: bool = field(init=False, default=False)

    def __post_init__(self):
        self.es_limpieza = self.rutas is not None or self.limpieza_extra is not None


def _navegadores_cache() -> List[Optional[str]]:
    la = env("LOCALAPPDATA")
    if not la:
        return []
    cache_sub = ["Cache", "Code Cache", "GPUCache", "Service Worker\\CacheStorage"]
    lista: List[Optional[str]] = []
    for base in (r"Google\Chrome\User Data", r"Microsoft\Edge\User Data", r"BraveSoftware\Brave-Browser\User Data"):
        for sub in cache_sub:
            lista.append(os.path.join(la, base, "*", sub))
            lista.append(os.path.join(la, base, "*", sub, "Cache_Data"))
    lista.append(os.path.join(la, "Mozilla", "Firefox", "Profiles", "*", "cache2"))
    return lista


def _wu_stop(m: "Motor"):
    for s in ("wuauserv", "bits"):
        ejecutar(["net", "stop", s])


def _wu_start(m: "Motor"):
    for s in ("bits", "wuauserv"):
        ejecutar(["net", "start", s])


def _accion_punto_restauracion(m: "Motor") -> str:
    cod, out = ejecutar(["powershell", "-NoProfile", "-Command",
                         "Checkpoint-Computer -Description 'Antes de optimizar' -RestorePointType MODIFY_SETTINGS"], timeout=180)
    if cod == 0:
        return "Punto de restauración creado."
    return "No se pudo crear (puede estar desactivada la Protección del sistema o ya hay uno de las últimas 24 h)."


def _accion_sfc(m: "Motor") -> str:
    cod, _ = ejecutar(["sfc", "/scannow"], timeout=3600)
    return {0: "SFC: sin infracciones de integridad.", 1: "SFC: encontró y reparó archivos."}.get(cod, f"SFC terminó con código {cod} (revisar CBS.log).")


def _accion_dism(m: "Motor") -> str:
    cod, _ = ejecutar(["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"], timeout=3600)
    return "DISM RestoreHealth completado." if cod == 0 else f"DISM terminó con código {cod}."


def _accion_componentes(m: "Motor") -> str:
    cod, _ = ejecutar(["DISM", "/Online", "/Cleanup-Image", "/StartComponentCleanup"], timeout=3600)
    return "Limpieza de componentes (WinSxS) completada." if cod == 0 else f"DISM terminó con código {cod}."


def _accion_defrag(m: "Motor") -> str:
    # /O elige la optimización correcta: desfragmenta HDD, hace TRIM en SSD.
    cod, _ = ejecutar([ "defrag", env("SystemDrive") or "C:", "/O"], timeout=7200)
    return "Unidad optimizada." if cod == 0 else f"defrag terminó con código {cod}."


def _accion_energia(m: "Motor") -> str:
    cod, _ = ejecutar(["powercfg", "/setactive", "SCHEME_MIN"])
    return "Plan de energía: Alto rendimiento." if cod == 0 else "No se pudo cambiar el plan de energía."


def _accion_dns(m: "Motor") -> str:
    cod, _ = ejecutar(["ipconfig", "/flushdns"])
    return "Caché DNS vaciada." if cod == 0 else "No se pudo vaciar la caché DNS."


def _limpiar_papelera(m: "Motor") -> int:
    antes = papelera_tamano()
    papelera_vaciar()
    return antes


TAREAS: List[Tarea] = [
    Tarea("restauracion", "Crear punto de restauración", "Recomendado antes de tocar nada.",
          True, True, accion=_accion_punto_restauracion),
    Tarea("temp_usuario", "Temporales del usuario", "Carpeta TEMP del usuario actual.",
          rutas=lambda: [env("TEMP"), join_env("LOCALAPPDATA", "Temp")]),
    Tarea("temp_windows", "Temporales de Windows", "C:\\Windows\\Temp.", True, True,
          rutas=lambda: [join_env("SystemRoot", "Temp")]),
    Tarea("navegadores", "Caché de navegadores", "Chrome, Edge, Brave y Firefox (no borra contraseñas ni historial). Cerrá los navegadores.",
          rutas=_navegadores_cache),
    Tarea("inetcache", "Caché de Internet / miniaturas", "INetCache y miniaturas del Explorador.",
          rutas=lambda: [join_env("LOCALAPPDATA", "Microsoft", "Windows", "INetCache"),
                         join_env("LOCALAPPDATA", "Microsoft", "Windows", "Explorer", "thumbcache_*.db")]),
    Tarea("errores", "Informes y volcados de error", "Windows Error Reporting, minidumps, MEMORY.DMP.", True, True,
          rutas=lambda: [join_env("LOCALAPPDATA", "CrashDumps"),
                         join_env("ProgramData", "Microsoft", "Windows", "WER", "ReportQueue"),
                         join_env("ProgramData", "Microsoft", "Windows", "WER", "ReportArchive"),
                         join_env("SystemRoot", "Minidump"), join_env("SystemRoot", "MEMORY.DMP")]),
    Tarea("windows_update", "Caché de Windows Update", "Descargas ya instaladas (SoftwareDistribution\\Download).", True, True,
          rutas=lambda: [join_env("SystemRoot", "SoftwareDistribution", "Download")], antes=_wu_stop, despues=_wu_start),
    Tarea("delivery_opt", "Caché de Optimización de entrega", "Archivos que Windows comparte con otras PCs.", True, True,
          rutas=lambda: [join_env("SystemRoot", "ServiceProfiles", "NetworkService", "AppData", "Local",
                                  "Microsoft", "Windows", "DeliveryOptimization", "Cache")]),
    Tarea("papelera", "Vaciar papelera de reciclaje", "Es irreversible: se pierde lo que haya en la papelera.", True,
          tamano_extra=papelera_tamano, limpieza_extra=_limpiar_papelera),
    Tarea("dns", "Vaciar caché DNS", "Soluciona algunos problemas de navegación.", True, accion=_accion_dns),
    Tarea("componentes", "Limpiar componentes de Windows (WinSxS)", "Libera espacio de actualizaciones viejas. Lento.", False, True,
          accion=_accion_componentes),
    Tarea("sfc", "Verificar archivos del sistema (SFC)", "Repara archivos de Windows dañados. Puede tardar 10-30 min.", False, True,
          accion=_accion_sfc),
    Tarea("dism", "Reparar imagen de Windows (DISM)", "Úsalo si SFC encuentra errores que no puede reparar.", False, True,
          accion=_accion_dism),
    Tarea("defrag", "Optimizar unidad (desfragmentar / TRIM)", "Detecta HDD o SSD y aplica lo correcto.", False, True,
          accion=_accion_defrag),
    Tarea("energia", "Plan de energía: Alto rendimiento", "En notebooks reduce la autonomía de batería.", False, True,
          accion=_accion_energia),
]
TAREAS_POR_CLAVE = {t.clave: t for t in TAREAS}


# ============================== programas de inicio ==============================

@dataclass
class EntradaInicio:
    nombre: str
    comando: str
    origen: str
    hive: int
    ruta_run: str
    ruta_aprobado: str
    habilitado: bool


_ORIGENES_INICIO = []
if winreg:
    _R = r"Software\Microsoft\Windows\CurrentVersion"
    _ORIGENES_INICIO = [
        ("Usuario", winreg.HKEY_CURRENT_USER, _R + r"\Run", _R + r"\Explorer\StartupApproved\Run"),
        ("Sistema", winreg.HKEY_LOCAL_MACHINE, _R + r"\Run", _R + r"\Explorer\StartupApproved\Run"),
        ("Sistema (32 bits)", winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
         _R + r"\Explorer\StartupApproved\Run32"),
    ]


def listar_inicio() -> List[EntradaInicio]:
    res: List[EntradaInicio] = []
    if not winreg:
        return res
    for origen, hive, ruta_run, ruta_ap in _ORIGENES_INICIO:
        try:
            with winreg.OpenKey(hive, ruta_run) as k:
                i = 0
                while True:
                    try:
                        nombre, valor, _t = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    hab = True
                    try:
                        with winreg.OpenKey(hive, ruta_ap) as ka:
                            datos, _ = winreg.QueryValueEx(ka, nombre)
                            hab = not (isinstance(datos, bytes) and datos and datos[0] & 1)  # bit 0 = deshabilitado
                    except OSError:
                        pass
                    res.append(EntradaInicio(nombre, str(valor), origen, hive, ruta_run, ruta_ap, hab))
        except OSError:
            continue
    return res


def cambiar_inicio(e: EntradaInicio, habilitar: bool) -> None:
    """Misma mecánica que el Administrador de tareas: no borra nada, es totalmente reversible."""
    if not winreg:
        raise RuntimeError("Solo disponible en Windows")
    datos = bytes([0x02 if habilitar else 0x03]) + bytes(11)
    with winreg.CreateKeyEx(e.hive, e.ruta_aprobado, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, e.nombre, 0, winreg.REG_BINARY, datos)
    e.habilitado = habilitar


# ============================== motor ==============================

def info_sistema() -> dict:
    d = {"Equipo": platform.node(), "Sistema": f"{platform.system()} {platform.release()} ({platform.version()})",
         "Procesador": platform.processor() or platform.machine()}
    try:
        total, usado, libre = shutil.disk_usage(env("SystemDrive") + "\\" if IS_WIN else "/")
        d["Disco (total)"], d["Disco (libre)"] = fmt_bytes(total), fmt_bytes(libre)
        d["_libre_bytes"] = libre
    except OSError:
        d["_libre_bytes"] = 0
    if IS_WIN:
        class MEM(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("carga", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("libre", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                        ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
        m = MEM()
        m.l = ctypes.sizeof(m)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            d["RAM"] = f"{fmt_bytes(m.total)} (en uso: {m.carga}%)"
    d["Programas de inicio activos"] = str(sum(1 for e in listar_inicio() if e.habilitado))
    return d


class Motor:
    def __init__(self, emitir: Callable[[str], None] = print):
        self._emitir = emitir
        self.registro: List[str] = []
        self.resultados: List[str] = []

    def log(self, msg: str) -> None:
        linea = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
        self.registro.append(linea)
        self._emitir(linea)

    def analizar(self, claves: List[str], al_medir: Callable[[str, int], None] = lambda k, b: None) -> int:
        total = 0
        for t in TAREAS:
            if t.clave not in claves or not t.es_limpieza:
                continue
            if t.requiere_admin and not is_admin():
                self.log(f"{t.titulo}: se necesita administrador, no se midió.")
                continue
            b = tamano_total(expandir(t.rutas())) if t.rutas else 0
            if t.tamano_extra:
                b += t.tamano_extra()
            al_medir(t.clave, b)
            self.log(f"{t.titulo}: {fmt_bytes(b)} recuperables")
            total += b
        self.log(f"TOTAL estimado recuperable: {fmt_bytes(total)}")
        return total

    def optimizar(self, claves: List[str], al_terminar_tarea: Callable[[str], None] = lambda k: None) -> int:
        antes = info_sistema()
        self.log("Iniciando optimización...")
        liberado_total = 0
        for t in TAREAS:  # respeta el orden de la lista (el punto de restauración va primero)
            if t.clave not in claves:
                continue
            if t.requiere_admin and not is_admin():
                self.log(f"OMITIDO: {t.titulo} (requiere administrador)")
                al_terminar_tarea(t.clave)
                continue
            self.log(f"→ {t.titulo}...")
            try:
                if t.antes:
                    t.antes(self)
                if t.rutas:
                    lib, omit = limpiar_rutas(expandir(t.rutas()))
                    liberado_total += lib
                    msg = f"{t.titulo}: {fmt_bytes(lib)} liberados" + (f" ({omit} archivos en uso omitidos)" if omit else "")
                    self.resultados.append(msg)
                    self.log("   " + msg)
                if t.limpieza_extra:
                    lib = t.limpieza_extra(self)
                    liberado_total += lib
                    msg = f"{t.titulo}: {fmt_bytes(lib)} liberados"
                    self.resultados.append(msg)
                    self.log("   " + msg)
                if t.accion:
                    msg = t.accion(self)
                    self.resultados.append(f"{t.titulo}: {msg}")
                    self.log("   " + msg)
            except Exception as ex:  # una tarea fallida no frena las demás
                self.log(f"   ERROR en {t.titulo}: {ex}")
            finally:
                if t.despues:
                    try:
                        t.despues(self)
                    except Exception:
                        pass
                al_terminar_tarea(t.clave)
        despues = info_sistema()
        self.log(f"Listo. Espacio liberado en total: {fmt_bytes(liberado_total)}")
        self._antes, self._despues = antes, despues
        return liberado_total

    def guardar_informe(self) -> str:
        ahora = datetime.datetime.now()
        antes = getattr(self, "_antes", None) or info_sistema()
        despues = getattr(self, "_despues", None) or antes
        carpeta = confiables.carpeta("desktop")
        if not os.path.isdir(carpeta):
            carpeta = confiables.carpeta("profile")
        ruta = os.path.join(carpeta, f"Informe_mantenimiento_{ahora:%Y%m%d_%H%M}.txt")
        L = ["BottiMint - INFORME DE MANTENIMIENTO", "=" * 50,
             f"Fecha: {ahora:%d/%m/%Y %H:%M}", ""]
        L.append("DATOS DEL EQUIPO")
        for k, v in despues.items():
            if not k.startswith("_"):
                L.append(f"  {k}: {v}")
        L += ["", "RESULTADO",
              f"  Espacio libre antes:   {fmt_bytes(antes['_libre_bytes'])}",
              f"  Espacio libre después: {fmt_bytes(despues['_libre_bytes'])}",
              f"  Diferencia:            {fmt_bytes(max(0, despues['_libre_bytes'] - antes['_libre_bytes']))}",
              f"  Programas de inicio activos: {antes.get('Programas de inicio activos', '?')} → {despues.get('Programas de inicio activos', '?')}",
              "", "TAREAS REALIZADAS"]
        L += [f"  - {r}" for r in self.resultados] or ["  (ninguna)"]
        L += ["", "DETALLE", *self.registro]
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("\n".join(L))
        self.log(f"Informe guardado en: {ruta}")
        return ruta


# ============================== CLI ==============================

def main() -> None:
    ap = argparse.ArgumentParser(description="BottiMint")
    ap.add_argument("--analizar", action="store_true", help="solo mide el espacio recuperable")
    ap.add_argument("--limpiar", action="store_true", help="ejecuta las tareas marcadas por defecto sin GUI")
    args = ap.parse_args()

    if args.analizar or args.limpiar:
        claves = [t.clave for t in TAREAS if t.por_defecto]
        m = Motor()
        if args.analizar:
            m.analizar(claves)
        else:
            m.optimizar(claves)
            m.guardar_informe()
        return

    ap.print_help()


if __name__ == "__main__":
    main()
