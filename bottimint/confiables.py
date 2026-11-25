# -*- coding: utf-8 -*-
"""Ubicaciones del sistema obtenidas de Windows y NO de variables de entorno.

Por qué existe: con UAC, el proceso elevado hereda el entorno de quien lo lanzó. Si las carpetas protegidas, el
System32 desde el que se ejecutan powershell/sc/reg o la carpeta de manifiestos salieran de `SystemRoot`,
`USERPROFILE` o `ProgramData`, quien lance el programa con esas variables cambiadas podría desproteger carpetas reales,
hacer que se ejecute un `powershell.exe` falso con privilegios de administrador o redirigir los manifiestos.

Aquí, en Windows, las rutas se piden con GetWindowsDirectoryW / GetSystemDirectoryW / SHGetKnownFolderPath (que leen
el registro y el token del usuario, no el entorno del proceso). Fuera de Windows (CI en Linux, pruebas) o si la API
fallara, se usan las variables de entorno como antes.

También `endurecer_proceso()`: quita el directorio actual de la búsqueda de ejecutables y de DLL.
"""
import ctypes
import os
import uuid
from typing import Optional

IS_WIN = os.name == "nt"

# Carpetas conocidas de Windows (KNOWNFOLDERID) -> variable de entorno que se usa solo como último recurso.
_CARPETAS = {
    "profile": ("5E6C858F-0E22-4760-9AFE-EA3317B67173", "USERPROFILE"),
    "programdata": ("62AB5D82-FDC1-4DC3-A9DD-070D1D495D97", "ProgramData"),
    "programfiles": ("905E63B6-C1BF-494E-B29C-65B732D3D21A", "ProgramFiles"),
    "programfilesx86": ("7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E", "ProgramFiles(x86)"),
    "localappdata": ("F1B32785-6FBA-4FCB-9D85-E7F6FFC9C77D", "LOCALAPPDATA"),
    "appdata": ("3EB685DB-65F9-4CF6-A03A-E3EF65729F3D", "APPDATA"),
    "documents": ("FDD39AD0-238F-46AF-ADB4-6C85480369C7", ""),
    "desktop": ("B4BFCC3A-DB2C-424C-B029-7FE99A87C641", ""),
    "pictures": ("33E28130-4E1E-4676-835A-98395C3BC3BB", ""),
    "videos": ("18989B1D-99B5-455B-841C-AB7C74E4DDFC", ""),
    "music": ("4BD8D571-6D19-48D3-BE97-422220080E43", ""),
    "downloads": ("374DE290-123F-4565-9164-39C4925E467B", ""),
    "contacts": ("56784854-C6CB-462B-8169-88E350ACB882", ""),
    "favorites": ("1777F761-68AD-4D8A-87BD-30B759FA33DD", ""),
}
# Nombres de variable de entorno de Windows -> clave de _CARPETAS (para `variable()`)
_VARIABLES = {"userprofile": "profile", "programdata": "programdata", "programfiles": "programfiles",
              "programfiles(x86)": "programfilesx86", "localappdata": "localappdata", "appdata": "appdata"}


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]


def _api_carpeta_conocida(guid: str) -> Optional[str]:
    """SHGetKnownFolderPath. None si no se puede (no es Windows o la llamada falla)."""
    if not IS_WIN:
        return None
    try:
        g = _GUID.from_buffer_copy(uuid.UUID(guid).bytes_le)
        ruta = ctypes.c_void_p()
        shell32, ole32 = ctypes.WinDLL("shell32"), ctypes.WinDLL("ole32")  # type: ignore[attr-defined]
        shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(_GUID), ctypes.c_ulong, ctypes.c_void_p,
                                                 ctypes.POINTER(ctypes.c_void_p)]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        try:
            if shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(ruta)) != 0 or not ruta.value:
                return None
            return ctypes.wstring_at(ruta.value) or None
        finally:
            if ruta.value:
                ole32.CoTaskMemFree(ruta)
    except Exception:
        return None


def _api_dir_windows(sistema: bool) -> Optional[str]:
    """GetSystemDirectoryW (System32) o GetWindowsDirectoryW (C:\\Windows)."""
    if not IS_WIN:
        return None
    try:
        k32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined]
        fn = k32.GetSystemDirectoryW if sistema else k32.GetWindowsDirectoryW
        fn.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
        fn.restype = ctypes.c_uint
        buf = ctypes.create_unicode_buffer(520)
        n = fn(buf, 520)
        return buf.value if 0 < n < 520 else None
    except Exception:
        return None


def windows_dir() -> str:
    """C:\\Windows (de la API de Windows; la variable SystemRoot solo como último recurso)."""
    return _api_dir_windows(False) or os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"


def system32() -> str:
    return _api_dir_windows(True) or os.path.join(windows_dir(), "System32")


def unidad_sistema() -> str:
    """Unidad donde está Windows, como 'C:'."""
    return os.path.splitdrive(windows_dir())[0] or "C:"


def carpeta(clave: str) -> str:
    """Carpeta conocida ('profile', 'programdata', 'documents', ...). Vacío si no se pudo averiguar."""
    guid, var = _CARPETAS[clave]
    r = _api_carpeta_conocida(guid)
    if r:
        return r
    if clave == "profile":
        return os.environ.get("USERPROFILE") or os.path.expanduser("~")
    if var:
        return os.environ.get(var, "")
    base = carpeta("profile")  # documents, desktop...: subcarpetas estándar del perfil
    return os.path.join(base, clave.capitalize()) if base else ""


def variable(nombre: str) -> str:
    """Como os.environ.get(nombre, ""), pero las variables que definen carpetas del sistema se piden a Windows."""
    n = nombre.lower()
    if n in ("systemroot", "windir"):
        return windows_dir()
    if n == "systemdrive":
        return unidad_sistema()
    if n in _VARIABLES:
        return carpeta(_VARIABLES[n])
    return os.environ.get(nombre, "")


def carpeta_de_datos() -> str:
    """Carpeta de datos de BottiMint (sesiones e informes): %ProgramData%\\BottiMint, sin fiarse de la variable."""
    return os.path.join(carpeta("programdata") or carpeta("profile"), "BottiMint")


def endurecer_proceso() -> None:
    """Quita el directorio actual de la búsqueda de ejecutables (CreateProcess) y de DLL. Llamar al arrancar.

    Si la carpeta desde la que se abre el programa (por ejemplo Descargas) tiene un winget.exe o una DLL plantados,
    no se ejecutan ni se cargan con privilegios de administrador. Los procesos hijos heredan el ajuste."""
    if not IS_WIN:
        return
    os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"
    try:
        ctypes.WinDLL("kernel32").SetDllDirectoryW("")  # type: ignore[attr-defined]
    except Exception:
        pass
