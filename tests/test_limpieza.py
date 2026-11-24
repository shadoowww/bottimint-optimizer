import os
import tempfile
import unittest

from bottimint import limpieza


class PruebasLimpieza(unittest.TestCase):
    def test_limpia_contenido_conserva_carpeta_y_no_sigue_enlaces(self):
        raiz = tempfile.mkdtemp()
        temp, fuera = os.path.join(raiz, "Temp"), os.path.join(raiz, "importante")
        os.makedirs(os.path.join(temp, "sub"))
        os.makedirs(fuera)
        with open(os.path.join(fuera, "dato.txt"), "w") as f:
            f.write("no se debe borrar")
        with open(os.path.join(temp, "a.txt"), "w") as f:
            f.write("hola")
        with open(os.path.join(temp, "sub", "b.bin"), "wb") as f:
            f.write(b"0" * 5000)
        try:
            os.symlink(fuera, os.path.join(temp, "enlace"))
        except (OSError, NotImplementedError):
            pass  # Windows sin privilegios para crear enlaces
        rutas = limpieza.expandir([temp])
        self.assertEqual(limpieza.tamano_total(rutas), 5004)
        liberado, omitidos = limpieza.limpiar_rutas(rutas)
        self.assertEqual((liberado, omitidos), (5004, 0))
        self.assertTrue(os.path.isdir(temp), "la carpeta raíz se conserva")
        self.assertEqual(os.listdir(temp), [])
        self.assertTrue(os.path.exists(os.path.join(fuera, "dato.txt")), "no sigue enlaces simbólicos")

    def test_rutas_peligrosas_se_descartan(self):
        self.assertEqual(limpieza.expandir([os.path.abspath(os.sep), "", None]), [])

    def test_fmt_bytes(self):
        self.assertEqual(limpieza.fmt_bytes(512), "512 B")
        self.assertEqual(limpieza.fmt_bytes(1024 * 1024 * 3), "3.0 MB")


if __name__ == "__main__":
    unittest.main()
