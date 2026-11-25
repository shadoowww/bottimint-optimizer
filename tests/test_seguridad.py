"""Pruebas de seguridad: enlaces/junctions, rutas absolutas, manifiestos manipulados, inyección y validación de datos."""
import contextlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from bottimint import ajustes, confiables, instalador, limpieza, nucleo
from tests.falsos import EntornoFalso, WingetFalso


def _windows_falso(sr: str, perfil: str, pf: str = "", programdata: str = ""):
    """Hace que 'Windows' (la API de confiables) devuelva estas ubicaciones, sea cual sea el sistema y el entorno."""
    pila = contextlib.ExitStack()
    pila.enter_context(mock.patch.object(confiables, "windows_dir", return_value=sr))
    pila.enter_context(mock.patch.object(confiables, "system32", return_value=os.path.join(sr, "System32")))
    pila.enter_context(mock.patch.object(confiables, "unidad_sistema", return_value=os.path.splitdrive(sr)[0] or "C:"))
    datos = {"profile": perfil, "programfiles": pf, "programdata": programdata,
             "localappdata": os.path.join(perfil, "AppData", "Local") if perfil else ""}
    pila.enter_context(mock.patch.object(confiables, "carpeta", side_effect=lambda k: datos.get(k, "")))
    return pila


def _senuelo_en(carpeta: str, nombre: str = "zzsenuelo.exe") -> str:
    """Un ejecutable inofensivo (whoami) con otro nombre, para comprobar si algo lo ejecuta desde donde no debe."""
    destino = os.path.join(carpeta, nombre)
    shutil.copy(os.path.join(confiables.windows_dir(), "System32", "whoami.exe"), destino)
    return destino


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
        with mock.patch.object(limpieza, "IS_WIN", True), _windows_falso(raiz, tempfile.mkdtemp()):
            self.assertEqual(limpieza.resolver_exe("powershell"), os.path.join(ps, "powershell.exe"))
            self.assertEqual(limpieza.resolver_exe("sc"), os.path.join(sys32, "sc.exe"))
            self.assertEqual(limpieza.resolver_exe("sc.exe"), os.path.join(sys32, "sc.exe"))
            explicita = os.path.join(raiz, "otra", "y.exe")  # (no una ruta "C:\..." literal: en Linux no tiene directorio)
            self.assertEqual(limpieza.resolver_exe(explicita), explicita)      # respeta rutas explícitas

    def test_un_ejecutable_inexistente_nunca_se_devuelve_como_nombre_desnudo(self):
        """Un nombre sin ruta lo busca Windows en el directorio actual y en el PATH: siempre se devuelve ruta absoluta."""
        raiz = tempfile.mkdtemp()
        with mock.patch.object(limpieza, "IS_WIN", True), _windows_falso(raiz, tempfile.mkdtemp()):
            for nombre in ("noexiste", "winget", "powershell", "DISM"):
                r = limpieza.resolver_exe(nombre)
                self.assertTrue(os.path.isabs(r), f"{nombre} -> {r}")
                self.assertTrue(r.startswith(raiz) or "WindowsApps" in r, r)
        # fuera del "Windows falso": con IS_WIN=True en Linux, subprocess rechazaría creationflags (solo existe en Windows)
        self.assertEqual(limpieza.ejecutar([os.path.join(raiz, "System32", "noexiste.exe")])[0], 127)

    def test_winget_sin_perfil_conocido_no_cae_a_una_ruta_relativa(self):
        raiz = tempfile.mkdtemp()
        with mock.patch.object(limpieza, "IS_WIN", True), _windows_falso(raiz, ""):  # sin LOCALAPPDATA
            self.assertEqual(limpieza.resolver_exe("winget"), os.path.join(raiz, "System32", "winget.exe"))

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
        """Windows (la API) dice dónde está el sistema; las variables de entorno de un atacante no cuentan."""
        raiz = tempfile.mkdtemp()
        sr, perfil = os.path.join(raiz, "Windows"), os.path.join(raiz, "Users", "yo")
        pf = os.path.join(raiz, "Program Files")
        for d in (os.path.join(sr, "System32", "config"), os.path.join(perfil, "Documents"), os.path.join(perfil, "AppData", "Temp"),
                  os.path.join(pf, "App")):
            os.makedirs(d)
        falso = tempfile.mkdtemp()  # lo que dice el atacante: un "sistema" que no existe
        entorno = {"SystemRoot": falso, "windir": falso, "USERPROFILE": falso, "ProgramFiles": falso, "ProgramData": falso}
        with _windows_falso(sr, perfil, pf), mock.patch.dict(os.environ, entorno):
            self.assertTrue(limpieza._es_ruta_peligrosa(os.path.join(sr, "System32", "config")))
            self.assertTrue(limpieza._es_ruta_peligrosa(os.path.join(perfil, "Documents")))
            self.assertTrue(limpieza._es_ruta_peligrosa(os.path.join(pf, "App")))
            self.assertTrue(limpieza._es_ruta_peligrosa(perfil))
            self.assertFalse(limpieza._es_ruta_peligrosa(os.path.join(perfil, "AppData", "Temp")))
            self.assertEqual(limpieza.expandir([os.path.join(sr, "System32", "config")]), [])
            self.assertEqual(limpieza.expandir([os.path.join(perfil, "Documents")]), [])
            self.assertEqual(limpieza.env("SystemRoot"), sr)  # env() y join_env() también piden a Windows
            self.assertEqual(limpieza.join_env("SystemRoot", "Temp"), os.path.join(sr, "Temp"))

    def test_fuera_de_windows_se_siguen_usando_las_variables_de_entorno(self):
        raiz = tempfile.mkdtemp()
        with mock.patch.object(confiables, "IS_WIN", False), mock.patch.dict(os.environ, {"SystemRoot": raiz, "ProgramData": raiz}):
            self.assertEqual(confiables.windows_dir(), raiz)
            self.assertEqual(confiables.carpeta("programdata"), raiz)
            self.assertEqual(confiables.carpeta_de_datos(), os.path.join(raiz, "BottiMint"))

    def test_la_carpeta_de_datos_no_depende_de_la_variable_ProgramData(self):
        datos, falso = tempfile.mkdtemp(), tempfile.mkdtemp()
        with _windows_falso(tempfile.mkdtemp(), tempfile.mkdtemp(), programdata=datos), mock.patch.dict(os.environ, {"ProgramData": falso}):
            self.assertEqual(nucleo.Entorno().base_dir, os.path.join(datos, "BottiMint"))
            self.assertEqual(instalador.Winget().base_dir, os.path.join(datos, "BottiMint"))

    def test_ningun_modulo_decide_rutas_del_sistema_con_variables_de_entorno(self):
        """Guarda contra regresiones: SystemRoot, ProgramData, USERPROFILE... solo se leen en confiables.py."""
        patron = re.compile(r"os\.environ(?:\.get\(|\[)\s*[\"'](SystemRoot|windir|ProgramData|ProgramFiles(?:\(x86\))?|USERPROFILE|"
                            r"LOCALAPPDATA|SystemDrive)[\"']", re.I)
        base = os.path.dirname(limpieza.__file__)
        for nombre in os.listdir(base):
            if nombre.endswith(".py") and nombre != "confiables.py":
                with open(os.path.join(base, nombre), encoding="utf-8") as f:
                    codigo = f.read()
                self.assertIsNone(patron.search(codigo), f"{nombre} lee una variable de entorno que debe pedirse a confiables.py")

    def test_endurecer_proceso_excluye_el_directorio_actual(self):
        with mock.patch.object(confiables, "IS_WIN", True), mock.patch.dict(os.environ):
            os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)
            confiables.endurecer_proceso()
            self.assertEqual(os.environ.get("NoDefaultCurrentDirectoryInExePath"), "1")
        with mock.patch.object(confiables, "IS_WIN", False), mock.patch.dict(os.environ):
            os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)
            confiables.endurecer_proceso()  # fuera de Windows no hace nada
            self.assertNotIn("NoDefaultCurrentDirectoryInExePath", os.environ)



