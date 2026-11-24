"""Pruebas de seguridad: enlaces/junctions, rutas absolutas, manifiestos manipulados, inyección y validación de datos."""
import json
import os
import tempfile
import unittest
from unittest import mock

from bottimint import ajustes, instalador, limpieza, nucleo
from tests.falsos import EntornoFalso, WingetFalso


class PruebasEnlaces(unittest.TestCase):
    def test_no_entra_a_carpetas_que_son_enlaces_aunque_sean_junctions(self):
        """En Windows una junction NO es symlink para os.walk: se simula marcando una carpeta como reparse point."""
        victima = tempfile.mkdtemp()
        with open(os.path.join(victima, "importante.txt"), "w") as f:
            f.write("no borrar")
        objetivo = tempfile.mkdtemp()
        falsa_junction = os.path.join(objetivo, "junction")
        os.makedirs(falsa_junction)
        with open(os.path.join(falsa_junction, "doc.txt"), "w") as f:
            f.write("dentro de la 'junction'")
        with open(os.path.join(objetivo, "temporal.tmp"), "w") as f:
            f.write("basura")
        original = limpieza.es_enlace
        with mock.patch.object(limpieza, "es_enlace", side_effect=lambda p: p == falsa_junction or original(p)):
            limpieza.limpiar_rutas([objetivo])
        self.assertFalse(os.path.exists(os.path.join(objetivo, "temporal.tmp")))
        self.assertTrue(os.path.exists(os.path.join(falsa_junction, "doc.txt")), "no debe vaciar el destino de una junction")
        self.assertTrue(os.path.exists(os.path.join(victima, "importante.txt")))

    def test_raiz_de_limpieza_que_es_enlace_se_ignora(self):
        real = tempfile.mkdtemp()
        with open(os.path.join(real, "a.txt"), "w") as f:
            f.write("x")
        enlace = os.path.join(tempfile.mkdtemp(), "tmp")
        try:
            os.symlink(real, enlace, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("sin permiso para crear symlinks")
        self.assertEqual(limpieza.limpiar_rutas([enlace]), (0, 0))
        self.assertTrue(os.path.exists(os.path.join(real, "a.txt")))

    def test_carpeta_de_datos_que_es_enlace_se_rechaza(self):
        real = tempfile.mkdtemp()
        enlace = os.path.join(tempfile.mkdtemp(), "BottiMint")
        try:
            os.symlink(real, enlace, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("sin permiso para crear symlinks")
        with self.assertRaises(OSError):
            limpieza.preparar_dir_datos(enlace)

    def test_carpeta_de_datos_normal_se_crea(self):
        ruta = os.path.join(tempfile.mkdtemp(), "BottiMint")
        self.assertEqual(limpieza.preparar_dir_datos(ruta), ruta)
        self.assertTrue(os.path.isdir(ruta))


class PruebasEjecutables(unittest.TestCase):
    def test_en_windows_se_usan_rutas_absolutas_de_system32(self):
        raiz = tempfile.mkdtemp()
        sys32 = os.path.join(raiz, "System32")
        ps = os.path.join(sys32, "WindowsPowerShell", "v1.0")
        os.makedirs(ps)
        for ruta in (os.path.join(ps, "powershell.exe"), os.path.join(sys32, "sc.exe")):
            open(ruta, "w").close()
        with mock.patch.object(limpieza, "IS_WIN", True), mock.patch.dict(os.environ, {"SystemRoot": raiz}):
            self.assertEqual(limpieza.resolver_exe("powershell"), os.path.join(ps, "powershell.exe"))
            self.assertEqual(limpieza.resolver_exe("sc"), os.path.join(sys32, "sc.exe"))
            self.assertEqual(limpieza.resolver_exe("sc.exe"), os.path.join(sys32, "sc.exe"))
            self.assertEqual(limpieza.resolver_exe("noexiste"), "noexiste")           # no inventa rutas
            self.assertEqual(limpieza.resolver_exe(r"C:\x\y.exe"), r"C:\x\y.exe")      # respeta rutas explícitas

    def test_fuera_de_windows_no_se_toca(self):
        with mock.patch.object(limpieza, "IS_WIN", False):
            self.assertEqual(limpieza.resolver_exe("powershell"), "powershell")

    def test_no_se_usa_shell_true_en_ninguna_parte(self):
        base = os.path.dirname(limpieza.__file__)
        for nombre in os.listdir(base):
            if nombre.endswith(".py"):
                with open(os.path.join(base, nombre), encoding="utf-8") as f:
                    codigo = f.read()
                self.assertNotIn("shell=True", codigo, nombre)
                self.assertNotIn("os.system(", codigo, nombre)
                self.assertNotIn("eval(", codigo, nombre)
                self.assertNotIn("pickle", codigo, nombre)


class PruebasInyeccion(unittest.TestCase):
    def test_ps_str_duplica_las_comillas(self):
        self.assertEqual(nucleo.ps_str("a'b"), "'a''b'")
        self.assertEqual(nucleo.ps_str("x'; Remove-Item C:\\ -Recurse; '"), "'x''; Remove-Item C:\\ -Recurse; '''")

    def test_ids_de_winget_con_opciones_o_espacios_se_rechazan(self):
        for malo in ("--source evil", "-h", "a b", "x;y", "x&y", "", "a|b", "$(calc)", "x\ny", "a" * 200):
            self.assertFalse(instalador.id_valido(malo), malo)
        for bueno in ("Valve.Steam", "Notepad++.Notepad++", "Python.Python.3.13", "7zip.7zip"):
            self.assertTrue(instalador.id_valido(bueno), bueno)

    def test_todo_el_catalogo_tiene_ids_validos(self):
        for p in instalador.CATALOGO:
            self.assertTrue(instalador.id_valido(p.id), p.id)

    def test_instalar_un_id_malicioso_no_ejecuta_nada(self):
        falso = WingetFalso()
        wg = instalador.Winget(falso, tempfile.mkdtemp())
        self.assertEqual(wg.instalar("--accept-source-agreements")[0], "error")
        self.assertFalse(wg.existe("-h"))
        self.assertEqual(falso.log, [])

    def test_appx_con_nombre_o_ruta_peligrosa_no_se_ejecuta(self):
        env = EntornoFalso(tempfile.mkdtemp())
        reales = nucleo.Entorno(tempfile.mkdtemp())
        reales.ps = mock.Mock(return_value=(0, ""))
        self.assertFalse(reales.quitar_appx("x'; calc; '"))
        self.assertFalse(reales.registrar_appx(r"C:\Users\Public\evil"))
        self.assertFalse(reales.registrar_appx("C:\\Program Files\\WindowsApps\\ok'; calc; '"))
        reales.ps.assert_not_called()
        self.assertIsNotNone(env)


class PruebasManifiesto(unittest.TestCase):
    def _sesion_con(self, env, cambios, nivel="profundo"):
        sesion = "20250101_000000"
        carpeta = os.path.join(env.base_dir, "sesiones", sesion)
        os.makedirs(carpeta)
        with open(os.path.join(carpeta, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"sesion": sesion, "nivel": nivel, "restaurada": False, "cambios": cambios}, f)
        return sesion

    def test_un_manifiesto_manipulado_no_puede_tocar_el_registro_ajeno(self):
        env = EntornoFalso(tempfile.mkdtemp())
        ajeno = ("HKLM", r"SYSTEM\CurrentControlSet\Services\WinDefend", "Start")
        env.reg[ajeno] = (2, 4)
        sesion = self._sesion_con(env, [{"id": "reg_sugerencias", "titulo": "x", "estado": {"valores": [
            {"hive": ajeno[0], "path": ajeno[1], "name": ajeno[2], "existe": True, "valor": 4, "tipo": 4}]}}])
        nucleo.restaurar(env, sesion, emitir=lambda s: None)
        self.assertEqual(env.reg[ajeno], (2, 4), "el valor ajeno debe quedar intacto")

    def test_un_manifiesto_no_puede_restaurar_servicios_o_tareas_que_el_cambio_no_toca(self):
        env = EntornoFalso(tempfile.mkdtemp())
        sesion = self._sesion_con(env, [
            {"id": "svc_telemetria", "titulo": "x", "estado": {"servicios": [{"nombre": "WinDefend", "start": 4, "corriendo": False}]}},
            {"id": "tareas_telemetria", "titulo": "y", "estado": {"tareas": [{"ruta": "\\Evil\\", "nombre": "Tarea"}]}}])
        antes = env.instantanea()
        nucleo.restaurar(env, sesion, emitir=lambda s: None)
        self.assertEqual(antes, env.instantanea())
        self.assertNotIn(["sc", "start", "WinDefend"], env.cmds)

    def test_guid_de_energia_invalido_se_ignora(self):
        env = EntornoFalso(tempfile.mkdtemp())
        cambio = nucleo.POR_ID["energia_alto"] if "energia_alto" in nucleo.POR_ID else next(
            c for c in nucleo.POR_ID.values() if isinstance(c, nucleo.CambioEnergia))
        cambio.revertir(env, {"guid": "x & calc"})
        self.assertFalse([c for c in env.cmds if "/setactive" in c])

    def test_id_de_sesion_con_ruta_se_rechaza(self):
        env = EntornoFalso(tempfile.mkdtemp())
        mensajes = []
        self.assertFalse(nucleo.restaurar(env, "..\\..\\Windows", emitir=mensajes.append))
        self.assertFalse(nucleo.restaurar(env, "../../etc", emitir=mensajes.append))

    def test_manifiesto_corrupto_o_con_forma_invalida_no_rompe(self):
        env = EntornoFalso(tempfile.mkdtemp())
        for contenido in ("{no es json", "[]", json.dumps({"nivel": "otro", "cambios": []}),
                          json.dumps({"nivel": "basico", "cambios": [1, 2]})):
            carpeta = os.path.join(env.base_dir, "sesiones", "20250101_000001")
            os.makedirs(carpeta, exist_ok=True)
            with open(os.path.join(carpeta, "manifest.json"), "w", encoding="utf-8") as f:
                f.write(contenido)
            self.assertEqual(nucleo.listar_sesiones(env), [])
            self.assertFalse(nucleo.restaurar(env, "20250101_000001", emitir=lambda s: None))

    def test_el_manifiesto_se_guarda_de_forma_atomica(self):
        env = EntornoFalso(tempfile.mkdtemp())
        sesion = nucleo.aplicar("profundo", env, ["reg_sugerencias"], emitir=lambda s: None)
        carpeta = os.path.join(env.base_dir, "sesiones", sesion)
        self.assertEqual(sorted(x for x in os.listdir(carpeta) if x.startswith("manifest")), ["manifest.json"])


class PruebasAjustes(unittest.TestCase):
    def test_valores_desconocidos_se_ignoran(self):
        ruta = os.path.join(tempfile.mkdtemp(), "a.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"idioma": "../../x", "tema": "<script>", "otro": 1}, f)
        cfg = ajustes.cargar(ruta)
        self.assertIn(cfg["idioma"], ajustes.IDIOMAS_VALIDOS)
        self.assertIn(cfg["tema"], ajustes.TEMAS_VALIDOS)

    def test_archivo_corrupto_no_rompe(self):
        ruta = os.path.join(tempfile.mkdtemp(), "a.json")
        with open(ruta, "w") as f:
            f.write("{{{")
        self.assertIn(ajustes.cargar(ruta)["tema"], ajustes.TEMAS_VALIDOS)

    def test_guardar_rechaza_valores_invalidos_y_guarda_los_validos(self):
        ruta = os.path.join(tempfile.mkdtemp(), "sub", "a.json")
        self.assertIsNone(ajustes.guardar("klingon", "claro", ruta))
        self.assertIsNone(ajustes.guardar("es", "rojo", ruta))
        self.assertEqual(ajustes.guardar("ja", "claro", ruta), ruta)
        self.assertEqual(ajustes.cargar(ruta), {"idioma": "ja", "tema": "claro"})

    def test_no_se_guardan_datos_personales(self):
        ruta = os.path.join(tempfile.mkdtemp(), "a.json")
        ajustes.guardar("en", "oscuro", ruta)
        with open(ruta, encoding="utf-8") as f:
            self.assertEqual(set(json.load(f)), {"idioma", "tema"})


class PruebasRutasProtegidas(unittest.TestCase):
    def test_una_variable_de_entorno_manipulada_no_apunta_la_limpieza_a_carpetas_criticas(self):
        raiz = tempfile.mkdtemp()
        sr, perfil = os.path.join(raiz, "Windows"), os.path.join(raiz, "Users", "yo")
        for d in (os.path.join(sr, "System32", "config"), os.path.join(perfil, "Documents"), os.path.join(perfil, "AppData", "Temp"),
                  os.path.join(raiz, "Program Files", "App")):
            os.makedirs(d)
        with mock.patch.dict(os.environ, {"SystemRoot": sr, "USERPROFILE": perfil, "ProgramFiles": os.path.join(raiz, "Program Files")}):
            self.assertTrue(limpieza._es_ruta_peligrosa(os.path.join(sr, "System32", "config")))
            self.assertTrue(limpieza._es_ruta_peligrosa(os.path.join(perfil, "Documents")))
            self.assertTrue(limpieza._es_ruta_peligrosa(os.path.join(raiz, "Program Files", "App")))
            self.assertTrue(limpieza._es_ruta_peligrosa(perfil))
            self.assertFalse(limpieza._es_ruta_peligrosa(os.path.join(perfil, "AppData", "Temp")))
            self.assertEqual(limpieza.expandir([os.path.join(sr, "System32", "config")]), [])



@unittest.skipUnless(os.name == "nt", "solo en Windows (en CI corre en windows-latest)")
class PruebasJunctionReal(unittest.TestCase):
    """Con una junction REAL de Windows (mklink /J): la limpieza no debe vaciar el destino."""

    def test_limpieza_no_sigue_una_junction_real(self):
        import subprocess
        victima = tempfile.mkdtemp()
        with open(os.path.join(victima, "importante.txt"), "w") as f:
            f.write("no borrar")
        objetivo = tempfile.mkdtemp()
        junction = os.path.join(objetivo, "enlace")
        r = subprocess.run(["cmd", "/c", "mklink", "/J", junction, victima], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(limpieza.es_enlace(junction))
        limpieza.limpiar_rutas([objetivo])
        self.assertTrue(os.path.exists(os.path.join(victima, "importante.txt")), "la junction fue seguida: se borró el destino")
        self.assertFalse(os.path.lexists(junction), "el enlace en sí debería haberse eliminado")


if __name__ == "__main__":
    unittest.main()
