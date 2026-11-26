import os
import tempfile
import unittest
from collections import Counter

from bottimint import instalador
from tests.falsos import WingetFalso


class PruebasInstalador(unittest.TestCase):
    def setUp(self):
        self.run = WingetFalso()
        self.wg = instalador.Winget(self.run, tempfile.mkdtemp())

    def test_catalogo_consistente(self):
        ids = [p.id for p in instalador.CATALOGO]
        self.assertEqual(len(ids), len(set(ids)), "IDs duplicados")
        for perfil in instalador.PERFILES.values():
            for i in perfil["ids"]:
                self.assertIn(i, instalador.POR_ID)

    def test_instalar_winget_registrandolo_si_ya_venia_con_windows(self):
        run = WingetFalso(presente=False, registra=True)
        self.assertTrue(instalador.Winget(run, tempfile.mkdtemp()).instalar_winget(lambda m: None))
        self.assertFalse(any("msixbundle" in " ".join(c) for c in run.log), "no hace falta descargar si alcanza con registrarlo")

    def test_instalar_winget_descargandolo_si_no_esta(self):
        run = WingetFalso(presente=False, descarga_ok=True)
        self.assertTrue(instalador.Winget(run, tempfile.mkdtemp()).instalar_winget(lambda m: None))
        self.assertTrue(any("msixbundle" in " ".join(c) for c in run.log))

    def test_instalar_winget_informa_si_falla(self):
        run, msgs = WingetFalso(presente=False), []
        self.assertFalse(instalador.Winget(run, tempfile.mkdtemp()).instalar_winget(msgs.append))
        self.assertTrue(any("Microsoft Store" in m for m in msgs))

    def test_script_de_winget_solo_usa_servidores_oficiales_de_microsoft(self):
        import re
        urls = re.findall(r"https://([^/\s\"']+)(/[^\s\"']*)", instalador.SCRIPT_INSTALAR_WINGET)
        self.assertGreaterEqual(len(urls), 3)
        for host, ruta in urls:
            self.assertIn(host, ("aka.ms", "github.com"))
            if host == "github.com":
                self.assertTrue(ruta.startswith("/microsoft/"), ruta)
        self.assertIn("CN=Microsoft Corporation", instalador.SCRIPT_INSTALAR_WINGET)

    def test_la_firma_de_los_tres_paquetes_se_comprueba_antes_de_instalar(self):
        s = instalador.SCRIPT_INSTALAR_WINGET
        comprobacion = s.index("Get-AuthenticodeSignature")
        self.assertLess(s.rindex("Invoke-WebRequest"), comprobacion)  # después de descargar todo
        self.assertLess(comprobacion, s.index("Add-AppxPackage"))  # y antes de instalar nada
        self.assertIn("@($wg, $vc, $xaml)", s)
        self.assertIn("$firma.Status -ne 'Valid'", s)
        self.assertIn("O=Microsoft Corporation(,|$)", s)
        self.assertIn("throw", s[comprobacion:s.index("Add-AppxPackage")])

    def test_perfiles_combinados_sin_duplicados(self):
        ids = instalador.ids_de(["gamer", "oficina"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_plan_marca_lo_instalado(self):
        pl = {x["id"]: x for x in instalador.plan(["Google.Chrome", "7zip.7zip"], self.wg)}
        self.assertTrue(pl["Google.Chrome"]["instalado"])
        self.assertFalse(pl["Google.Chrome"]["seleccionado"])
        self.assertTrue(pl["7zip.7zip"]["seleccionado"])

    def test_estados_de_instalacion(self):
        ids = ["Google.Chrome", "Valve.Steam", "Discord.Discord", "Microsoft.DotNet.DesktopRuntime.9", "7zip.7zip"]
        res = {r["id"]: r["estado"] for r in instalador.instalar_lote(ids, self.wg, emitir=lambda s: None)}
        self.assertEqual(res, {"Google.Chrome": "ya", "Valve.Steam": "reinicio", "Discord.Discord": "error",
                               "Microsoft.DotNet.DesktopRuntime.9": "no_existe", "7zip.7zip": "ok"})
        self.assertTrue(os.listdir(os.path.join(self.wg.base_dir, "instalaciones")))

    def test_sin_winget_no_instala_nada(self):
        wg = instalador.Winget(lambda c, t=None: (127, "no existe"), tempfile.mkdtemp())
        self.assertEqual(instalador.instalar_lote(["Valve.Steam"], wg, emitir=lambda s: None), [])

    def test_instalacion_usa_fuente_oficial_y_id_exacto(self):
        instalador.instalar_lote(["7zip.7zip"], self.wg, emitir=lambda s: None)
        inst = [c for c in self.run.log if c[:2] == ["winget", "install"]][0]
        for flag in ("--exact", "--silent", "--source", "winget", "--disable-interactivity"):
            self.assertIn(flag, inst)


if __name__ == "__main__":
    unittest.main()
