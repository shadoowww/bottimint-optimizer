"""Pruebas de la ronda 1.3.4: carpeta de datos, valores del manifiesto, punto de restauración y cadena de publicación."""
import os
import re
import subprocess
import tempfile
import unittest
from unittest import mock

from bottimint import limpieza, nucleo
from tests.falsos import EntornoFalso

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _escribir(ruta: str, texto: str = "x") -> str:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return ruta


class PruebasCarpetaDeDatos(unittest.TestCase):
    """Se simula ser administrador y se registra cada llamada a icacls (sin cambiar permisos de verdad)."""

    def preparar(self, datos, codigo=0):
        llamadas = []

        def falso(cmd, timeout=None):
            llamadas.append(cmd)
            return codigo, "" if codigo == 0 else "Acceso denegado"
        with mock.patch.object(limpieza, "IS_WIN", True), mock.patch.object(limpieza, "is_admin", return_value=True), \
                mock.patch.object(limpieza, "ejecutar", side_effect=falso):
            limpieza.preparar_dir_datos(datos)
        return llamadas

    def test_se_asegura_tambien_lo_que_ya_habia_dentro_y_primero_la_carpeta_que_lo_contiene(self):
        datos = tempfile.mkdtemp()
        manifiesto = _escribir(os.path.join(datos, "sesiones", "20260101_000000", "manifest.json"))
        llamadas = self.preparar(datos)
        orden = [c[1] for c in llamadas if "/setowner" in c]
        esperados = [datos, os.path.join(datos, "sesiones"), os.path.dirname(manifiesto), manifiesto]
        self.assertEqual(orden, esperados)  # de arriba hacia abajo: nadie puede plantar algo en lo ya asegurado
        for ruta in esperados[1:]:
            self.assertTrue(any(c[1] == ruta and "/reset" in c for c in llamadas), ruta)
        for c in llamadas:
            self.assertEqual(c[-1], "/L", c)  # siempre sobre el propio elemento, nunca sobre el destino de un enlace
            self.assertNotIn("/T", c)  # nada de recursión de icacls: seguiría junctions

    def test_los_enlaces_se_quitan_y_nunca_reciben_permisos(self):
        datos = tempfile.mkdtemp()
        trampa = _escribir(os.path.join(datos, "sesiones", "trampa"))
        real = limpieza.es_enlace
        with mock.patch.object(limpieza, "es_enlace", side_effect=lambda p: p == trampa or real(p)):
            llamadas = self.preparar(datos)
        self.assertFalse(os.path.lexists(trampa))
        self.assertFalse(any(c[1] == trampa for c in llamadas))

    def test_un_enlace_duro_se_quita_sin_tocar_el_archivo_original(self):
        datos, ajena = tempfile.mkdtemp(), tempfile.mkdtemp()
        original = _escribir(os.path.join(ajena, "importante.txt"), "no tocar")
        duro = os.path.join(datos, "manifest.json")
        try:
            os.link(original, duro)
        except OSError:
            self.skipTest("este sistema de archivos no admite enlaces duros")
        llamadas = self.preparar(datos)
        self.assertFalse(os.path.exists(duro))
        with open(original, encoding="utf-8") as f:
            self.assertEqual(f.read(), "no tocar")
        self.assertFalse(any(c[1] in (duro, original) for c in llamadas))

    def test_si_no_se_pueden_asegurar_los_permisos_no_se_continua(self):
        with self.assertRaises(OSError):
            self.preparar(tempfile.mkdtemp(), codigo=5)


