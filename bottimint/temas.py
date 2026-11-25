# -*- coding: utf-8 -*-
"""Temas claro y oscuro (acento «mint») para tkinter/ttk."""
try:  # las paletas se pueden usar (y probar) aunque este Python no traiga tkinter
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # pragma: no cover
    tk = ttk = None

PALETAS = {
    "claro": dict(bg="#f4f7f6", panel="#ffffff", fg="#1b2a25", sub="#5a6a64", acento="#0a7d54", acento_fg="#ffffff",
                  borde="#cdd8d3", sel="#d6f0e4", entrada="#ffffff", log="#fbfdfc", ok="#1b7f4d", warn="#a35f00",
                  peligro="#c62828", gris="#97a39e", caja1="#eef8f2", caja2="#fff4e8", caja3="#eef3fa",
                  nivel_tinte={"basico": "#d3efd9", "profundo": "#ffe0bd", "extremo": "#ffd0d0"}),
    "oscuro": dict(bg="#121718", panel="#1b2223", fg="#e5eeea", sub="#97a8a1", acento="#3ddc97", acento_fg="#08130f",
                   borde="#2e3a3b", sel="#244a3d", entrada="#232c2d", log="#0e1213", ok="#4ade80", warn="#f0a24d",
                   peligro="#ff7070", gris="#66746f", caja1="#17291f", caja2="#2b2317", caja3="#1a2430",
                   nivel_tinte={"basico": "#1f4d34", "profundo": "#5a3d12", "extremo": "#5a2222"}),
}
NIVEL_COLOR_CLAVE = {"basico": "ok", "profundo": "warn", "extremo": "peligro"}


def paleta(nombre: str) -> dict:
    return PALETAS.get(nombre, PALETAS["oscuro"])


def aplicar(root: "tk.Misc", nombre: str) -> dict:
    """Configura todos los estilos ttk y los widgets clásicos. Devuelve la paleta usada."""
    p = paleta(nombre)
    st = ttk.Style(root)
    st.theme_use("clam")  # único tema de ttk que se deja colorear por completo
    fuente = ("Segoe UI", 9)
    st.configure(".", background=p["bg"], foreground=p["fg"], fieldbackground=p["entrada"], bordercolor=p["borde"],
                 lightcolor=p["borde"], darkcolor=p["borde"], troughcolor=p["panel"], focuscolor=p["acento"],
                 selectbackground=p["sel"], selectforeground=p["fg"], insertcolor=p["fg"], font=fuente)
    st.configure("TFrame", background=p["bg"])
    st.configure("Panel.TFrame", background=p["panel"])
    st.configure("TLabel", background=p["bg"], foreground=p["fg"])
    st.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"), foreground=p["acento"])
    st.configure("Sub.TLabel", foreground=p["sub"])
    st.configure("Peligro.TLabel", foreground=p["peligro"], font=("Segoe UI", 9, "bold"))
    st.configure("EstadoOk.TLabel", foreground=p["ok"], font=("Segoe UI", 10, "bold"))
    st.configure("EstadoBusy.TLabel", foreground=p["warn"], font=("Segoe UI", 10, "bold"))
    st.configure("TButton", background=p["panel"], foreground=p["fg"], padding=(10, 4), borderwidth=1, relief="flat")
    st.map("TButton", background=[("disabled", p["bg"]), ("active", p["sel"])],
           foreground=[("disabled", p["gris"])], bordercolor=[("focus", p["acento"])])
    st.configure("Accion.TButton", background=p["acento"], foreground=p["acento_fg"], font=("Segoe UI", 10, "bold"), padding=8)
    st.map("Accion.TButton", background=[("disabled", p["borde"]), ("active", p["acento"])],
           foreground=[("disabled", p["gris"]), ("active", p["acento_fg"])])
    st.configure("Modo.TButton", font=("Segoe UI Symbol", 12), padding=(8, 2), background=p["panel"])
    st.configure("ModoActivo.TButton", font=("Segoe UI Symbol", 12), padding=(8, 2), background=p["acento"], foreground=p["acento_fg"])
    st.map("ModoActivo.TButton", background=[("active", p["acento"])], foreground=[("active", p["acento_fg"])])
    st.configure("TCheckbutton", background=p["bg"], foreground=p["fg"])
    st.map("TCheckbutton", background=[("active", p["bg"])], indicatorcolor=[("selected", p["acento"]), ("!selected", p["entrada"])])
    st.configure("TNotebook", background=p["bg"], borderwidth=0, tabmargins=(0, 4, 0, 0))
    st.configure("TNotebook.Tab", background=p["panel"], foreground=p["sub"], padding=(14, 6), borderwidth=0)
    st.map("TNotebook.Tab", background=[("selected", p["bg"]), ("active", p["sel"])],
           foreground=[("selected", p["acento"])])
    st.configure("Treeview", background=p["panel"], fieldbackground=p["panel"], foreground=p["fg"], rowheight=22, borderwidth=0)
    st.map("Treeview", background=[("selected", p["sel"])], foreground=[("selected", p["fg"])])
    st.configure("Treeview.Heading", background=p["bg"], foreground=p["sub"], relief="flat", font=("Segoe UI", 9, "bold"))
    st.map("Treeview.Heading", background=[("active", p["sel"])])
    st.configure("TScrollbar", background=p["borde"], troughcolor=p["panel"], arrowcolor=p["sub"], borderwidth=0)
    st.map("TScrollbar", background=[("active", p["gris"])])
    st.configure("TEntry", fieldbackground=p["entrada"], foreground=p["fg"], insertcolor=p["fg"])
    st.configure("TCombobox", fieldbackground=p["entrada"], background=p["panel"], foreground=p["fg"],
                 arrowcolor=p["fg"], selectbackground=p["entrada"], selectforeground=p["fg"])
    st.map("TCombobox", fieldbackground=[("readonly", p["entrada"])], foreground=[("readonly", p["fg"])])
    st.configure("Horizontal.TProgressbar", background=p["acento"], troughcolor=p["panel"], borderwidth=0)
    st.configure("TSeparator", background=p["borde"])
    root.configure(bg=p["bg"])
    for patron, valor in (("*TCombobox*Listbox.background", p["entrada"]), ("*TCombobox*Listbox.foreground", p["fg"]),
                          ("*TCombobox*Listbox.selectBackground", p["acento"]), ("*TCombobox*Listbox.selectForeground", p["acento_fg"])):
        root.option_add(patron, valor)
    return p


def barra_titulo(ventana: "tk.Misc", oscuro: bool) -> None:
    """Pone oscura (o clara) la barra de título de Windows 10/11. Si no se puede, no pasa nada."""
    try:
        import ctypes
        ventana.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(ventana.winfo_id())  # type: ignore[attr-defined]
        valor = ctypes.c_int(1 if oscuro else 0)
        for atributo in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (Win11/Win10 2004+, Win10 antiguo)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(valor), ctypes.sizeof(valor)) == 0:  # type: ignore[attr-defined]
                break
    except Exception:
        pass
