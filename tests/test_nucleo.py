import json
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

    def test_profundo_limpia_inicio_y_xbox_pero_respeta_lo_protegido(self):
        env = EntornoFalso(tempfile.mkdtemp())
        nombres_ini = ["Microsoft.Office.OneNote", "Microsoft.WindowsMaps", "7EE7776C.LinkedInforWindows", "Microsoft.MSPaint",
                       "Microsoft.Copilot", "Microsoft.GamingApp", "Microsoft.XboxGamingOverlay", "Microsoft.XboxIdentityProvider",
                       "Microsoft.WindowsCamera", "Microsoft.WindowsCalculator", "Microsoft.Windows.Photos", "Microsoft.WindowsAlarms",
                       "Microsoft.ZuneMusic", "Microsoft.Paint", "Microsoft.MicrosoftEdge.Stable", "Microsoft.WindowsStore"]
        env.apps = [{"Name": n, "PackageFullName": f"{n}_1", "InstallLocation": "C:\\x"} for n in nombres_ini]
        plan = {p["id"]: p["seleccionado"] for p in nucleo.plan("profundo", env)}
        self.assertTrue(plan["apps_inicio"] and plan["apps_xbox"])
        self.assertFalse(plan["apps_extra"], "Cámara/Notas/Outlook son opcionales, no vienen marcadas")
        nucleo.aplicar("profundo", env, ["apps_inicio", "apps_xbox"], emitir=lambda s: None)
        quedan = {a["Name"] for a in env.apps}
        self.assertEqual(quedan, {"Microsoft.XboxIdentityProvider", "Microsoft.WindowsCamera", "Microsoft.WindowsCalculator",
                                  "Microsoft.Windows.Photos", "Microsoft.WindowsAlarms", "Microsoft.ZuneMusic", "Microsoft.Paint",
                                  "Microsoft.MicrosoftEdge.Stable", "Microsoft.WindowsStore"})

    def test_copilot_se_apaga_y_se_restaura(self):
        env = EntornoFalso(tempfile.mkdtemp())
        antes = env.instantanea()
        ses = nucleo.aplicar("profundo", env, ["reg_copilot"], emitir=lambda s: None)
        self.assertEqual(env.reg[("HKCU", r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot")][0], 1)
        self.assertEqual(env.reg[("HKCU", nucleo.W + r"\Explorer\Advanced", "ShowCopilotButton")][0], 0)
        self.assertTrue(nucleo.restaurar(env, ses, emitir=lambda s: None))
        self.assertEqual(antes, env.instantanea())

    def test_onedrive_no_viene_marcado_se_desinstala_y_se_reinstala_al_restaurar(self):
        env = EntornoFalso(tempfile.mkdtemp())
        plan = {p["id"]: p for p in nucleo.plan("profundo", env)}
        self.assertTrue(plan["onedrive"]["aplica"])
        self.assertFalse(plan["onedrive"]["seleccionado"], "OneDrive no se quita sin que el usuario lo marque")
        antes = env.instantanea()
        ses = nucleo.aplicar("profundo", env, ["onedrive"], emitir=lambda s: None)
        self.assertFalse(env.onedrive)
        self.assertEqual(env.reg[("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\OneDrive", "DisableFileSyncNGSC")][0], 1)
        self.assertTrue(any(c[:3] == ["taskkill", "/f", "/im"] for c in env.cmds))
        self.assertTrue(nucleo.restaurar(env, ses, emitir=lambda s: None))
        self.assertTrue(env.onedrive)
        self.assertEqual(antes, env.instantanea())

    def test_onedrive_no_se_toca_si_guarda_escritorio_y_documentos(self):
        env = EntornoFalso(tempfile.mkdtemp())
        env.reg[("HKCU", nucleo.W + r"\Explorer\User Shell Folders", "Desktop")] = (r"%USERPROFILE%\OneDrive\Escritorio", 2)
        plan = {p["id"]: p for p in nucleo.plan("profundo", env)}
        self.assertFalse(plan["onedrive"]["aplica"])
        self.assertTrue(env.onedrive)

    def test_si_windows_no_deja_quitar_una_app_se_informa(self):
        env = EntornoFalso(tempfile.mkdtemp())
        env.apps = [{"Name": "Microsoft.Copilot", "PackageFullName": "CP_1", "InstallLocation": "C:\\x"}]
        env.quitar_appx = lambda f: False
        ses = nucleo.aplicar("profundo", env, ["apps_inicio"], emitir=lambda s: None)
        self.assertTrue(ses)
        with open(os.path.join(env.base_dir, "sesiones", ses, "manifest.json"), encoding="utf-8") as f:
            entradas = [c for c in json.load(f)["cambios"] if c["id"] == "apps_inicio"]
        self.assertFalse(entradas[0]["ok"])
        self.assertIn("Microsoft.Copilot", entradas[0]["resultado"])
        self.assertEqual(len(env.apps), 1)

    def test_profundo_desancla_el_menu_inicio(self):
        env = EntornoFalso(tempfile.mkdtemp())
        plan = {p["id"]: p for p in nucleo.plan("profundo", env)}
        self.assertTrue(plan["inicio_pines"]["seleccionado"])
        ids = [c.id for c in nucleo.cambios_del_nivel("profundo")]
        self.assertGreater(ids.index("inicio_pines"), ids.index("apps_xbox"), "se desancla después de quitar las apps")
        nucleo.aplicar("profundo", env, ["inicio_pines"], emitir=lambda s: None)
        self.assertEqual(env.anclados, 0)

    def test_programas_de_inicio_quita_onedrive_y_edge_pero_deja_los_basicos(self):
        env = EntornoFalso(tempfile.mkdtemp())
        nucleo.aplicar("profundo", env, ["inicio_conocidos"], emitir=lambda s: None)
        estado = {e.nombre: e.habilitado for e in env.inicio}
        self.assertFalse(estado["OneDrive"])
        self.assertFalse(estado["MicrosoftEdgeAutoLaunch_AB12"])
        self.assertTrue(estado["SecurityHealth"] and estado["Realtek"], "antivirus y drivers no se tocan")

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
