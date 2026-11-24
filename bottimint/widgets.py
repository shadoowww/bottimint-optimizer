# -*- coding: utf-8 -*-
"""Widgets con esquinas redondeadas (tkinter/ttk no los trae): botones, selector de nivel, tarjetas y diálogos.

Todo se dibuja con Canvas usando la paleta del tema activo. Los botones aceptan configure(state=...) como un botón
normal, así el resto de la interfaz los trata igual que a un ttk.Button.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Callable, Optional

from . import temas
from .i18n import tr


def rect_redondo(c: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float, **kw) -> int:
    """Rectángulo con esquinas redondeadas (polígono suavizado)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
         x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(p, smooth=True, **kw)


class BotonRedondo(tk.Canvas):
    """estilo: normal | accion | peligro | modo | modo_activo"""

    def __init__(self, master, pal: dict, texto: str, comando: Optional[Callable] = None, estilo: str = "normal",
                 ancho_min: int = 0, simbolo: bool = False, fondo: Optional[str] = None):
        self.pal, self.texto, self.comando, self.estilo = pal, texto, comando, estilo
        self._estado, self._hover, self._presionado = "normal", False, False
        self._fuente = tkfont.Font(family="Segoe UI Symbol" if simbolo else "Segoe UI", size=12 if simbolo else 9,
                                   weight="bold" if estilo == "accion" else "normal")
        w = max(ancho_min, self._fuente.measure(texto) + (24 if not simbolo else 16))
        h = self._fuente.metrics("linespace") + (14 if estilo == "accion" else 10)
        super().__init__(master, width=w, height=h, bg=fondo or pal["bg"], highlightthickness=0, bd=0, takefocus=1)
        self.configure(cursor="hand2")
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, presionado=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(presionado=True))
        self.bind("<ButtonRelease-1>", self._soltar)
        self.bind("<Return>", lambda e: self.invoke())
        self.bind("<space>", lambda e: self.invoke())
        self.bind("<FocusIn>", lambda e: self._dibujar())
        self.bind("<FocusOut>", lambda e: self._dibujar())
        self.bind("<Configure>", lambda e: self._dibujar())
        self._dibujar()

    # --- interfaz tipo ttk.Button ---
    def configure(self, cnf=None, **kw):
        if "state" in kw:
            self._estado = kw.pop("state")
            self.configure_canvas_cursor()
            self._dibujar()
        if "text" in kw:
            self.texto = kw.pop("text")
            self._dibujar()
        if cnf or kw:
            return super().configure(cnf, **kw)
        return None

    config = configure

    def configure_canvas_cursor(self) -> None:
        super().configure(cursor="arrow" if self._estado == "disabled" else "hand2")

    def cget(self, key):
        return self._estado if key == "state" else super().cget(key)

    def invoke(self) -> None:
        if self._estado != "disabled" and self.comando:
            self.comando()

    # --- internos ---
    def _set(self, hover=None, presionado=None) -> None:
        if hover is not None:
            self._hover = hover
        if presionado is not None:
            self._presionado = presionado
        self._dibujar()

    def _soltar(self, e) -> None:
        activo = self._presionado
        self._set(presionado=False)
        if activo and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.invoke()

    def _colores(self):
        p, e = self.pal, self.estilo
        if self._estado == "disabled":
            return p["bg"], p["borde"], p["gris"]
        if e in ("accion", "modo_activo"):
            return (p["acento"], p["fg"] if self._hover else p["acento"], p["acento_fg"])
        if e == "peligro":
            return (p["peligro"], p["peligro"], p["bg"]) if self._hover else (p["panel"], p["peligro"], p["peligro"])
        return (p["sel"] if self._hover else p["panel"], p["borde"], p["fg"])

    def _dibujar(self) -> None:
        self.delete("all")
        w, h = max(self.winfo_width(), int(self["width"])), max(self.winfo_height(), int(self["height"]))
        relleno, borde, texto = self._colores()
        if self.focus_get() is self and self._estado != "disabled":
            borde = self.pal["acento"]
        rect_redondo(self, 1, 1, w - 1, h - 1, 10, fill=relleno, outline=borde, width=1)
        self.create_text(w / 2, h / 2 + (1 if self._presionado else 0), text=self.texto, fill=texto, font=self._fuente)


