#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera docs/NIVELES.md y docs/PROGRAMAS.md DESDE EL CÓDIGO, para que la documentación nunca quede desactualizada.

    python scripts/generar_docs.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from bottimint import instalador, nucleo  # noqa: E402

RIESGO = {"bajo": "🟢 bajo", "medio": "🟠 medio", "alto": "🔴 alto"}


def celda(t: str) -> str:
    return str(t).replace("|", "\\|").replace("\n", " ")


def niveles() -> str:
    L = ["# Niveles de optimización", "",
         "> Generado automáticamente desde `bottimint/nucleo.py` con `python scripts/generar_docs.py`. No editar a mano.", "",
         "Los niveles son **acumulativos**: Profundo incluye todo Básico, y Extremo incluye todo Profundo.",
         "Antes de aplicar cualquiera se crea un **punto de restauración de Windows** y se verifica; si no se puede crear, **no se modifica nada**.", ""]
    for n in nucleo.ORDEN:
        d = nucleo.NIVELES[n]
        L += [f"## {d['titulo']}", "", f"**Ideal para:** {d['para_quien']}", "", "**Qué hace**", ""]
        L += [f"- {x}" for x in d["que_hace"]]
        L += ["", "**Consecuencias a tener en cuenta**", ""] + [f"- {x}" for x in d["consecuencias"]]
        L += ["", f"**Reversibilidad:** {d['reversibilidad']}", ""]
        nuevos = [c for c in nucleo.CATALOGO if c.nivel == n]
        L += [f"### Cambios que incorpora este nivel ({len(nuevos)})", "",
              "| Cambio | Grupo | Riesgo | Reversible | Marcado por defecto | Qué hace | Consecuencia |",
              "|---|---|---|---|---|---|---|"]
        for c in nuevos:
            if callable(c._defecto):
                pre = "según el equipo"
            else:
                pre = "sí" if c._defecto else "no"
            L.append(f"| **{celda(c.titulo)}**<br>`{c.id}` | {celda(c.grupo)} | {RIESGO.get(c.riesgo, c.riesgo)} | "
                     f"{'sí' if c.reversible else 'no'} | {pre} | {celda(c.que_hace)} | {celda(c.consecuencia)} |")
        L.append("")
    L += ["## Qué NO toca nunca", "",
          "- Windows Defender ni el Firewall (no se desactivan ni se modifican).",
          "- Windows Update: no se desactiva; solo se limpian las descargas que ya se instalaron.", "- Servicios de red y audio.",
          "- Apps críticas: Microsoft Store, Calculadora, Fotos, Bloc de notas, Terminal, Edge, Seguridad de Windows.",
          "- Archivos personales (documentos, fotos, escritorio).", "- El registro de Windows más allá de los ajustes listados arriba (no hay «limpiador de registro»)."]
    return "\n".join(L) + "\n"


def programas() -> str:
    L = ["# Catálogo de programas", "",
         "> Generado automáticamente desde `bottimint/instalador.py` con `python scripts/generar_docs.py`. No editar a mano.", "",
         "Todo se instala con **winget** (fuente oficial `winget`), en silencio y con el ID exacto.", "", "## Perfiles", ""]
    for k, v in instalador.PERFILES.items():
        L += [f"### `{k}` - {v['titulo']}", "", v["descripcion"], "",
              ", ".join(instalador.POR_ID[i].nombre for i in v["ids"]), ""]
    L += ["## Catálogo completo", ""]
    cat = None
    for p in instalador.CATALOGO:
        if p.categoria != cat:
            cat = p.categoria
            L += ["", f"### {cat}", "", "| Programa | ID de winget | Descripción | Nota |", "|---|---|---|---|"]
        L.append(f"| {celda(p.nombre)} | `{p.id}` | {celda(p.descripcion)} | {celda(p.nota)} |")
    L += ["", "## Agregar un programa", "",
          "1. Buscá el ID exacto: `winget search <nombre>` (columna *Id*) y comprobá con `winget show --id <ID> --exact`.",
          "2. Agregá una línea `Programa(...)` en `CATALOGO` (`bottimint/instalador.py`) y, si corresponde, su ID en un perfil.",
          "3. Ejecutá `python scripts/generar_docs.py` y `python -m unittest discover -s tests -t .`."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    os.makedirs(os.path.join(RAIZ, "docs"), exist_ok=True)
    for nombre, texto in (("NIVELES.md", niveles()), ("PROGRAMAS.md", programas())):
        with open(os.path.join(RAIZ, "docs", nombre), "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        print("generado docs/" + nombre)
