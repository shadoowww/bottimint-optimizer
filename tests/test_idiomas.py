"""Cobertura y coherencia de las traducciones, y paletas de los temas."""
import ast
import glob
import importlib
import os
import re
import unittest

from bottimint import i18n, instalador, nucleo, temas
from bottimint.i18n import tr

PAQUETE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bottimint")
MARCADORES = re.compile(r"\{(\w+)\}")


def claves_de_codigo():
    """Todos los literales que el código pasa a tr(...)."""
    claves = set()
    for ruta in glob.glob(os.path.join(PAQUETE, "*.py")):
        with open(ruta, encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        for n in ast.walk(arbol):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "tr" and n.args \
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                claves.add(n.args[0].value)
    return claves


def textos_del_catalogo():
    s = []
    for n in nucleo.NIVELES.values():
        for v in n.values():
            s += v if isinstance(v, list) else [v]
    for c in nucleo.POR_ID.values():
        s += [c.grupo, c.titulo, c.que_hace, c.consecuencia]
    for p in instalador.CATALOGO:
        s += [p.categoria, p.descripcion] + ([p.nota] if p.nota else [])
    for v in instalador.PERFILES.values():
        s += [v["titulo"], v["descripcion"]]
    return set(s)


class PruebasIdiomas(unittest.TestCase):
    def tearDown(self):
        i18n.set_idioma("es")

    def tabla(self, cod):
        return importlib.import_module(f"bottimint.idiomas.{cod}").T

    def test_ingles_cubre_interfaz_y_catalogo_completos(self):
        en = self.tabla("en")
        faltan = [k for k in claves_de_codigo() | textos_del_catalogo() if k not in en]
        self.assertEqual(faltan, [], "textos sin traducir al inglés")

    def test_ruso_japones_y_chino_cubren_toda_la_interfaz(self):
        for cod in ("ru", "ja", "zh"):
            t = self.tabla(cod)
            faltan = [k for k in claves_de_codigo() if k not in t]
            self.assertEqual(faltan, [], f"faltan en {cod}")
            vacias = [k for k, v in t.items() if not str(v).strip()]
            self.assertEqual(vacias, [], f"traducciones vacías en {cod}")

    def test_los_marcadores_coinciden_en_todas_las_traducciones(self):
        for cod in ("en", "ru", "ja", "zh"):
            for clave, valor in self.tabla(cod).items():
                if clave in ("PATRONES",):
                    continue
                self.assertEqual(set(MARCADORES.findall(clave)) - {"s2"}, set(MARCADORES.findall(valor)) - {"s2"},
                                 f"[{cod}] marcadores distintos en {clave!r}")

    def test_todas_las_claves_con_marcadores_se_pueden_formatear(self):
        for cod in ("en", "ru", "ja", "zh"):
            i18n.set_idioma(cod)
            for clave in self.tabla(cod):
                marcadores = {m: "X" for m in MARCADORES.findall(clave)}
                if marcadores:
                    self.assertNotIn("{", tr(clave, **marcadores), f"[{cod}] {clave!r}")

    def test_sin_traduccion_se_usa_ingles_y_luego_el_original(self):
        i18n.set_idioma("ja")
        self.assertEqual(tr("Navegador de Google."), "Google's browser.")
        self.assertEqual(tr("texto que no existe en ninguna tabla"), "texto que no existe en ninguna tabla")
        i18n.set_idioma("es")
        self.assertEqual(tr("Cancelar"), "Cancelar")

    def test_idioma_invalido_vuelve_a_espanol(self):
        i18n.set_idioma("klingon")
        self.assertEqual(i18n.idioma(), "es")

    def test_mensajes_dinamicos_del_motor_se_traducen_por_patron(self):
        i18n.set_idioma("en")
        self.assertEqual(tr("12 tareas activas"), "12 active tasks")
        self.assertEqual(tr("12.5 MB liberados"), "12.5 MB freed")
        self.assertEqual(tr("← Servicio de ubicación: 2 servicios ajustados"), "← Location service: 2 services adjusted")

    def test_un_patron_no_se_aplica_a_un_texto_cualquiera(self):
        i18n.set_idioma("ja")
        self.assertEqual(tr("Telemetría de Windows al mínimo"), "Windows telemetry to the minimum")

    def test_cada_idioma_declarado_tiene_su_tabla(self):
        for cod in i18n.IDIOMAS:
            if cod != "es":
                self.assertTrue(self.tabla(cod))


class PruebasTemas(unittest.TestCase):
    def test_las_dos_paletas_tienen_las_mismas_claves_y_colores_validos(self):
        self.assertEqual(set(temas.PALETAS["claro"]), set(temas.PALETAS["oscuro"]))
        for nombre, pal in temas.PALETAS.items():
            for k, v in pal.items():
                if isinstance(v, str):
                    self.assertRegex(v, r"^#[0-9a-fA-F]{6}$", f"{nombre}.{k}")
                else:
                    for vv in v.values():
                        self.assertRegex(vv, r"^#[0-9a-fA-F]{6}$")

    def test_el_texto_es_legible_sobre_el_fondo(self):
        def lum(h):
            r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

        def contraste(a, b):
            la, lb = sorted((lum(a), lum(b)), reverse=True)
            return (la + 0.05) / (lb + 0.05)
        for nombre, p in temas.PALETAS.items():
            for fg, bg in (("fg", "bg"), ("fg", "panel"), ("sub", "bg"), ("acento_fg", "acento"), ("ok", "panel"),
                           ("warn", "panel"), ("peligro", "panel")):
                self.assertGreaterEqual(contraste(p[fg], p[bg]), 4.5, f"{nombre}: {fg} sobre {bg}")


if __name__ == "__main__":
    unittest.main()
