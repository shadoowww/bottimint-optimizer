# -*- coding: utf-8 -*-
"""Punto de entrada: sin argumentos abre la interfaz gráfica.

    python -m bottimint                      -> interfaz gráfica
    python -m bottimint optimizar <args>     -> motor por niveles (niveles, plan, aplicar, sesiones, restaurar...)
    python -m bottimint programas <args>     -> instalador (catalogo, perfiles, plan, instalar, verificar, actualizar...)
    python -m bottimint limpieza <args>      -> limpieza suelta (--analizar / --limpiar)
"""
import sys


def main() -> None:
    from . import ajustes, i18n
    i18n.set_idioma(ajustes.cargar()["idioma"])  # la consola también habla el idioma elegido
    args = sys.argv[1:]
    if not args or args[0] == "gui":
        from .gui import lanzar
        lanzar()
        return
    modulo, resto = args[0], args[1:]
    sys.argv = [f"bottimint {modulo}"] + resto
    if modulo == "optimizar":
        from . import nucleo
        nucleo.main()
    elif modulo == "programas":
        from . import instalador
        instalador.main()
    elif modulo == "limpieza":
        from . import limpieza
        limpieza.main()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
