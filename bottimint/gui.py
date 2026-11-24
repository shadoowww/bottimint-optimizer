# -*- coding: utf-8 -*-
"""Interfaz gráfica de BottiMint (tkinter): Inicio, Optimización por niveles, Programas e Inicio de Windows.

Tema claro/oscuro y varios idiomas: al cambiar cualquiera de los dos, la ventana se reconstruye conservando
el estado (plan, programas detectados, registro). Las tareas largas corren en un hilo aparte; la interfaz solo se
toca desde el hilo principal (los hilos se comunican por una cola). Los diálogos son métodos para poder probarlos.
"""
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from . import ajustes as ajustes_mod, i18n, instalador, limpieza as base, nucleo, temas
from .i18n import tr
from .widgets import BotonRedondo, DialogoSiNo, SelectorNivel, Tarjeta

NIVEL_NOMBRE = {"basico": "Básico", "profundo": "Profundo", "extremo": "Extremo / Gaming"}
NIVEL_LEMA = {"basico": "Limpieza general", "profundo": "Limpieza + quitar lo que sobra", "extremo": "Mínimo de procesos"}


# ====================================================================
# Widgets auxiliares
# ====================================================================
class ListaCheck(ttk.Frame):
    """Tabla con casillas de verificación (clic en la columna ✔ o barra espaciadora)."""

    def __init__(self, master, columnas: List[tuple], pal: dict, altura: int = 10, al_elegir: Optional[Callable[[str], None]] = None, al_cambiar: Optional[Callable[[], None]] = None):
        super().__init__(master, style="Panel.TFrame")
        self.al_cambiar = al_cambiar
        self.ids = [c[0] for c in columnas]
        self.marcado: Dict[str, bool] = {}
        self.bloqueado: set = set()
        self.al_elegir = al_elegir
        self.tree = ttk.Treeview(self, columns=["chk"] + self.ids, show="headings", height=altura, selectmode="browse")
        self.tree.heading("chk", text="✔")
        self.tree.column("chk", width=34, anchor="center", stretch=False)
        for cid, titulo, ancho, *resto in columnas:
            self.tree.heading(cid, text=titulo)
            self.tree.column(cid, width=ancho, anchor=resto[0] if resto else "w")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("medio", foreground=pal["warn"])
        self.tree.tag_configure("alto", foreground=pal["peligro"])
        self.tree.tag_configure("gris", foreground=pal["gris"])
        self.tree.tag_configure("ok", foreground=pal["ok"])
        self.tree.bind("<Button-1>", self._clic)
        self.tree.bind("<space>", lambda e: self._alternar(self.tree.focus()))
        self.tree.bind("<<TreeviewSelect>>", self._seleccion)

    def _simbolo(self, iid: str) -> str:
        return "☑" if self.marcado.get(iid) else "☐"

    def cargar(self, filas: List[dict]) -> None:
        """filas: {id, valores: tuple, marcado: bool, bloqueado: bool, tags: tuple}"""
        self.tree.delete(*self.tree.get_children())
        self.marcado.clear()
        self.bloqueado.clear()
        for f in filas:
            iid = f["id"]
            self.marcado[iid] = bool(f.get("marcado")) and not f.get("bloqueado")
            if f.get("bloqueado"):
                self.bloqueado.add(iid)
            self.tree.insert("", "end", iid=iid, values=(self._simbolo(iid),) + tuple(f["valores"]),
                             tags=tuple(f.get("tags", ())))
        self._avisar()

    def _avisar(self) -> None:
        if self.al_cambiar:
            self.al_cambiar()

    def _refrescar_fila(self, iid: str) -> None:
        self.tree.set(iid, "chk", self._simbolo(iid))

    def _alternar(self, iid: str) -> None:
        if not iid or iid in self.bloqueado:
            return
        self.marcado[iid] = not self.marcado.get(iid, False)
        self._refrescar_fila(iid)
        self._avisar()

    def _clic(self, ev) -> None:
        if self.tree.identify_region(ev.x, ev.y) == "cell" and self.tree.identify_column(ev.x) == "#1":
            self._alternar(self.tree.identify_row(ev.y))

    def _seleccion(self, _ev) -> None:
        sel = self.tree.selection()
        if sel and self.al_elegir:
            self.al_elegir(sel[0])

    def marcados(self) -> List[str]:
        return [i for i in self.tree.get_children() if self.marcado.get(i)]

    def marcar(self, ids, valor: bool = True) -> None:
        for i in ids:
            if i in self.marcado and i not in self.bloqueado:
                self.marcado[i] = valor
                self._refrescar_fila(i)
        self._avisar()

    def marcar_todo(self, valor: bool) -> None:
        self.marcar(list(self.tree.get_children()), valor)

    def set_valor(self, iid: str, columna: str, texto: str) -> None:
        if self.tree.exists(iid):
            self.tree.set(iid, columna, texto)


