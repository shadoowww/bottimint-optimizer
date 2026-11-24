#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera docs/NIVELES.md y docs/PROGRAMAS.md (en inglés) DESDE EL CÓDIGO, para que la documentación nunca quede desactualizada.

    python scripts/generar_docs.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from bottimint import i18n, instalador, nucleo  # noqa: E402
from bottimint.i18n import tr  # noqa: E402

i18n.set_idioma("en")  # la documentación del repositorio se genera en inglés (los textos vienen de las traducciones de la app)

RIESGO = {"bajo": "🟢 low", "medio": "🟠 medium", "alto": "🔴 high"}


def celda(t: str) -> str:
    return str(t).replace("|", "\\|").replace("\n", " ")


def niveles() -> str:
    L = ["# Optimization levels", "",
         "> Automatically generated from `bottimint/nucleo.py` with `python scripts/generar_docs.py`. Do not edit by hand.", "",
         "The levels are **cumulative**: Deep includes everything in Basic, and Extreme includes everything in Deep.",
         "Before applying any of them a **Windows restore point** is created and verified; if it cannot be created, **nothing is modified**.", ""]
    for n in nucleo.ORDEN:
        d = nucleo.NIVELES[n]
        L += [f"## {tr(d['titulo'])}", "", f"**Ideal for:** {tr(d['para_quien'])}", "", "**What it does**", ""]
        L += [f"- {tr(x)}" for x in d["que_hace"]]
        L += ["", "**Consequences to keep in mind**", ""] + [f"- {tr(x)}" for x in d["consecuencias"]]
        L += ["", f"**Reversibility:** {tr(d['reversibilidad'])}", ""]
        nuevos = [c for c in nucleo.CATALOGO if c.nivel == n]
        L += [f"### Changes introduced by this level ({len(nuevos)})", "",
              "| Change | Group | Risk | Reversible | Checked by default | What it does | Consequence |",
              "|---|---|---|---|---|---|---|"]
        for c in nuevos:
            if callable(c._defecto):
                pre = "depends on the machine"
            else:
                pre = "yes" if c._defecto else "no"
            L.append(f"| **{celda(tr(c.titulo))}**<br>`{c.id}` | {celda(tr(c.grupo))} | {RIESGO.get(c.riesgo, c.riesgo)} | "
                     f"{'yes' if c.reversible else 'no'} | {pre} | {celda(tr(c.que_hace))} | {celda(tr(c.consecuencia))} |")
        L.append("")
    L += ["## What it NEVER touches", "",
          "- Windows Defender and the Firewall (never disabled or modified).",
          "- Windows Update: never disabled; only the downloads that were already installed are cleaned.", "- Network and audio services.",
          "- Critical apps: Microsoft Store, Calculator, Photos, Notepad, Terminal, Edge, Windows Security.",
          "- Personal files (documents, photos, desktop).", "- The Windows registry beyond the settings listed above (there is no \"registry cleaner\")."]
    return "\n".join(L) + "\n"


def programas() -> str:
    L = ["# Program catalog", "",
         "> Automatically generated from `bottimint/instalador.py` with `python scripts/generar_docs.py`. Do not edit by hand.", "",
         "Everything is installed with **winget** (official `winget` source), silently and with the exact ID.", "", "## Profiles", ""]
    for k, v in instalador.PERFILES.items():
        L += [f"### `{k}` - {tr(v['titulo'])}", "", tr(v["descripcion"]), "",
              ", ".join(instalador.POR_ID[i].nombre for i in v["ids"]), ""]
    L += ["## Full catalog", ""]
    cat = None
    for p in instalador.CATALOGO:
        if p.categoria != cat:
            cat = p.categoria
            L += ["", f"### {tr(cat)}", "", "| Program | winget ID | Description | Note |", "|---|---|---|---|"]
        L.append(f"| {celda(p.nombre)} | `{p.id}` | {celda(tr(p.descripcion))} | {celda(tr(p.nota) if p.nota else '')} |")
    L += ["", "## Adding a program", "",
          "1. Find the exact ID: `winget search <name>` (*Id* column) and check it with `winget show --id <ID> --exact`.",
          "2. Add a `Programa(...)` line to `CATALOGO` (`bottimint/instalador.py`) and, if appropriate, its ID to a profile. Add the English text of the description to `bottimint/idiomas/en.py`.",
          "3. Run `python scripts/generar_docs.py` and `python -m unittest discover -s tests -t .`."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    os.makedirs(os.path.join(RAIZ, "docs"), exist_ok=True)
    for nombre, texto in (("NIVELES.md", niveles()), ("PROGRAMAS.md", programas())):
        with open(os.path.join(RAIZ, "docs", nombre), "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        print("generado docs/" + nombre)
