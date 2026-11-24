import json
import os
import tempfile
import unittest

from bottimint import nucleo
from tests.falsos import EntornoFalso


def ids_sin_limpieza(env, nivel):
    """Los cambios que NO borran archivos reales (para no tocar el disco en las pruebas)."""
    return [x["id"] for x in nucleo.plan(nivel, env) if not x["id"].startswith("limp_")]


class PruebasNucleo(unittest.TestCase):
    def test_aplicar_y_restaurar_deja_todo_igual(self):
        env = EntornoFalso(tempfile.mkdtemp())
        antes = env.instantanea()
        sesion = nucleo.aplicar("extremo", env, ids_sin_limpieza(env, "extremo"), emitir=lambda s: None)
        self.assertTrue(sesion)
        self.assertTrue(env.puntos, "debe crear el punto de restauración")
        despues_aplicar = env.instantanea()
        self.assertNotEqual(antes, despues_aplicar)
        self.assertEqual(env.reg[("HKLM", nucleo.SVC_KEY + "Spooler", "Start")][0], 4)
        self.assertNotIn("DiagTrack", env.corriendo)
        self.assertTrue(nucleo.restaurar(env, sesion, emitir=lambda s: None))
        self.assertEqual(antes, env.instantanea())

    def test_apps_protegidas_no_se_tocan(self):
        env = EntornoFalso(tempfile.mkdtemp())
        nucleo.aplicar("profundo", env, ["apps_bloat"], emitir=lambda s: None)
        nombres = [a["Name"] for a in env.apps]
        self.assertEqual(nombres, ["Microsoft.WindowsStore"])

    def test_aborta_si_falla_el_punto_de_restauracion(self):
        env = EntornoFalso(tempfile.mkdtemp(), punto_ok=False)
        antes = env.instantanea()
        self.assertIsNone(nucleo.aplicar("profundo", env, ids_sin_limpieza(env, "profundo"), emitir=lambda s: None))
        self.assertEqual(antes, env.instantanea())

    def test_exige_administrador(self):
        env = EntornoFalso(tempfile.mkdtemp(), admin=False)
        self.assertIsNone(nucleo.aplicar("basico", env, None, emitir=lambda s: None))

    def test_opciones_dependen_del_equipo(self):
        env = EntornoFalso(tempfile.mkdtemp())
        sel = {p["id"]: p["seleccionado"] for p in nucleo.plan("extremo", env, {"media": "SSD", "bateria": True, "impresoras": 1})}
        self.assertTrue(sel["svc_sysmain"])
        self.assertFalse(sel["energia"], "en notebook no se sugiere alto rendimiento")
        self.assertFalse(sel["svc_impresion"], "con impresora no se desactiva el spooler")
        self.assertFalse(sel["svc_xbox"])

    def test_niveles_son_acumulativos(self):
        env = EntornoFalso(tempfile.mkdtemp())
        b, p, e = (set(x["id"] for x in nucleo.plan(n, env)) for n in nucleo.ORDEN)
        self.assertTrue(b < p < e)

    def test_extremo_quita_animaciones_deja_fondo_negro_y_conserva_cleartype(self):
        env = EntornoFalso(tempfile.mkdtemp())
        sesion = nucleo.aplicar("extremo", env, ["anim_ui", "fondo_negro", "reg_visual"], emitir=lambda s: None)
        for clave, get, _s, _v, deseado in nucleo.SPI_AJUSTES:
            self.assertEqual(env.spi[get], deseado, clave)
        self.assertEqual(env.spi[0x004A], 1, "el suavizado de letras debe quedar ACTIVO")
        self.assertEqual(env.spi[0x200A], 2, "debe quedar ClearType")
        self.assertEqual(env.reg[("HKCU", r"Control Panel\Desktop", "WallPaper")][0], "")
        self.assertEqual(env.reg[("HKCU", r"Control Panel\Colors", "Background")][0], "0 0 0")
        self.assertEqual(env.fondos[-1], ("", (0, 0, 0)))
        self.assertTrue(nucleo.restaurar(env, sesion, emitir=lambda s: None))
        self.assertEqual(env.reg[("HKCU", r"Control Panel\Desktop", "WallPaper")][0], "C:\\Users\\x\\foto.jpg")
        self.assertEqual(env.fondos[-1], ("C:\\Users\\x\\foto.jpg", (10, 20, 30)))
        self.assertEqual(env.spi[0x103E], 1)
        self.assertEqual(env.spi[0x200A], 1)

    def test_manifest_manipulado_no_cambia_ajustes_ajenos_ni_pone_fondos_raros(self):
        env = EntornoFalso(tempfile.mkdtemp())
        sesion = nucleo.aplicar("extremo", env, ["anim_ui", "fondo_negro"], emitir=lambda s: None)
        ruta = os.path.join(env.base_dir, "sesiones", sesion, "manifest.json")
        with open(ruta, encoding="utf-8") as f:
            m = json.load(f)
        for c in m["cambios"]:
            if c["id"] == "anim_ui":
                c["estado"]["spi"].append({"clave": "algo_inventado", "valor": 1})
                c["estado"]["spi"].append({"clave": "menu_anim", "valor": 99})
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(m, f)
        env.reg[("HKCU", r"Control Panel\Desktop", "WallPaper")] = (r"\\atacante\share\x.jpg", 1)  # el registro dice una ruta UNC
        nucleo.restaurar(env, sesion, emitir=lambda s: None)
        self.assertEqual(env.spi[0x1002], 1, "un valor inválido del manifiesto no se aplica")
        for ruta_fondo, _c in env.fondos:
            self.assertFalse(ruta_fondo.startswith("\\\\"), "nunca se aplica una ruta de red como fondo")

    def test_manifest_se_guarda_y_lista_sesiones(self):
        env = EntornoFalso(tempfile.mkdtemp())
        nucleo.aplicar("profundo", env, ["reg_sugerencias"], emitir=lambda s: None)
        ses = nucleo.listar_sesiones(env)
        self.assertEqual(len(ses), 1)
        self.assertFalse(ses[0]["restaurada"])
        self.assertTrue(os.path.isfile(os.path.join(env.base_dir, "sesiones", ses[0]["sesion"], "informe.txt")))


if __name__ == "__main__":
    unittest.main()