class DialogoConfirmacion(tk.Toplevel):
    """Muestra un texto largo y exige tildar una casilla antes de continuar."""

    def __init__(self, master, titulo: str, texto: str, casilla: str, boton: str, pal: dict, oscuro: bool):
        super().__init__(master)
        self.title(titulo)
        self.configure(bg=pal["bg"])
        self.transient(master)
        self.resultado = False
        self.geometry("720x560")
        marco = ttk.Frame(self, padding=10)
        marco.pack(fill="both", expand=True)
        tarjeta = Tarjeta(marco, pal, fondo=pal["panel"], alto=380)
        tarjeta.pack(fill="both", expand=True)
        txt = tk.Text(tarjeta.cuerpo, wrap="word", font=("Segoe UI", 10), padx=8, pady=8, bg=pal["panel"], fg=pal["fg"],
                      insertbackground=pal["fg"], relief="flat", highlightthickness=0)
        sb = ttk.Scrollbar(tarjeta.cuerpo, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", texto)
        txt.configure(state="disabled")
        self.var = tk.BooleanVar(value=False)
        ttk.Checkbutton(marco, text=casilla, variable=self.var, command=self._cambio).pack(anchor="w", pady=(10, 4))
        fila = ttk.Frame(marco)
        fila.pack(fill="x")
        self.ok = BotonRedondo(fila, pal, boton, self._aceptar, "accion")
        self.ok.configure(state="disabled")
        self.ok.pack(side="right")
        BotonRedondo(fila, pal, tr("Cancelar"), self.destroy).pack(side="right", padx=8)
        temas.barra_titulo(self, oscuro)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _cambio(self) -> None:
        self.ok.configure(state="normal" if self.var.get() else "disabled")

    def _aceptar(self) -> None:
        self.resultado = True
        self.destroy()


# ====================================================================
# Aplicación
# ====================================================================
class App(tk.Tk):
    def __init__(self, env: Optional[nucleo.Entorno] = None, wg: Optional[instalador.Winget] = None,
                 ruta_ajustes: Optional[str] = None):
        super().__init__()
        self.ruta_ajustes = ruta_ajustes
        self.ajustes = ajustes_mod.cargar(ruta_ajustes)
        i18n.set_idioma(self.ajustes["idioma"])
        self.title("BottiMint")
        self.geometry("1040x740")
        self.minsize(940, 640)
        self.env = env or nucleo.Entorno()
        self.wg = wg or instalador.Winget()
        self.q: "queue.Queue" = queue.Queue()
        self.busy = False
        self.equipo: dict = {}
        self.plan_actual: List[dict] = []
        self.instalados: set = set()
        self._deteccion_inicial = False
        self.winget_ok: Optional[bool] = None
        self._res_inicial: Optional[tuple] = None
        self._lineas_log: List[str] = []
        self.botones: List[BotonRedondo] = []
        self.nivel = tk.StringVar(value="basico")
        self.vars_info: Dict[str, tk.StringVar] = {}
        self.pal: dict = {}
        self._estilos()
        self._construir()
        self.protocol("WM_DELETE_WINDOW", self.salir)
        self._id_bombear = self.after(100, self._bombear)
        self._tarea(self._carga_inicial, self._tras_carga_inicial)

    # ---------------- infraestructura ----------------
    @property
    def oscuro(self) -> bool:
        return self.ajustes["tema"] == "oscuro"

    def _estilos(self) -> None:
        self.pal = temas.aplicar(self, self.ajustes["tema"])
        temas.barra_titulo(self, self.oscuro)

    def log(self, msg: str) -> None:
        self.q.put(("log", msg))

    def _tarea(self, fn: Callable, hecho: Optional[Callable] = None) -> bool:
        if self.busy:
            self.log("Hay una tarea en curso; esperá a que termine.")
            return False
        self._set_busy(True)

        def run():
            try:
                self.q.put(("fin", hecho, fn(), None))
            except Exception as ex:  # nunca dejar la interfaz bloqueada
                self.q.put(("fin", hecho, None, ex))
        threading.Thread(target=run, daemon=True).start()
        return True

    def _set_busy(self, b: bool) -> None:
        self.busy = b
        for w in self.botones:
            try:
                w.configure(state="disabled" if b else "normal")
            except tk.TclError:
                pass
        if b:
            self.barra.configure(mode="indeterminate")
            self.barra.start(12)
        else:
            self.barra.stop()
            self.barra.configure(mode="determinate", value=0)
        self._actualizar_cuenta()

    def _bombear(self) -> None:
        try:
            while True:
                tipo, *datos = self.q.get_nowait()
                if tipo == "log":
                    self._escribir_log(datos[0])
                elif tipo == "prog":
                    actual, total = datos[0]
                    self.barra.stop()
                    self.barra.configure(mode="determinate", maximum=max(1, total), value=actual)
                elif tipo == "fin":
                    hecho, resultado, error = datos
                    self._set_busy(False)
                    if error is not None:
                        self._escribir_log(f"ERROR: {error}")
                    elif hecho:
                        try:
                            hecho(resultado)
                        except Exception as ex:  # un error al mostrar resultados no debe frenar la interfaz
                            self._escribir_log(f"ERROR al mostrar el resultado: {ex!r}")
        except queue.Empty:
            pass
        self._id_bombear = self.after(120, self._bombear)

    def _escribir_log(self, s: str) -> None:
        s = tr(s)  # los mensajes del motor vienen en español: se traducen al idioma activo
        self._lineas_log.append(s)
        self._lineas_log = self._lineas_log[-500:]
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", s + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def destroy(self) -> None:
        try:
            self.after_cancel(self._id_bombear)
        except Exception:
            pass
        super().destroy()

    def salir(self) -> None:
        """Botón «Salir» y cruz de la ventana: siempre piden confirmación (más fuerte si hay una tarea en curso)."""
        texto = tr("¿Seguro que querés salir de BottiMint?")
        if self.busy:
            texto = tr("Hay una tarea en curso. Salir ahora puede dejar una optimización a medias; no se recomienda.") + "\n\n" + texto
        if self.preguntar(tr("Salir de BottiMint"), texto, tr("Salir"), tr("Quedarme"), peligro=True):
            self.destroy()

    # Los diálogos son métodos para poder reemplazarlos en las pruebas.
    def pedir_confirmacion(self, titulo: str, texto: str, casilla: str, boton: Optional[str] = None) -> bool:
        d = DialogoConfirmacion(self, titulo, texto, casilla, boton or tr("Continuar"), self.pal, self.oscuro)
        self.wait_window(d)
        return d.resultado

    def preguntar(self, titulo: str, texto: str, si: Optional[str] = None, no: Optional[str] = None, peligro: bool = False) -> bool:
        d = DialogoSiNo(self, self.pal, self.oscuro, titulo, texto, si or tr("Sí"), no or tr("No"), peligro)
        self.wait_window(d)
        return d.resultado

    def aviso(self, titulo: str, texto: str, nivel: str = "info") -> None:
        icono = {"info": "", "warn": "⚠  ", "error": "✖  "}[nivel]
        self.wait_window(DialogoSiNo(self, self.pal, self.oscuro, titulo, icono + texto, tr("Aceptar")))

    # ---------------- tema e idioma ----------------
    def cambiar_tema(self, tema: str) -> None:
        if tema == self.ajustes["tema"] or tema not in ajustes_mod.TEMAS_VALIDOS:
            return
        if self.busy:
            return self.log("Hay una tarea en curso; esperá a que termine.")
        self.ajustes["tema"] = tema
        ajustes_mod.guardar(self.ajustes["idioma"], tema, self.ruta_ajustes)
        self._reconstruir()

    def cambiar_idioma(self, cod: str) -> None:
        if cod == self.ajustes["idioma"] or cod not in ajustes_mod.IDIOMAS_VALIDOS:
            return
        if self.busy:
            return self.log("Hay una tarea en curso; esperá a que termine.")
        self.ajustes["idioma"] = cod
        i18n.set_idioma(cod)
        ajustes_mod.guardar(cod, self.ajustes["tema"], self.ruta_ajustes)
        self._reconstruir()

    def _reconstruir(self) -> None:
        """Vuelve a dibujar toda la ventana (nuevo tema o idioma) conservando el estado."""
        for w in self.winfo_children():
            w.destroy()
        self.botones = []
        self.vars_info = {}
        self._estilos()
        self._construir()
        self._repoblar()

    def _repoblar(self) -> None:
        self._aplicar_info()
        self._pintar_plan()
        self._pintar_programas()
        for linea in self._lineas_log:
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", linea + "\n")
            self.txt_log.configure(state="disabled")
        self.txt_log.see("end")

    # ---------------- construcción ----------------
    def _construir(self) -> None:
        p = self.pal
        cab = ttk.Frame(self, padding=(12, 8, 12, 0))
        cab.pack(fill="x")
        ttk.Label(cab, text="BottiMint", style="Titulo.TLabel").pack(side="left")
        ttk.Label(cab, text="   " + tr("Limpieza, optimización y programas para Windows"), style="Sub.TLabel").pack(side="left")
        # botón Salir (pide confirmación)
        self.btn_salir = BotonRedondo(cab, p, "⏻  " + tr("Salir"), self.salir, "peligro")
        self.btn_salir.pack(side="right", padx=(12, 0))
        # selector de tema: ☀ claro  ☾ oscuro
        modos = ttk.Frame(cab)
        modos.pack(side="right", padx=(10, 0))
        self.btn_claro = BotonRedondo(modos, p, "☀", lambda: self.cambiar_tema("claro"),
                                      "modo" if self.oscuro else "modo_activo", ancho_min=40, simbolo=True)
        self.btn_oscuro = BotonRedondo(modos, p, "☾", lambda: self.cambiar_tema("oscuro"),
                                       "modo_activo" if self.oscuro else "modo", ancho_min=40, simbolo=True)
        self.btn_claro.pack(side="left")
        self.btn_oscuro.pack(side="left", padx=(4, 0))
        # selector de idioma
        self.var_idioma = tk.StringVar(value=i18n.IDIOMAS[self.ajustes["idioma"]])
        self.cb_idioma = ttk.Combobox(cab, textvariable=self.var_idioma, values=list(i18n.IDIOMAS.values()),
                                      state="readonly", width=10)
        self.cb_idioma.pack(side="right")
        self.cb_idioma.bind("<<ComboboxSelected>>", self._elegir_idioma)
        self.lbl_admin = ttk.Label(cab, text="", style="Peligro.TLabel")
        self.lbl_admin.pack(side="right", padx=12)

        pie = ttk.Frame(self, padding=(12, 0, 12, 10))
        pie.pack(side="bottom", fill="x")  # primero el pie: así el registro nunca queda cortado
        self.barra = ttk.Progressbar(pie, mode="determinate")
        self.barra.pack(fill="x")
        caja = Tarjeta(pie, p, fondo=p["log"], alto=86)
        caja.pack(fill="x", pady=(6, 0))
        self.txt_log = tk.Text(caja.cuerpo, height=3, state="disabled", font=("Consolas", 9), bg=p["log"], fg=p["fg"],
                               relief="flat", highlightthickness=0)
        sb = ttk.Scrollbar(caja.cuerpo, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        self.txt_log.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=8)
        self._tab_inicio()
        self._tab_optimizacion()
        self._tab_programas()
        self._tab_arranque()

        if self.busy:
            self._set_busy(True)

    def _elegir_idioma(self, _ev=None) -> None:
        nombre = self.var_idioma.get()
        cod = next((c for c, n in i18n.IDIOMAS.items() if n == nombre), self.ajustes["idioma"])
        self.cambiar_idioma(cod)

    def _boton(self, master, texto, comando, estilo="normal", bloquea=True) -> BotonRedondo:
        b = BotonRedondo(master, self.pal, texto, comando, estilo)
        if bloquea:
            self.botones.append(b)
        return b

    def _caja_texto(self, master, fondo: str, **kw) -> tk.Text:
        p = self.pal
        return tk.Text(master, wrap="word", bg=fondo, fg=p["fg"], insertbackground=p["fg"], relief="flat",
                       highlightthickness=0, state="disabled", **kw)

    # ----- pestaña Inicio -----
    CAMPOS_INFO = ["Equipo", "Sistema", "Procesador", "RAM", "Disco libre", "Tipo de disco", "Batería", "Impresoras", "winget", "Permisos"]

    def _tab_inicio(self) -> None:
        f = ttk.Frame(self.nb, padding=14)
        self.nb.add(f, text="  " + tr("Inicio") + "  ")
        ttk.Label(f, text=tr("Este equipo"), font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", columnspan=2)
        for i, c in enumerate(self.CAMPOS_INFO, start=1):
            ttk.Label(f, text=tr(c) + ":", style="Sub.TLabel").grid(row=i, column=0, sticky="e", padx=(0, 8), pady=1)
            v = tk.StringVar(value="…")
            self.vars_info[c] = v
            ttk.Label(f, textvariable=v).grid(row=i, column=1, sticky="w")
        fila = len(self.CAMPOS_INFO) + 1
        bs = ttk.Frame(f)
        bs.grid(row=fila, column=0, columnspan=2, sticky="w", pady=(14, 0))
        self._boton(bs, tr("Abrir «Restaurar sistema» de Windows"), lambda: self.env.run(["rstrui.exe"]), bloquea=False).pack(side="left")
        self._boton(bs, tr("Abrir carpeta de informes"), self._abrir_informes, bloquea=False).pack(side="left", padx=6)
        self.btn_admin = self._boton(bs, tr("Reabrir como administrador"), self._reabrir_admin, bloquea=False)
        self.btn_winget = self._boton(bs, tr("Instalar winget"), self._instalar_winget, "accion")
        ttk.Separator(f).grid(row=fila + 1, column=0, columnspan=2, sticky="ew", pady=14)
        ttk.Label(f, text=tr("BottiMint no envía ningún dato: funciona sin conexión salvo para instalar programas (winget), "
                             "y antes de cambiar nada crea un punto de restauración de Windows."),
                  style="Sub.TLabel", wraplength=900, justify="left").grid(row=fila + 2, column=0, columnspan=2, sticky="w")

    def _abrir_informes(self) -> None:
        try:
            base.preparar_dir_datos(self.env.base_dir)
            os.startfile(self.env.base_dir)  # type: ignore[attr-defined]
        except Exception as ex:
            self.aviso(tr("Informes"), tr("Los informes están en:\n{ruta}\n\n({ex})", ruta=self.env.base_dir, ex=ex))

    def _reabrir_admin(self) -> None:
        base.relaunch_as_admin()
        self.destroy()

    def _carga_inicial(self):
        equipo = self.env.detectar_equipo()
        info = base.info_sistema()
        winget_ok = self.wg.disponible()
        return equipo, info, winget_ok

    def _tras_carga_inicial(self, res) -> None:
        self._res_inicial = res
        self.equipo = res[0]
        self._aplicar_info()
        self._refrescar_plan()  # al terminar, detecta los programas instalados (ver _mostrar_plan)

    def _aplicar_info(self) -> None:
        if not self._res_inicial:
            return
        equipo, info, winget_ok = self._res_inicial
        admin = self.env.is_admin()
        v = self.vars_info
        v["Equipo"].set(info.get("Equipo", "?"))
        v["Sistema"].set(info.get("Sistema", "?"))
        v["Procesador"].set(info.get("Procesador", "?"))
        v["RAM"].set(info.get("RAM") or (f"{equipo.get('ram_gb')} GB" if equipo.get("ram_gb") else "?"))
        v["Disco libre"].set(tr("{libre} de {total}", libre=info.get("Disco (libre)", "?"), total=info.get("Disco (total)", "?")))
        v["Tipo de disco"].set(equipo.get("media") or tr("no detectado"))
        v["Batería"].set(tr("Sí (notebook)") if equipo.get("bateria") else tr("No (escritorio)"))
        v["Impresoras"].set(str(equipo.get("impresoras", "?")))
        self.winget_ok = bool(winget_ok)
        v["winget"].set(tr("Disponible") if winget_ok else tr("NO disponible (se instala con el botón «Instalar winget»)"))
        self._actualizar_winget_ui()
        v["Permisos"].set(tr("Administrador") if admin else tr("SIN administrador"))
        if not admin:
            self.lbl_admin.configure(text=tr("Sin permisos de administrador: los cambios del sistema se omiten"))
            if base.IS_WIN:
                self.btn_admin.pack(side="left")

    # ----- pestaña Optimización -----
    def _color_nivel(self, n: str) -> str:
        return self.pal[temas.NIVEL_COLOR_CLAVE[n]]

    def _tab_optimizacion(self) -> None:
        p = self.pal
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  " + tr("Optimización") + "  ")
        sel = ttk.Frame(f)
        sel.pack(fill="x")
        for n in nucleo.ORDEN:
            SelectorNivel(sel, p, f"{tr(NIVEL_NOMBRE[n])}\n{tr(NIVEL_LEMA[n])}", self.nivel, n, self._color_nivel(n),
                          p["nivel_tinte"][n], self._cambio_nivel).pack(side="left", padx=(0, 10))
        paneles = ttk.Frame(f)
        paneles.pack(fill="x", pady=(8, 6))
        paneles.columnconfigure(0, weight=1, uniform="p")
        paneles.columnconfigure(1, weight=1, uniform="p")
        self.txt_nivel, self.txt_consec = [
            self._texto_con_scroll(paneles, col, bg) for col, bg in ((0, p["caja1"]), (1, p["caja2"]))]
        for t in (self.txt_nivel, self.txt_consec):
            for tag, color in (("tit", p["fg"]), ("ok", p["ok"]), ("warn", p["warn"])):
                t.tag_configure(tag, foreground=color, font=("Segoe UI", 9, "bold"))
        acc = ttk.Frame(f)
        acc.pack(fill="x", pady=(0, 6))
        self.btn_aplicar = self._boton(acc, tr("APLICAR CAMBIOS MARCADOS ({n})", n=0), self._aplicar, "accion")
        self.btn_aplicar.pack(side="right")
        self.lbl_cuenta = ttk.Label(acc, text="", style="Sub.TLabel")
        self.lbl_cuenta.pack(side="right", padx=12)
        self._boton(acc, tr("Marcar todo"), lambda: self.lista_opt.marcar_todo(True), bloquea=False).pack(side="left")
        self._boton(acc, tr("Desmarcar todo"), lambda: self.lista_opt.marcar_todo(False), bloquea=False).pack(side="left", padx=4)
        self._boton(acc, tr("Actualizar vista previa"), self._refrescar_plan).pack(side="left", padx=4)
        self._boton(acc, tr("Restaurar una sesión…"), self._dialogo_restaurar).pack(side="left", padx=4)
        ttk.Label(f, text=tr("Elegir un nivel no cambia nada: solo muestra qué se haría. Marcá lo que quieras y confirmá con el botón."),
                  style="Sub.TLabel").pack(fill="x", pady=(0, 6))
        tarj_lista = Tarjeta(f, p, fondo=p["panel"], alto=150)
        tarj_lista.pack(fill="both", expand=True)
        self.lista_opt = ListaCheck(tarj_lista.cuerpo, [("grupo", tr("Grupo"), 150), ("titulo", tr("Cambio"), 330), ("riesgo", tr("Riesgo"), 70, "center"),
                                        ("estado", tr("En este equipo"), 300)], p, altura=7, al_elegir=self._detalle_cambio,
                                    al_cambiar=self._actualizar_cuenta)
        self.lista_opt.pack(fill="both", expand=True)
        tarj_det = Tarjeta(f, p, fondo=p["caja3"], alto=84)
        tarj_det.pack(fill="x", pady=(6, 0))
        self.txt_det = self._caja_texto(tarj_det.cuerpo, p["caja3"], height=3, font=("Segoe UI", 9), padx=4, pady=2)
        self.txt_det.pack(fill="both", expand=True)
        self._texto_nivel()

    def _texto_con_scroll(self, master, columna: int, fondo: str) -> tk.Text:
        tarjeta = Tarjeta(master, self.pal, fondo=fondo, alto=150)
        tarjeta.grid(row=0, column=columna, sticky="nsew", padx=(0 if columna == 0 else 5, 5 if columna == 0 else 0))
        t = self._caja_texto(tarjeta.cuerpo, fondo, height=6, font=("Segoe UI", 9), padx=6, pady=4)
        sb = ttk.Scrollbar(tarjeta.cuerpo, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return t

    def _actualizar_cuenta(self) -> None:
        """Contador de cambios marcados y estado del botón de aplicar."""
        try:
            n = len(self.lista_opt.marcados())
            total = sum(1 for x in self.plan_actual if x["aplica"])
            self.lbl_cuenta.configure(text=tr("{n} de {total} cambios marcados", n=n, total=total))
            self.btn_aplicar.configure(text=tr("APLICAR CAMBIOS MARCADOS ({n})", n=n),
                                       state="disabled" if (n == 0 or self.busy) else "normal")
        except (AttributeError, tk.TclError):
            pass

    def _cambio_nivel(self) -> None:
        self._texto_nivel()
        self._refrescar_plan()

    def _texto_nivel(self) -> None:
        n = nucleo.NIVELES[self.nivel.get()]
        izq, der = self.txt_nivel, self.txt_consec
        for t in (izq, der):
            t.configure(state="normal")
            t.delete("1.0", "end")
        izq.insert("end", tr(n["titulo"]) + "\n", "tit")
        izq.insert("end", tr("Ideal para: {x}", x=tr(n["para_quien"])) + "\n\n")
        izq.insert("end", tr("Qué hace:") + "\n", "ok")
        for x in n["que_hace"]:
            izq.insert("end", f"  • {tr(x)}\n")
        der.insert("end", tr("Consecuencias a tener en cuenta:") + "\n", "warn")
        for x in n["consecuencias"]:
            der.insert("end", f"  ! {tr(x)}\n")
        der.insert("end", "\n" + tr("Reversibilidad:") + " ", "tit")
        der.insert("end", tr(n["reversibilidad"]))
        for t in (izq, der):
            t.configure(state="disabled")

    def _refrescar_plan(self) -> None:
        nivel = self.nivel.get()
        if self.busy:
            self.after(500, self._refrescar_plan)
            return
        self.log(tr("Revisando el equipo (solo lectura, no se modifica nada) para el nivel {nivel}...", nivel=tr(NIVEL_NOMBRE[nivel])))
        self._tarea(lambda: (nivel, nucleo.plan(nivel, self.env, self.equipo or None)), self._mostrar_plan)

    def _mostrar_plan(self, res) -> None:
        nivel, plan = res
        if nivel != self.nivel.get():
            return self._refrescar_plan()
        self.plan_actual = plan
        self._pintar_plan()
        self.log(tr("Vista previa lista: {n} cambios marcados de {total}.",
                    n=sum(1 for p in plan if p["seleccionado"]), total=len(plan)))
        if not self._deteccion_inicial:
            self._deteccion_inicial = True
            self._detectar_instalados()

    def _pintar_plan(self) -> None:
        filas = []
        for p in self.plan_actual:
            if p["aplica"]:
                estado = tr(p["detalle"]) if p["detalle"] else tr("Se puede aplicar")
                tags = (p["riesgo"],) if p["riesgo"] in ("medio", "alto") else ()
            else:
                estado = tr("No aplica: {motivo}", motivo=tr(p["detalle"])) if p["detalle"] else tr("No aplica")
                tags = ("gris",)
            filas.append({"id": p["id"], "valores": (tr(p["grupo"]), tr(p["titulo"]), tr(p["riesgo"]), estado),
                          "marcado": p["seleccionado"], "bloqueado": not p["aplica"], "tags": tags})
        self.lista_opt.cargar(filas)

    def _detalle_cambio(self, iid: str) -> None:
        p = next((x for x in self.plan_actual if x["id"] == iid), None)
        if not p:
            return
        t = self.txt_det
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", tr(p["titulo"]) + "\n")
        t.insert("end", tr("Qué hace: {x}", x=tr(p["que_hace"])) + "\n" + tr("Consecuencia: {x}", x=tr(p["consecuencia"])) + "\n")
        t.insert("end", tr("Riesgo: {x}", x=tr(p["riesgo"])) + "  ·  " +
                 (tr("Reversible con «Restaurar»") if p["reversible"] else tr("No reversible (archivos descartables / apps)")))
        t.configure(state="disabled")

    def _aplicar(self) -> None:
        nivel = self.nivel.get()
        ids = self.lista_opt.marcados()
        if not ids:
            return self.aviso(tr("Nada para aplicar"), tr("No hay cambios marcados."))
        if not self.env.is_admin():
            return self.aviso(tr("Permisos"), tr("Hace falta ejecutar como administrador para aplicar cambios."), "warn")
        riesgosos = [p for p in self.plan_actual if p["id"] in ids and p["riesgo"] in ("medio", "alto")]
        texto = nucleo.resumen_nivel(nivel) + f"\n\n{'=' * 50}\n" + tr("Se aplicarán {n} cambios.", n=len(ids)) + "\n"
        texto += tr("ANTES de cualquier cambio se crea un punto de restauración. Si no se puede crear, no se toca nada.") + "\n"
        if riesgosos:
            texto += "\n" + tr("Cambios de riesgo medio/alto que están marcados:") + "\n"
            texto += "\n".join(f"  - {tr(p['titulo'])} ({tr(p['riesgo'])}): {tr(p['consecuencia'])}" for p in riesgosos)
        if not self.pedir_confirmacion(tr("Confirmar optimización"), texto,
                                       tr("Leí las consecuencias y quiero continuar"), tr("Aplicar")):
            return
        self._tarea(lambda: nucleo.aplicar(nivel, self.env, ids, self.log, self.equipo or None), self._tras_aplicar)

    def _tras_aplicar(self, sesion) -> None:
        if sesion:
            self.aviso(tr("Listo"), tr("Optimización aplicada.\nSesión: {sesion}\n\nPara deshacer: «Restaurar una sesión…».\n"
                                       "El informe quedó en el Escritorio. Conviene reiniciar la PC.", sesion=sesion))
        else:
            self.aviso(tr("No se aplicó"), tr("No se hicieron cambios. Revisá el registro de abajo para ver el motivo."), "warn")
        self._refrescar_plan()

    def _dialogo_restaurar(self) -> None:
        sesiones = nucleo.listar_sesiones(self.env)
        if not sesiones:
            return self.aviso(tr("Restaurar"), tr("Todavía no hay sesiones guardadas."))
        d = tk.Toplevel(self)
        d.title(tr("Restaurar una sesión"))
        d.configure(bg=self.pal["bg"])
        d.transient(self)
        d.geometry("560x340")
        temas.barra_titulo(d, self.oscuro)
        ttk.Label(d, text=tr("Elegí la sesión que querés deshacer (se revierten sus cambios en orden inverso):"),
                  padding=8, wraplength=520).pack(anchor="w")
        tv = ttk.Treeview(d, columns=("nivel", "cambios", "estado"), show="headings", height=9)
        for c, t, w in (("nivel", tr("Nivel"), 120), ("cambios", tr("Cambios"), 80), ("estado", tr("Estado"), 140)):
            tv.heading(c, text=t)
            tv.column(c, width=w)
        for s in reversed(sesiones):
            tv.insert("", "end", iid=s["sesion"], values=(tr(NIVEL_NOMBRE.get(s["nivel"], s["nivel"])), s["cambios"],
                                                         tr("Ya restaurada") if s["restaurada"] else tr("Activa")))
        tv.pack(fill="both", expand=True, padx=8)
        if tv.get_children():
            tv.selection_set(tv.get_children()[0])

        def ir():
            sel = tv.selection()
            if not sel:
                return
            if self.preguntar(tr("Confirmar"), tr("¿Restaurar la sesión {s}?\nSe deshacen los cambios del sistema que hizo.", s=sel[0]), tr("Restaurar"), tr("Cancelar")):
                d.destroy()
                self._tarea(lambda: nucleo.restaurar(self.env, sel[0], self.log),
                            lambda ok: (self.aviso(tr("Restauración"), tr("Listo. Conviene reiniciar la PC.") if ok
                                                   else tr("No se pudo restaurar; mirá el registro.")),
                                        self._refrescar_plan()))
        fila = ttk.Frame(d, padding=8)
        fila.pack(fill="x")
        BotonRedondo(fila, self.pal, tr("Restaurar seleccionada"), ir, "accion").pack(side="right")
        BotonRedondo(fila, self.pal, tr("Cerrar"), d.destroy).pack(side="right", padx=8)

    # ----- pestaña Programas -----
    def _tab_programas(self) -> None:
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  " + tr("Programas") + "  ")
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text=tr("Marcar perfil:")).pack(side="left")
        for k, v in instalador.PERFILES.items():
            BotonRedondo(top, self.pal, tr(v["titulo"]), lambda k=k: self._marcar_perfil(k)).pack(side="left", padx=4)
        BotonRedondo(top, self.pal, tr("Limpiar selección"), lambda: self.lista_prog.marcar_todo(False)).pack(side="left", padx=12)
        self.fr_top_prog = top
        self.fr_winget = ttk.Frame(f)
        ttk.Label(self.fr_winget, text="⚠ " + tr("winget no está instalado en este equipo: sin él no se pueden instalar programas."),
                  style="Sub.TLabel").pack(side="left")
        self._boton(self.fr_winget, tr("Instalar winget"), self._instalar_winget, "accion").pack(side="left", padx=10)
        tarj_prog = Tarjeta(f, self.pal, fondo=self.pal["panel"], alto=220)
        tarj_prog.pack(fill="both", expand=True, pady=8)
        self.lista_prog = ListaCheck(tarj_prog.cuerpo, [("cat", tr("Categoría"), 110), ("nombre", tr("Programa"), 230), ("estado", tr("Estado"), 100),
                                         ("desc", tr("Descripción"), 460)], self.pal, altura=14, al_elegir=self._detalle_prog)
        self.lista_prog.pack(fill="both", expand=True)
        self.lbl_prog = ttk.Label(f, text="", style="Sub.TLabel", wraplength=960)
        self.lbl_prog.pack(fill="x")
        bs = ttk.Frame(f)
        bs.pack(fill="x", pady=(6, 0))
        self._boton(bs, tr("Detectar instalados"), self._detectar_instalados).pack(side="left")
        self._boton(bs, tr("Actualizar todos los programas"), self._actualizar_todo).pack(side="left", padx=6)
        self._boton(bs, tr("Verificar IDs del catálogo"), self._verificar_ids).pack(side="left")
        self._boton(bs, tr("INSTALAR SELECCIONADOS"), self._instalar, "accion").pack(side="right")
        self._pintar_programas()
        self._actualizar_winget_ui()

    def _actualizar_winget_ui(self) -> None:
        """Muestra el botón/aviso de instalar winget solo si falta."""
        try:
            if self.winget_ok is False:
                self.btn_winget.pack(side="left", padx=6)
                self.fr_winget.pack(fill="x", pady=(0, 8), before=self.fr_top_prog)
            else:
                self.btn_winget.pack_forget()
                self.fr_winget.pack_forget()
        except (AttributeError, tk.TclError):
            pass

    def _instalar_winget(self) -> None:
        if self.busy:
            return
        texto = tr("winget («Instalador de aplicaciones» de Microsoft) no está en este equipo.\n\n"
                   "BottiMint puede instalarlo ahora: primero intenta registrarlo y, si no está, lo descarga de los servidores oficiales de Microsoft "
                   "(github.com/microsoft y aka.ms, unos 20 MB) y Windows comprueba su firma.\n\nHace falta conexión a internet. ¿Instalarlo ahora?")
        if self.preguntar(tr("Instalar winget"), texto, tr("Instalar ahora"), tr("Cancelar")):
            self._tarea(lambda: self.wg.instalar_winget(self.log), self._tras_instalar_winget)

    def _tras_instalar_winget(self, ok) -> None:
        if ok:
            self.winget_ok = True
            if self._res_inicial:
                self._res_inicial = (self._res_inicial[0], self._res_inicial[1], True)
            self._aplicar_info()
            self.aviso(tr("Instalar winget"), tr("winget quedó instalado. Ya podés instalar programas."))
            self._detectar_instalados()
        else:
            self.aviso(tr("Instalar winget"), tr("No se pudo instalar winget. Probá instalar «Instalador de aplicaciones» desde Microsoft Store. Mirá el registro para ver el detalle."), "warn")

    def _pintar_programas(self) -> None:
        filas = []
        for p in instalador.CATALOGO:
            ya = p.id.lower() in self.instalados
            filas.append({"id": p.id, "valores": (tr(p.categoria), p.nombre, tr("Instalado") if ya else "", tr(p.descripcion)),
                          "bloqueado": False, "tags": ("ok",) if ya else ()})
        previos = set(self.lista_prog.marcados()) if hasattr(self, "lista_prog") and self.lista_prog.marcado else set()
        self.lista_prog.cargar(filas)
        self.lista_prog.marcar([i for i in previos if i.lower() not in self.instalados], True)

    def _marcar_perfil(self, k: str) -> None:
        self.lista_prog.marcar([i for i in instalador.PERFILES[k]["ids"] if i.lower() not in self.instalados], True)

    def _detalle_prog(self, iid: str) -> None:
        p = instalador.POR_ID.get(iid)
        self.lbl_prog.configure(text=(f"{p.nombre}: {tr(p.descripcion)}  " + (f"⚠ {tr(p.nota)}" if p.nota else "") +
                                      f"   [winget: {p.id}]") if p else "")

    def _detectar_instalados(self) -> None:
        if not base.IS_WIN and not self.wg.disponible():
            return
        self._tarea(self.wg.instalados, self._tras_detectar)

    def _tras_detectar(self, ids) -> None:
        self.instalados = set(ids)
        self._pintar_programas()

    def _instalar(self) -> None:
        ids = self.lista_prog.marcados()
        if not ids:
            return self.aviso(tr("Programas"), tr("No hay programas marcados."))
        if self.winget_ok is False:
            return self._instalar_winget()
        if not self.env.is_admin():
            return self.aviso(tr("Permisos"), tr("Hace falta ejecutar como administrador para instalar."), "warn")
        notas = [f"  - {instalador.POR_ID[i].nombre}: {tr(instalador.POR_ID[i].nota)}" for i in ids if instalador.POR_ID[i].nota]
        texto = tr("Se van a instalar {n} programas con winget (fuente oficial, instalación silenciosa):", n=len(ids)) + "\n\n"
        texto += "\n".join(f"  • {instalador.POR_ID[i].nombre}" for i in ids)
        if notas:
            texto += "\n\n" + tr("Avisos de licencia:") + "\n" + "\n".join(notas)
        texto += "\n\n" + tr("La PC necesita conexión a internet. Puede tardar varios minutos.")
        if not self.pedir_confirmacion(tr("Confirmar instalación"), texto, tr("Revisé la lista y las licencias"), tr("Instalar")):
            return
        total = len(ids)
        hechos = {"n": 0}

        def al_terminar(_i, _estado):
            hechos["n"] += 1
            self.q.put(("prog", (hechos["n"], total)))
        self._tarea(lambda: instalador.instalar_lote(ids, self.wg, self.log, al_terminar), self._tras_instalar)

    def _tras_instalar(self, res) -> None:
        if not res:
            return self.aviso(tr("Instalación"), tr("No se pudo instalar (¿winget disponible? ¿hay internet?). Mirá el registro."), "warn")
        cuenta = {}
        for r in res:
            cuenta[r["estado"]] = cuenta.get(r["estado"], 0) + 1
        self.aviso(tr("Instalación terminada"), "\n".join(f"{tr(k)}: {v}" for k, v in sorted(cuenta.items())) +
                   "\n\n" + tr("El informe quedó en C:\\ProgramData\\BottiMint\\instalaciones."))
        self._detectar_instalados()

    def _actualizar_todo(self) -> None:
        if self.preguntar(tr("Actualizar"), tr("Se actualizarán todos los programas que winget pueda actualizar.\n¿Continuar?"), tr("Continuar"), tr("Cancelar")):
            self._tarea(self.wg.actualizar_todo, lambda r: self.log((r[1] or "")[-1500:]))

    def _verificar_ids(self) -> None:
        self._tarea(lambda: instalador.verificar_catalogo(self.wg, self.log),
                    lambda faltan: self.aviso(tr("Verificación"), tr("Todos los IDs existen en winget.") if not faltan
                                              else tr("No se encontraron:") + "\n" + "\n".join(faltan), "info" if not faltan else "warn"))

    # ----- pestaña Programas de inicio -----
    def _tab_arranque(self) -> None:
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  " + tr("Inicio de Windows") + "  ")
        ttk.Label(f, text=tr("Programas que se abren solos al encender la PC. Deshabilitar es reversible y no desinstala nada."),
                  style="Sub.TLabel").pack(anchor="w")
        tarj_ini = Tarjeta(f, self.pal, fondo=self.pal["panel"], alto=260)
        tarj_ini.pack(fill="both", expand=True, pady=8)
        self.tv_inicio = ttk.Treeview(tarj_ini.cuerpo, columns=("estado", "origen", "comando"), show="headings", height=12)
        for c, t, w in (("estado", tr("Estado"), 100), ("origen", tr("Origen"), 120), ("comando", tr("Programa / comando"), 700)):
            self.tv_inicio.heading(c, text=t)
            self.tv_inicio.column(c, width=w)
        self.tv_inicio.pack(fill="both", expand=True)
        bs = ttk.Frame(f)
        bs.pack(fill="x")
        BotonRedondo(bs, self.pal, tr("Actualizar lista"), self._refrescar_arranque).pack(side="left")
        BotonRedondo(bs, self.pal, tr("Habilitar / Deshabilitar seleccionado"), self._alternar_arranque).pack(side="left", padx=8)
        self.entradas_inicio: list = []
        self._refrescar_arranque()

    def _refrescar_arranque(self) -> None:
        self.tv_inicio.delete(*self.tv_inicio.get_children())
        self.entradas_inicio = list(self.env.listar_inicio())
        for i, e in enumerate(self.entradas_inicio):
            self.tv_inicio.insert("", "end", iid=str(i), values=(tr("Activo") if e.habilitado else tr("Deshabilitado"), e.origen,
                                                                f"{e.nombre}  -  {e.comando}"))

    def _alternar_arranque(self) -> None:
        sel = self.tv_inicio.selection()
        if not sel:
            return
        e = self.entradas_inicio[int(sel[0])]
        try:
            self.env.set_inicio(e, not e.habilitado)
            self.log(tr("Inicio: {nombre} → {estado}", nombre=e.nombre,
                        estado=tr("habilitado") if e.habilitado else tr("deshabilitado")))
        except PermissionError:
            self.aviso(tr("Permisos"), tr("Ese elemento es del sistema: ejecutá el programa como administrador."), "warn")
        except Exception as ex:
            self.aviso(tr("Error"), str(ex), "error")
        self._refrescar_arranque()


def lanzar() -> None:
    if base.IS_WIN:
        try:  # evita que la ventana se vea borrosa en pantallas de alta resolución
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == "__main__":
    lanzar()