@unittest.skipUnless(os.name == "nt", "solo en Windows (en CI corre en windows-latest)")
class PruebasCarpetaDeDatosReal(unittest.TestCase):
    def test_una_junction_plantada_dentro_no_se_sigue(self):
        datos, victima = tempfile.mkdtemp(), tempfile.mkdtemp()
        archivo = _escribir(os.path.join(victima, "importante.txt"), "no tocar")
        junction = os.path.join(datos, "sesiones", "planta")
        os.makedirs(os.path.dirname(junction))
        r = subprocess.run(["cmd", "/c", "mklink", "/J", junction, victima], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        llamadas = PruebasCarpetaDeDatos.preparar(self, datos)
        self.assertFalse(os.path.lexists(junction))
        self.assertTrue(os.path.isfile(archivo))
        self.assertFalse(any(victima in c[1] or c[1] == junction for c in llamadas))

    def test_la_sintaxis_de_icacls_es_valida_en_este_windows(self):
        """Con icacls de verdad, sobre un archivo propio (no hace falta ser administrador)."""
        archivo = _escribir(os.path.join(tempfile.mkdtemp(), "a.txt"))
        salida = subprocess.run([limpieza.resolver_exe("whoami"), "/user", "/fo", "csv", "/nh"], capture_output=True)
        sid = re.search(rb"S-1-5-[0-9-]+", salida.stdout).group(0).decode()
        limpieza._icacls(archivo, "/setowner", "*" + sid)  # lanza OSError si icacls no acepta los argumentos
        limpieza._icacls(archivo, "/reset")

    @unittest.skipUnless(limpieza.is_admin(), "requiere administrador (los runners de Windows de la CI lo son)")
    def test_como_administrador_asegura_de_verdad_un_arbol_ya_existente(self):
        datos = tempfile.mkdtemp()
        manifiesto = _escribir(os.path.join(datos, "sesiones", "20260101_000000", "manifest.json"), "{}")
        limpieza.preparar_dir_datos(datos)
        with open(manifiesto, encoding="utf-8") as f:
            self.assertEqual(f.read(), "{}")  # un administrador lo sigue pudiendo leer


class PruebasValoresDelManifiesto(unittest.TestCase):
    def revertir(self, cambio_id, ruta_contiene, nombre, tipo, valor, existe=True):
        env = EntornoFalso(tempfile.mkdtemp())
        cambio = nucleo.POR_ID[cambio_id]
        hive, path, name, _t, _v = next(v for v in cambio.valores if v[2] == nombre and ruta_contiene in v[1])
        env.reg[(hive, path, name)] = ("ANTES", 1)
        texto = nucleo.CambioRegistro.revertir(cambio, env, {"valores": [
            {"hive": hive, "path": path, "name": name, "existe": existe, "tipo": tipo, "valor": valor}]})
        return env.reg.get((hive, path, name)), texto

    def test_un_valor_o_tipo_que_el_ajuste_no_puede_tener_no_se_escribe(self):
        numero = ("reg_gaming", "", nucleo.POR_ID["reg_gaming"].valores[0][2])
        malos = [(1, "texto"), (4, "texto"), (4, True), (4, -1), (4, 2 ** 32), (4, 1.5), (3, 1), (7, "a"), (11, 1),
                 (True, 1), ("4", 1)]
        for tipo, valor in malos:
            actual, texto = self.revertir(numero[0], numero[1], numero[2], tipo, valor)
            self.assertEqual(actual, ("ANTES", 1), (tipo, valor))
            self.assertIn("1 valores no válidos ignorados", texto)
        for tipo, valor in [(1, "a\x00b"), (1, "x" * 3000), (4, 5), (1, 5)]:
            actual, _ = self.revertir("reg_visual", "Desktop", "MenuShowDelay", tipo, valor)
            self.assertEqual(actual, ("ANTES", 1), (tipo, valor))

    def test_los_valores_legitimos_se_restauran(self):
        nombre = nucleo.POR_ID["reg_gaming"].valores[0][2]
        for valor in (0, 1, 0xFFFFFFFF):
            actual, texto = self.revertir("reg_gaming", "", nombre, 4, valor)
            self.assertEqual(actual, (valor, 4))
            self.assertNotIn("ignorados", texto)
        for tipo in (1, 2):  # texto normal o expandible
            actual, _ = self.revertir("reg_visual", "Desktop", "MenuShowDelay", tipo, "400")
            self.assertEqual(actual, ("400", tipo))

    def test_solo_un_existe_False_explicito_borra_un_valor(self):
        nombre = nucleo.POR_ID["reg_gaming"].valores[0][2]
        for raro in (0, "", None, "no"):
            actual, _ = self.revertir("reg_gaming", "", nombre, 4, None, existe=raro)
            self.assertEqual(actual, ("ANTES", 1), repr(raro))
        self.assertIsNone(self.revertir("reg_gaming", "", nombre, 4, None, existe=False)[0])

    def test_restaurar_inicio_no_reactiva_entradas_ajenas_al_cambio(self):
        env = EntornoFalso(tempfile.mkdtemp())
        for e in env.inicio:
            e.habilitado = False  # por ejemplo, las había desactivado el usuario o el antivirus
        estado = {"inicio": [{"nombre": e.nombre, "origen": e.origen} for e in env.inicio]}  # manifiesto alterado: todas
        nucleo.POR_ID["inicio_conocidos"].revertir(env, estado)
        activos = {e.nombre for e in env.inicio if e.habilitado}
        self.assertIn("Spotify", activos)
        self.assertNotIn("Realtek", activos)
        self.assertNotIn("SecurityHealth", activos)


class PruebasPuntoDeRestauracion(unittest.TestCase):
    def test_la_descripcion_va_escapada_en_powershell(self):
        scripts = []
        env = EntornoFalso(tempfile.mkdtemp())
        env.ps = lambda s, t=300: scripts.append(s) or (0, "1")
        nucleo.crear_punto_restauracion(env, "x'; Remove-Item C:\\ -Recurse; '", lambda m: None)
        con_texto = [s for s in scripts if "Remove-Item" in s]
        self.assertEqual(len(con_texto), 2)
        for s in con_texto:
            self.assertIn("'x''; Remove-Item C:\\ -Recurse; '''", s)


class PruebasCadenaDePublicacion(unittest.TestCase):
    """Guardas contra regresiones en los workflows (se leen como texto: sin dependencias externas)."""

    def workflows(self):
        carpeta = os.path.join(RAIZ_REPO, ".github", "workflows")
        for nombre in sorted(os.listdir(carpeta)):
            with open(os.path.join(carpeta, nombre), encoding="utf-8") as f:
                yield nombre, f.read()

    def test_todas_las_acciones_van_fijadas_por_commit(self):
        total = 0
        for nombre, texto in self.workflows():
            for linea in texto.splitlines():
                m = re.match(r"\s*(?:- )?uses:\s*(.+)$", linea)
                if m:
                    total += 1
                    self.assertRegex(m.group(1), r"^[\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$", f"{nombre}: {linea.strip()}")
        self.assertGreater(total, 8)

    def test_todos_los_workflows_parten_de_solo_lectura(self):
        for nombre, texto in self.workflows():
            m = re.search(r"^permissions:\n((?:[ ]{2}.*\n)+)", texto, re.M)
            self.assertIsNotNone(m, f"{nombre} no declara permisos")
            self.assertNotIn("write", m.group(1), nombre)

    def test_la_release_compila_sin_permisos_de_escritura_y_con_hashes(self):
        texto = dict(self.workflows())["release.yml"]
        compilar, publicar = texto.split("\n  publicar:")
        self.assertNotIn("write", compilar.split("jobs:")[1])
        self.assertIn("--require-hashes", compilar)
        self.assertNotIn("pip install", publicar)  # el trabajo con permisos no instala ni ejecuta nada del proyecto
        self.assertNotIn("actions/checkout", publicar)

    def test_cada_dependencia_de_compilacion_tiene_version_exacta_y_hash(self):
        with open(os.path.join(RAIZ_REPO, "requirements-build.txt"), encoding="utf-8") as f:
            unidas = f.read().replace("\\\n", " ")
        reqs = [x for x in unidas.splitlines() if x.strip() and not x.startswith("#")]
        self.assertTrue(any(x.startswith("pyinstaller==") for x in reqs))
        for r in reqs:
            self.assertRegex(r, r"^[A-Za-z0-9._-]+==[A-Za-z0-9.]+\s+--hash=sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