@unittest.skipUnless(os.name == "nt", "solo en Windows (en CI corre en windows-latest)")
class PruebasEntornoManipuladoReal(unittest.TestCase):
    """Con la API real de Windows: el entorno manipulado no cambia las rutas ni desprotege carpetas."""

    def test_la_api_ignora_un_entorno_manipulado(self):
        reales = {"win": confiables.windows_dir(), "sys32": confiables.system32(), "perfil": confiables.carpeta("profile"),
                  "pd": confiables.carpeta("programdata"), "pf": confiables.carpeta("programfiles"),
                  "docs": confiables.carpeta("documents")}
        falso = tempfile.mkdtemp()
        entorno = {v: falso for v in ("SystemRoot", "windir", "USERPROFILE", "ProgramData", "ProgramFiles", "LOCALAPPDATA")}
        with mock.patch.dict(os.environ, entorno):
            self.assertEqual(confiables.windows_dir(), reales["win"])
            self.assertEqual(confiables.system32(), reales["sys32"])
            self.assertEqual(confiables.carpeta("profile"), reales["perfil"])
            self.assertEqual(confiables.carpeta("programdata"), reales["pd"])
            self.assertEqual(confiables.carpeta("programfiles"), reales["pf"])
            self.assertEqual(confiables.carpeta("documents"), reales["docs"])
            # la limpieza sigue negándose a tocar el sistema y los archivos personales reales
            for ruta in (os.path.join(reales["sys32"], "drivers", "etc"), reales["docs"], reales["perfil"], reales["pf"]):
                self.assertTrue(limpieza._es_ruta_peligrosa(ruta), ruta)
                self.assertEqual(limpieza.expandir([ruta]), [], ruta)
            # y los comandos del sistema siguen saliendo del System32 real, no de uno falso
            self.assertTrue(limpieza.resolver_exe("powershell").lower().startswith(reales["win"].lower()))
            self.assertEqual(nucleo.Entorno().base_dir, os.path.join(reales["pd"], "BottiMint"))

    def test_el_directorio_actual_no_se_busca_para_ejecutar_comandos(self):
        carpeta = tempfile.mkdtemp()
        _senuelo_en(carpeta)
        anterior = os.getcwd()
        with mock.patch.dict(os.environ):
            os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)
            os.chdir(carpeta)
            try:
                try:  # control: sin la defensa, Windows SÍ ejecutaría el señuelo (si no, esta prueba no demostraría nada)
                    subprocess.run(["zzsenuelo"], capture_output=True, timeout=10)
                except FileNotFoundError:
                    self.skipTest("este entorno ya excluye el directorio actual de la búsqueda")
                self.assertEqual(limpieza.ejecutar(["zzsenuelo"], 10)[0], 127)  # ejecutar(): ruta absoluta, nunca el cwd
                confiables.endurecer_proceso()
                with self.assertRaises(FileNotFoundError):  # y con la defensa del proceso, ni el nombre desnudo
                    subprocess.run(["zzsenuelo"], capture_output=True, timeout=10)
            finally:
                os.chdir(anterior)

    def test_winget_plantado_en_el_directorio_actual_no_se_ejecuta(self):
        carpeta = tempfile.mkdtemp()
        _senuelo_en(carpeta, "winget.exe")
        anterior, real = os.getcwd(), confiables.carpeta
        # una cuenta de administrador distinta, sin winget instalado en su perfil
        sin_winget = lambda k: os.path.join(carpeta, "otro_perfil") if k == "localappdata" else real(k)  # noqa: E731
        with mock.patch.dict(os.environ), mock.patch.object(confiables, "carpeta", side_effect=sin_winget):
            os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)
            os.chdir(carpeta)
            try:
                self.assertFalse(os.path.isfile(limpieza.resolver_exe("winget")))
                self.assertTrue(os.path.isabs(limpieza.resolver_exe("winget")))
                cod, salida = limpieza.ejecutar(["winget", "--version"], 30)
                self.assertEqual(cod, 127, salida)  # no se ejecutó el winget.exe plantado en el directorio actual
            finally:
                os.chdir(anterior)


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
