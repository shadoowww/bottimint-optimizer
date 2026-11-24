# -*- coding: utf-8 -*-
"""Preferencias del usuario (idioma y tema). Nada más: BottiMint no guarda datos personales.

Se guardan por usuario en  %APPDATA%\\BottiMint\\ajustes.json  (en otros sistemas, ~/.bottimint/ajustes.json).
Seguridad: el archivo es solo una preferencia; cada valor se valida contra una lista cerrada, así que un archivo
manipulado no puede inyectar nada (valores desconocidos se ignoran).
"""
import json
import os
from typing import Optional

IDIOMAS_VALIDOS = ("es", "en", "ru", "ja", "zh")
TEMAS_VALIDOS = ("claro", "oscuro")


def ruta_ajustes() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "BottiMint", "ajustes.json")


def idioma_del_sistema() -> str:
    """Idioma de la interfaz de Windows si está soportado; si no, inglés."""
    codigo = ""
    try:
        import ctypes
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
        codigo = {0x09: "en", 0x0A: "es", 0x19: "ru", 0x11: "ja", 0x04: "zh"}.get(lcid & 0x3FF, "")
    except Exception:
        import locale
        try:
            codigo = (locale.getlocale()[0] or os.environ.get("LANG", "") or "")[:2].lower()
        except Exception:
            codigo = ""
    return codigo if codigo in IDIOMAS_VALIDOS else "en"


def tema_del_sistema() -> str:
    """Respeta el modo de aplicaciones de Windows (claro/oscuro); por defecto, oscuro."""
    try:
        import winreg  # type: ignore
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return "claro" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "oscuro"
    except Exception:
        return "oscuro"


def cargar(ruta: Optional[str] = None) -> dict:
    cfg = {"idioma": idioma_del_sistema(), "tema": tema_del_sistema()}
    try:
        with open(ruta or ruta_ajustes(), encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict):
            if datos.get("idioma") in IDIOMAS_VALIDOS:
                cfg["idioma"] = datos["idioma"]
            if datos.get("tema") in TEMAS_VALIDOS:
                cfg["tema"] = datos["tema"]
    except (OSError, ValueError):
        pass
    return cfg


def guardar(idioma: str, tema: str, ruta: Optional[str] = None) -> Optional[str]:
    if idioma not in IDIOMAS_VALIDOS or tema not in TEMAS_VALIDOS:
        return None
    destino = ruta or ruta_ajustes()
    try:
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        tmp = destino + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"idioma": idioma, "tema": tema}, f, indent=1)
        os.replace(tmp, destino)
        return destino
    except OSError:
        return None
