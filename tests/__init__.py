"""Pruebas de BottiMint.

Varias llaman a aplicar() con un Windows falso, que además copia el informe al Escritorio: aquí se redirige a una carpeta
temporal para que correr las pruebas no deje archivos en el Escritorio real."""
import tempfile

from bottimint import confiables

_carpeta_real = confiables.carpeta
ESCRITORIO_DE_PRUEBAS = tempfile.mkdtemp(prefix="bottimint_escritorio_")


def _carpeta_en_pruebas(clave: str) -> str:
    return ESCRITORIO_DE_PRUEBAS if clave == "desktop" else _carpeta_real(clave)


confiables.carpeta = _carpeta_en_pruebas
