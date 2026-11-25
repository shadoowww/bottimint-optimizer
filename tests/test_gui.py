"""Prueba de humo de la interfaz: solo corre si hay tkinter y pantalla (en CI se usa xvfb)."""
import gc
import os
import tempfile
import unittest

try:
    import tkinter
    tkinter.Tk().destroy()
    HAY_PANTALLA = True
except Exception:
    HAY_PANTALLA = False

from tests.falsos import EntornoFalso, WingetFalso  # noqa: E402


@unittest.skipUnless(HAY_PANTALLA, "sin tkinter o sin pantalla")
class PruebasGui(unittest.TestCase):
    def esperar(self, app, cond, seg=10):
        import time
        fin = time.time() + seg
        while time.time() < fin:
            app.update()
            if cond():
                return True
            time.sleep(0.05)
        return False

    def setUp(self):
        from bottimint import gui, instalador
        from bottimint import ajustes
        self.env = EntornoFalso(tempfile.mkdtemp())
        self.ruta_aj = os.path.join(tempfile.mkdtemp(), "ajustes.json")
        ajustes.guardar("es", "oscuro", self.ruta_aj)  # idioma y tema fijos para que las pruebas sean deterministas
        self.app = gui.App(self.env, instalador.Winget(WingetFalso(), tempfile.mkdtemp()), ruta_ajustes=self.ruta_aj)
        self.app.pedir_confirmacion = lambda *a, **k: True
        self.app.aviso = lambda *a, **k: None
        self.app.preguntar = lambda *a, **k: True
        self.assertTrue(self.esperar(self.app, lambda: not self.app.busy and self.app.plan_actual and self.app.instalados))

    def tearDown(self):
        from bottimint import i18n
        i18n.set_idioma("es")
        self.app.destroy()
        self.app = None
        gc.collect()  # que las variables de Tk se liberen en el hilo principal, no en un hilo de trabajo

    def test_sin_winget_ofrece_instalarlo_y_el_aviso_desaparece_al_instalar(self):
        from bottimint import gui, instalador, ajustes
        run = WingetFalso(presente=False, registra=True)
        app = gui.App(EntornoFalso(tempfile.mkdtemp()), instalador.Winget(run, tempfile.mkdtemp()), ruta_ajustes=self.ruta_aj)
        try:
            app.preguntar = lambda *a, **k: True
            app.aviso = lambda *a, **k: None
            self.assertTrue(self.esperar(app, lambda: not app.busy and app.plan_actual))
            self.assertFalse(app.winget_ok)
            self.assertTrue(app.fr_winget.winfo_manager(), "el aviso con el botón debe verse")
            self.assertTrue(app.btn_winget.winfo_manager())
            app._instalar_winget()
            self.assertTrue(self.esperar(app, lambda: app.winget_ok and not app.busy))
            self.assertFalse(app.fr_winget.winfo_manager(), "con winget instalado el aviso desaparece")
            self.assertFalse(app.btn_winget.winfo_manager())
        finally:
            app.destroy()
            gc.collect()

    def test_instalar_programas_sin_winget_ofrece_instalarlo_en_vez_de_solo_avisar(self):
        from bottimint import gui, instalador
        run = WingetFalso(presente=False, registra=True)
        app = gui.App(EntornoFalso(tempfile.mkdtemp()), instalador.Winget(run, tempfile.mkdtemp()), ruta_ajustes=self.ruta_aj)
        try:
            preguntas = []
            app.preguntar = lambda titulo, *a, **k: preguntas.append(titulo) or False
            app.aviso = lambda *a, **k: None
            self.assertTrue(self.esperar(app, lambda: not app.busy and app.plan_actual))
            app.lista_prog.marcar(["7zip.7zip"], True)
            app._instalar()
            self.assertIn("Instalar winget", preguntas)
        finally:
            app.destroy()
            gc.collect()

    def test_el_titulo_muestra_la_version(self):
        from bottimint import __version__
        self.assertIn(__version__, self.app.title())

    def test_arranca_y_carga_plan_e_instalados(self):
        self.assertTrue(self.app.lista_opt.marcados())
        self.assertIn("google.chrome", self.app.instalados)
        self.assertEqual(self.app.vars_info["Permisos"].get(), "Administrador")

    def test_elegir_nivel_no_aplica_nada_y_el_boton_sigue_a_las_casillas(self):
        app = self.app
        app.pedir_confirmacion = lambda *a, **k: self.fail("elegir un nivel no debe pedir ni aplicar nada")
        app.nivel.set("profundo")
        app._cambio_nivel()
        self.assertTrue(self.esperar(app, lambda: not app.busy and app.lista_opt.marcados()))
        self.assertEqual(str(app.btn_aplicar.cget("state")), "normal")
        app.lista_opt.marcar_todo(False)
        self.assertEqual(str(app.btn_aplicar.cget("state")), "disabled")
        self.assertIn("0 de", app.lbl_cuenta.cget("text"))
        app.lista_opt.marcar_todo(True)
        self.assertEqual(str(app.btn_aplicar.cget("state")), "normal")

    def test_cambiar_de_nivel_reutiliza_lo_evaluado_y_actualizar_vuelve_a_consultar(self):
        from bottimint import gui, instalador, nucleo

        class Contador(EntornoFalso):
            apps = 0

            def listar_appx(self, ubicacion=True):
                Contador.apps += 1
                return super().listar_appx(ubicacion)
        Contador.apps = 0
        app = gui.App(Contador(tempfile.mkdtemp()), instalador.Winget(WingetFalso(), tempfile.mkdtemp()), ruta_ajustes=self.ruta_aj)
        try:
            app.aviso = lambda *a, **k: None
            self.assertTrue(self.esperar(app, lambda: not app.busy and app.plan_actual and app.instalados))
            self.assertEqual(Contador.apps, 0)  # Básico no consulta las apps
            for nivel in ("profundo", "extremo", "basico", "profundo", "extremo"):
                app.nivel.set(nivel)
                app._cambio_nivel()
                esperado = len(nucleo.cambios_del_nivel(nivel))
                self.assertTrue(self.esperar(app, lambda: not app.busy and len(app.plan_actual) == esperado), nivel)
            self.assertEqual(Contador.apps, 1)  # una sola consulta en toda la sesión, no una por cada cambio de nivel
            app._refrescar_plan()  # «Actualizar vista previa»: fuerza volver a mirar el equipo
            self.assertTrue(self.esperar(app, lambda: not app.busy and Contador.apps == 2))
        finally:
            app.destroy()
            gc.collect()

    def test_la_carga_inicial_detecta_los_programas_instalados_una_sola_vez(self):
        from bottimint import gui, instalador
        run = WingetFalso()
        app = gui.App(EntornoFalso(tempfile.mkdtemp()), instalador.Winget(run, tempfile.mkdtemp()), ruta_ajustes=self.ruta_aj)
        try:
            self.assertTrue(self.esperar(app, lambda: not app.busy and app.plan_actual and app.instalados))
            self.esperar(app, lambda: False, 0.5)  # margen por si hubiera una segunda detección pendiente
            self.assertEqual(sum(1 for c in run.log if c[:2] == ["winget", "export"]), 1)
            self.assertIn("google.chrome", app.instalados)
        finally:
            app.destroy()
            gc.collect()

    def test_cambiar_de_nivel_recarga_el_plan(self):
        n_basico = len(self.app.plan_actual)
        self.app.nivel.set("extremo")
        self.app._cambio_nivel()
        self.assertTrue(self.esperar(self.app, lambda: not self.app.busy and len(self.app.plan_actual) > n_basico))

    def test_aplicar_y_restaurar_desde_la_interfaz(self):
        self.app.nivel.set("profundo")
        self.app._cambio_nivel()
        self.esperar(self.app, lambda: not self.app.busy and any(p["id"] == "reg_sugerencias" for p in self.app.plan_actual))
        antes = self.env.instantanea()
        self.app.lista_opt.marcar_todo(False)
        self.app.lista_opt.marcar(["reg_sugerencias", "tareas_telemetria", "inicio_conocidos"], True)
        self.app._aplicar()
        self.assertTrue(self.esperar(self.app, lambda: not self.app.busy and nucleo_sesiones(self.env)))
        self.assertNotEqual(antes, self.env.instantanea())
        from bottimint import nucleo
        sesion = nucleo.listar_sesiones(self.env)[-1]["sesion"]
        nucleo.restaurar(self.env, sesion, lambda s: None)
        self.assertEqual(antes, self.env.instantanea())

    def test_marcar_perfil_en_programas(self):
        self.app._marcar_perfil("gamer")
        marcados = self.app.lista_prog.marcados()
        self.assertIn("Valve.Steam", marcados)
        self.assertNotIn("Google.Chrome", marcados, "lo ya instalado no se marca")

    def test_instalar_desde_la_interfaz(self):
        self.app.lista_prog.marcar(["7zip.7zip", "Valve.Steam"], True)
        self.app._instalar()
        self.assertTrue(self.esperar(self.app, lambda: not self.app.busy))
        carpeta = os.path.join(self.app.wg.base_dir, "instalaciones")
        self.assertTrue(os.path.isdir(carpeta) and os.listdir(carpeta))


    # ---------- tema e idioma ----------
    def test_cambiar_tema_se_guarda_y_conserva_el_estado(self):
        from bottimint import ajustes
        plan = list(self.app.plan_actual)
        instalados = set(self.app.instalados)
        self.app.cambiar_tema("claro")
        self.assertEqual(self.app.pal["bg"], "#f4f7f6")
        self.assertEqual(ajustes.cargar(self.ruta_aj)["tema"], "claro")
        self.assertEqual(self.app.plan_actual, plan)
        self.assertEqual(self.app.instalados, instalados)
        self.assertTrue(self.app.lista_opt.tree.get_children(), "la lista se vuelve a poblar tras el cambio")
        self.app.cambiar_tema("oscuro")
        self.assertEqual(self.app.pal["bg"], "#121718")

    def test_cambiar_idioma_traduce_toda_la_interfaz(self):
        from bottimint import ajustes
        marcados = set(self.app.lista_opt.marcados())
        self.app.cambiar_idioma("en")
        self.assertEqual(ajustes.cargar(self.ruta_aj)["idioma"], "en")
        self.assertEqual(self.app.vars_info["Permisos"].get(), "Administrator")
        self.assertEqual(self.app.nb.tab(0, "text").strip(), "Home")
        self.assertIn("Basic", self.app.txt_nivel.get("1.0", "end"))
        titulos = [self.app.lista_opt.tree.set(i, "titulo") for i in self.app.lista_opt.tree.get_children()]
        self.assertTrue(all(t for t in titulos))
        self.assertNotIn("Vaciar caché DNS", titulos)
        for cod in ("ru", "ja", "zh", "es"):
            self.app.cambiar_idioma(cod)
            self.assertTrue(self.app.nb.tab(0, "text").strip())
        self.assertEqual(self.app.nb.tab(0, "text").strip(), "Inicio")
        self.assertTrue(marcados)

    def test_el_motor_aplica_igual_en_cualquier_idioma(self):
        self.app.cambiar_idioma("ja")
        self.app.nivel.set("profundo")
        self.app._cambio_nivel()
        self.esperar(self.app, lambda: not self.app.busy and any(p["id"] == "reg_sugerencias" for p in self.app.plan_actual))
        self.app.lista_opt.marcar_todo(False)
        self.app.lista_opt.marcar(["reg_sugerencias"], True)
        self.app._aplicar()
        self.assertTrue(self.esperar(self.app, lambda: not self.app.busy and nucleo_listar(self.env)))

    # ---------- salir y widgets redondeados ----------
    def test_salir_pide_confirmacion_y_si_se_cancela_no_cierra(self):
        pedidos = []
        self.app.preguntar = lambda titulo, texto, si=None, no=None, peligro=False: pedidos.append((texto, peligro)) or False
        self.app.salir()
        self.assertEqual(len(pedidos), 1)
        self.assertTrue(pedidos[0][1], "el diálogo de salida usa el estilo de peligro")
        self.assertTrue(self.app.winfo_exists())

    def test_salir_confirmado_cierra_la_ventana(self):
        self.app.preguntar = lambda *a, **k: True
        self.app.salir()
        with self.assertRaises(Exception):
            self.app.winfo_exists()
        self.app = type("X", (), {"destroy": lambda s: None})()

    def test_salir_con_tarea_en_curso_advierte(self):
        textos = []
        self.app.preguntar = lambda titulo, texto, *a, **k: textos.append(texto) or False
        self.app.busy = True
        self.app.salir()
        self.app.busy = False
        self.assertIn("optimiz", textos[0])

    def test_boton_redondo_respeta_el_estado_deshabilitado(self):
        from bottimint.widgets import BotonRedondo
        hechos = []
        b = BotonRedondo(self.app, self.app.pal, "x", lambda: hechos.append(1))
        b.invoke()
        b.configure(state="disabled")
        b.invoke()
        b.configure(state="normal")
        b.invoke()
        self.assertEqual(len(hechos), 2)
        self.assertEqual(b.cget("state"), "normal")

    def test_selector_de_nivel_cambia_la_variable(self):
        from bottimint.widgets import SelectorNivel
        sel = SelectorNivel(self.app, self.app.pal, "a\nb", self.app.nivel, "extremo", "#fff", "#000")
        sel.elegir()
        self.assertEqual(self.app.nivel.get(), "extremo")

    def test_cambiar_tema_e_idioma_varias_veces_no_pierde_la_interfaz(self):
        for _ in range(3):
            self.app.cambiar_tema("claro")
            self.app.cambiar_idioma("zh")
            self.app.cambiar_tema("oscuro")
            self.app.cambiar_idioma("es")
        self.assertTrue(self.app.btn_salir.winfo_exists())
        self.assertTrue(self.app.lista_opt.tree.get_children())


def nucleo_sesiones(env):
    from bottimint import nucleo
    return nucleo.listar_sesiones(env)


def nucleo_listar(env):
    from bottimint import nucleo
    return nucleo.listar_sesiones(env)


if __name__ == "__main__":
    unittest.main()
