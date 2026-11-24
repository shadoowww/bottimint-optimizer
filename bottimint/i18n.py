# -*- coding: utf-8 -*-
"""Traducciones. La clave es el texto en español (idioma base); cada idioma es un diccionario en bottimint/idiomas/.

    tr("Cancelar")                       -> "Cancel" (en inglés)
    tr("Se aplicarán {n} cambios.", n=5) -> "5 changes will be applied."

Las claves listadas en PATRONES de cada idioma también traducen textos dinámicos que ya vienen formateados desde
el motor (por ejemplo "12 tareas activas"): se reconocen por patrón. Si falta una traducción se usa el inglés y,
si tampoco está, el texto original: nunca falla ni deja la interfaz en blanco.
"""
import importlib
import re
import sys
from typing import Dict, List, Optional, Tuple

IDIOMAS = {"es": "Español", "en": "English", "ru": "Русский", "ja": "日本語", "zh": "中文"}
_idioma = "es"
_tablas: Dict[str, dict] = {}
_patrones: Dict[str, List[Tuple["re.Pattern", str]]] = {}


def _tabla(cod: str) -> dict:
    if cod not in _tablas:
        try:
            _tablas[cod] = importlib.import_module(f"bottimint.idiomas.{cod}").T
        except ImportError:
            _tablas[cod] = {}
        pats = []
        # solo las claves declaradas en PATRONES (mensajes dinámicos del motor) se reconocen por patrón;
        # así una clave como "{libre} de {total}" nunca se aplica por error a un texto cualquiera
        declaradas = getattr(sys.modules.get(f"bottimint.idiomas.{cod}"), "PATRONES", ())
        for clave, valor in _tablas[cod].items():
            if clave in declaradas and "{" in clave:
                rx = re.escape(clave)
                rx = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>.+?)", rx)
                pats.append((re.compile("^" + rx + "$", re.S), valor))
        _patrones[cod] = pats
    return _tablas[cod]


def set_idioma(cod: str) -> None:
    global _idioma
    _idioma = cod if cod in IDIOMAS else "es"


def idioma() -> str:
    return _idioma


def _cadena() -> List[str]:
    return [] if _idioma == "es" else ([_idioma, "en"] if _idioma != "en" else ["en"])


def _buscar(texto: str) -> Optional[str]:
    for cod in _cadena():
        t = _tabla(cod)
        if texto in t:
            return t[texto]
        for rx, plantilla in _patrones[cod]:
            m = rx.match(texto)
            if m:
                try:
                    return plantilla.format(**{k: tr(v) for k, v in m.groupdict().items()})
                except (KeyError, IndexError, ValueError):
                    return None
    return None


def tr(texto: str, **kw) -> str:
    """Traduce `texto` (en español) al idioma activo y rellena los {marcadores} con kw."""
    if not texto:
        return texto
    if kw:
        plantilla = None
        for cod in _cadena():
            plantilla = _tabla(cod).get(texto)
            if plantilla is not None:
                break
        try:
            return (plantilla if plantilla is not None else texto).format(**kw)
        except (KeyError, IndexError, ValueError):
            return texto
    r = _buscar(texto)
    return r if r is not None else texto