class SelectorNivel(tk.Canvas):
    """Tarjeta seleccionable de dos líneas (reemplaza al Radiobutton cuadrado)."""

    def __init__(self, master, pal: dict, texto: str, variable: tk.StringVar, valor: str, color: str, tinte: str,
                 comando: Optional[Callable] = None, ancho: int = 232, alto: int = 54):
        super().__init__(master, width=ancho, height=alto, bg=pal["bg"], highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        self.pal, self.texto, self.variable, self.valor = pal, texto, variable, valor
        self.color, self.tinte, self.comando, self._hover = color, tinte, comando, False
        self._fuente = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self._traza = variable.trace_add("write", lambda *a: self._dibujar())
        self.bind("<Destroy>", self._al_destruir)
        self.bind("<Enter>", lambda e: self._hover_set(True))
        self.bind("<Leave>", lambda e: self._hover_set(False))
        self.bind("<ButtonRelease-1>", lambda e: self.elegir())
        self.bind("<Return>", lambda e: self.elegir())
        self.bind("<space>", lambda e: self.elegir())
        self.bind("<FocusIn>", lambda e: self._dibujar())
        self.bind("<FocusOut>", lambda e: self._dibujar())
        self._dibujar()

    def _al_destruir(self, e) -> None:
        if e.widget is self:
            try:
                self.variable.trace_remove("write", self._traza)
            except Exception:
                pass

    def _hover_set(self, v: bool) -> None:
        self._hover = v
        self._dibujar()

    def elegir(self) -> None:
        self.variable.set(self.valor)
        if self.comando:
            self.comando()

    def _dibujar(self) -> None:
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        sel = self.variable.get() == self.valor
        relleno = self.tinte if sel else (self.pal["sel"] if self._hover else self.pal["panel"])
        borde = self.color if sel else (self.pal["acento"] if self.focus_get() is self else self.pal["borde"])
        rect_redondo(self, 2, 2, w - 2, h - 2, 14, fill=relleno, outline=borde, width=2 if sel else 1)
        self.create_text(w / 2, h / 2, text=self.texto, fill=self.color, font=self._fuente, justify="center")


class Tarjeta(tk.Canvas):
    """Contenedor con fondo redondeado. Los hijos van en `.cuerpo`. `alto` es la altura pedida (puede crecer con expand)."""

    def __init__(self, master, pal: dict, fondo: Optional[str] = None, alto: int = 100, radio: int = 14, pad: int = 8):
        super().__init__(master, bg=pal["bg"], highlightthickness=0, bd=0, height=alto)
        self.pal, self.radio, self.pad = pal, radio, pad
        self.fondo = fondo or pal["panel"]
        self.cuerpo = tk.Frame(self, bg=self.fondo)
        self._ventana = self.create_window(pad, pad, window=self.cuerpo, anchor="nw")
        self.bind("<Configure>", self._ajustar)

    def _ajustar(self, e) -> None:
        self.delete("fondo")
        rect_redondo(self, 1, 1, e.width - 1, e.height - 1, self.radio, fill=self.fondo, outline=self.pal["borde"], width=1, tags="fondo")
        self.tag_lower("fondo")
        self.itemconfigure(self._ventana, width=max(1, e.width - 2 * self.pad), height=max(1, e.height - 2 * self.pad))


class DialogoSiNo(tk.Toplevel):
    """Cuadro de diálogo con el tema de la app (los nativos de Windows no respetan el modo oscuro).
    El foco inicial queda en el botón seguro (el «no»), para que un Enter distraído no confirme."""

    def __init__(self, master, pal: dict, oscuro: bool, titulo: str, texto: str, si: str, no: Optional[str] = None,
                 peligro: bool = False):
        super().__init__(master)
        self.title(titulo)
        self.configure(bg=pal["bg"])
        self.transient(master)
        self.resizable(False, False)
        self.resultado = False
        marco = ttk.Frame(self, padding=18)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text=texto, wraplength=420, justify="left").pack(anchor="w")
        fila = ttk.Frame(marco)
        fila.pack(fill="x", pady=(18, 0))
        self.btn_si = BotonRedondo(fila, pal, si, self._aceptar, "peligro" if peligro else "accion")
        self.btn_si.pack(side="right")
        self.btn_no = None
        if no:
            self.btn_no = BotonRedondo(fila, pal, no, self.destroy)
            self.btn_no.pack(side="right", padx=8)
        temas.barra_titulo(self, oscuro)
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        if master is not None:  # centrado sobre la ventana principal
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_reqwidth()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_reqheight()) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.grab_set()
        (self.btn_no or self.btn_si).focus_set()

    def _aceptar(self) -> None:
        self.resultado = True
        self.destroy()
