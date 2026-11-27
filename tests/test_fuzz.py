"""Fuzzing de lo que BottiMint lee de disco: el manifiesto de restauración (se usa con permisos de administrador) y los
ajustes del usuario. Sin dependencias externas.

Se parte de un manifiesto legítimo (nivel Extremo con todos los cambios), se lo deforma de miles de maneras y se
comprueba que:
  1. nunca se produce un error sin manejar (el programa no se cae);
  2. todo lo que restaurar() intenta escribir en el sistema está en una lista cerrada sacada del catálogo.

Es reproducible: cada caso sale de una semilla y el mensaje de fallo la indica. Para una corrida más larga:
    set BOTTIMINT_FUZZ=50000  &&  python -m unittest tests.test_fuzz
"""
import copy
import json
import os
import random
import tempfile
import unittest

from bottimint import ajustes, nucleo
from tests.falsos import EntornoFalso

CASOS = int(os.environ.get("BOTTIMINT_FUZZ", "1200"))
SESION = "20260101_000000"

RAROS = [None, True, False, 0, 1, 2, 3, 4, 5, -1, 255, 2 ** 31, 2 ** 32, 2 ** 64, 1.5, 4.0, "", "a", "4", "x" * 5000,
         "a\x00b", "\n", "'; Remove-Item C:\\ -Recurse; '", "$(calc)", "a & calc", "--source evil", "..\\..\\Windows",
         "C:\\Windows\\System32", "\\\\servidor\\recurso\\x.jpg", "C:\\Program Files\\WindowsApps\\..\\..\\Temp\\x",
         "HKLM", "HKCU", "SYSTEM\\CurrentControlSet\\Services\\WinDefend\\", "WinDefend", "mpssvc", "Start", "DiagTrack",
         "SecurityHealth", "Realtek", "381b4222-f694-41f0-9685-ff5bb260df2e", "381b4222-f694-41f0-9685-ff5bb260df2e\n",
         [], [1], [[]], ["a"], {}, {"a": 1}, [{}], [None], {"nombre": "WinDefend", "start": 4, "corriendo": True}]


# ---------------------------------------------------------------- lo que restaurar() tiene permitido hacer
CATALOGO = nucleo.CATALOGO
REGISTRO = {(h, p.lower(), n.lower()): t for c in CATALOGO if isinstance(c, nucleo.CambioRegistro)
            for h, p, n, t, _v in c.valores}
SERVICIOS = {s for c in CATALOGO if isinstance(c, nucleo.CambioServicios) for s in c.servicios}
CLAVES_SERVICIO = {(nucleo.SVC_KEY + s).lower() for s in SERVICIOS}
TAREAS = {tuple(t) for c in CATALOGO if isinstance(c, nucleo.CambioTareas) for t in c.tareas}
CAMBIOS_INICIO = [c for c in CATALOGO if isinstance(c, nucleo.CambioInicio)]
SPI = {a[2] for a in nucleo.SPI_AJUSTES}


# Las comprobaciones del vigilante se escriben aparte a propósito: si usaran las funciones del programa, un error en
# ellas pasaría inadvertido.
def valor_aceptable(tipo_catalogo, tipo, valor) -> bool:
    if tipo_catalogo == 4:  # REG_DWORD
        return type(tipo) is int and tipo == 4 and type(valor) is int and 0 <= valor < 2 ** 32
    return type(tipo) is int and tipo in (1, 2) and isinstance(valor, str) and len(valor) <= 2048 and chr(0) not in valor


def es_entrada_de_la_lista(e) -> bool:
    texto = (e.nombre.lower(), e.comando.lower())
    return any(p in t for c in CAMBIOS_INICIO for p in c.patrones for t in texto)


class EntornoVigilado(EntornoFalso):
    """Windows falso que anota como violación cualquier escritura fuera de lo permitido."""

    def __init__(self, base_dir):
        super().__init__(base_dir)
        self.violaciones = []

    def _exigir(self, condicion, *que):
        if not condicion:
            self.violaciones.append(repr(que)[:300])

    def reg_set(self, h, p, n, t, v):
        clave = (h, str(p).lower(), str(n).lower())
        if clave in REGISTRO:
            self._exigir(valor_aceptable(REGISTRO[clave], t, v), "reg_set: valor no válido", p, n, t, v)
        else:
            self._exigir(h == "HKLM" and str(p).lower() in CLAVES_SERVICIO and n == "Start" and t == nucleo.REG_DWORD
                         and type(v) is int and 0 <= v <= 4, "reg_set: clave o valor ajeno", h, p, n, t, v)

    def reg_del(self, h, p, n):
        self._exigir((h, str(p).lower(), str(n).lower()) in REGISTRO, "reg_del ajeno", h, p, n)

    def tarea_set(self, r, n, h):
        self._exigir((r, n) in TAREAS and h is True, "tarea ajena", r, n, h)
        return True

    def run(self, cmd, timeout=None):
        permitido = (cmd == ["powercfg", "/h", "on"] or cmd == [self.onedrive_setup()]
                     or (len(cmd) == 3 and cmd[:2] == ["sc", "start"] and cmd[2] in SERVICIOS)
                     or (len(cmd) == 3 and cmd[:2] == ["powercfg", "/setactive"] and isinstance(cmd[2], str)
                         and nucleo._RE_GUID.fullmatch(cmd[2]) is not None))
        self._exigir(permitido, "comando ajeno", cmd)
        return 0, ""

    def ps(self, script, timeout=300):
        self._exigir(False, "PowerShell durante la restauración", script)
        return 1, ""

    def set_inicio(self, e, habilitar):
        self._exigir(habilitar is True and es_entrada_de_la_lista(e), "inicio ajeno", e.nombre)

    def spi_set(self, accion, valor, via="pv"):
        self._exigir(accion in SPI and valor in (0, 1, 2), "ajuste de interfaz ajeno", accion, valor)
        return True

    def fondo_aplicar(self, ruta, color):
        self._exigir(isinstance(ruta, str) and nucleo._RE_RUTA_FONDO.fullmatch(ruta) is not None
                     and len(color) == 3 and all(type(x) is int and 0 <= x <= 255 for x in color), "fondo raro", ruta, color)

    def registrar_appx(self, ubicacion):
        # el Entorno real solo registra si _loc_appx_valida() lo acepta: lo aceptado debe estar dentro de WindowsApps
        if nucleo._loc_appx_valida(ubicacion):
            self._exigir(os.sep + "windowsapps" + os.sep in os.path.normcase(os.path.abspath(ubicacion)).lower(),
                         "appx fuera de WindowsApps", ubicacion)
        return False

    def quitar_appx(self, full):
        self._exigir(False, "desinstalar durante la restauración", full)
        return False

    def desanclar_inicio(self):
        self._exigir(False, "desanclar durante la restauración")
        return 0


def manifiesto_legitimo() -> dict:
    env = EntornoFalso(tempfile.mkdtemp())
    ids = [c.id for c in CATALOGO if not c.id.startswith("limp_")]
    sesion = nucleo.aplicar("extremo", env, ids, emitir=lambda s: None)
    with open(os.path.join(env.base_dir, "sesiones", sesion, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def nodos(objeto):
    """Todos los (contenedor, clave) del árbol."""
    pila, res = [objeto], []
    while pila:
        o = pila.pop()
        for k, v in (o.items() if isinstance(o, dict) else enumerate(o) if isinstance(o, list) else []):
            res.append((o, k))
            pila.append(v)
    return res


def deformar(base: dict, azar: random.Random):
    m = copy.deepcopy(base)
    for _ in range(azar.randint(1, 6)):
        lista = nodos(m)
        if not lista:
            break
        cont, clave = azar.choice(lista)
        que = azar.randrange(7)
        if que in (0, 1):
            cont[clave] = copy.deepcopy(azar.choice(RAROS))
        elif que == 2:
            del cont[clave]
        elif que == 3:  # trasplantar un trozo legítimo a otro sitio (p. ej. el estado de un cambio en otro)
            otro, k2 = azar.choice(lista)
            cont[clave] = copy.deepcopy(otro[k2])
        elif que == 4 and isinstance(m.get("cambios"), list) and m["cambios"]:
            entrada = azar.choice(m["cambios"])
            if isinstance(entrada, dict):
                entrada["id"] = azar.choice(CATALOGO).id
        elif que == 5 and isinstance(cont, dict):
            cont[azar.choice(["hive", "path", "name", "tipo", "valor", "existe", "nombre", "start", "corriendo", "ruta",
                              "origen", "loc", "Name", "guid", "estaba", "onedrive", "estado", "titulo", "nivel",
                              "cambios", "id", "valores", "servicios", "tareas", "apps", "inicio", "spi", "clave"])] = \
                copy.deepcopy(azar.choice(RAROS))
        elif isinstance(cont[clave], str):
            cont[clave] = cont[clave] + azar.choice(["\n", " ", "\x00", "\\..\\..\\x", "'", ";calc"])
    return m


class PruebasFuzzManifiesto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = manifiesto_legitimo()

    def preparar(self):
        env = EntornoVigilado(tempfile.mkdtemp())
        carpeta = os.path.join(env.base_dir, "sesiones", SESION)
        os.makedirs(carpeta)
        return env, os.path.join(carpeta, "manifest.json")

    def ejercitar(self, env, errores, etiqueta):
        env.violaciones.clear()
        try:
            nucleo.listar_sesiones(env)
            nucleo.restaurar(env, SESION, emitir=lambda s: None)
        except Exception as ex:  # noqa: BLE001 - justamente se busca cualquier error sin manejar
            errores.setdefault(f"error sin manejar {type(ex).__name__}: {str(ex)[:120]}", etiqueta)
        for v in env.violaciones:
            errores.setdefault("violación " + v, etiqueta)

    def informar(self, errores):
        self.assertFalse(errores, "\n" + "\n".join(f"- [{donde}] {que}" for que, donde in list(errores.items())[:15])
                         + f"\n({len(errores)} problemas distintos)")

    def test_el_manifiesto_legitimo_no_viola_nada(self):
        env, ruta = self.preparar()
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.base, f)
        errores = {}
        self.ejercitar(env, errores, "legítimo")
        self.informar(errores)

    def test_manifiestos_con_la_estructura_deformada(self):
        env, ruta = self.preparar()
        errores = {}
        for semilla in range(CASOS):
            m = deformar(self.base, random.Random(semilla))
            if isinstance(m, dict):
                m["restaurada"] = False
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(m, f)
            self.ejercitar(env, errores, f"semilla {semilla}")
        self.informar(errores)

    def test_manifiestos_con_los_bytes_corrompidos(self):
        env, ruta = self.preparar()
        original = json.dumps(self.base).encode()
        errores = {}
        for semilla in range(CASOS // 4):
            azar = random.Random(semilla)
            datos = bytearray(original)
            for _ in range(azar.randint(1, 8)):
                i = azar.randrange(len(datos))
                que = azar.randrange(4)
                if que == 0:
                    datos[i] = azar.randrange(256)
                elif que == 1:
                    del datos[i:i + azar.randint(1, 200)]
                elif que == 2:
                    datos[i:i] = azar.choice([b"[", b"{", b"}", b"]", b'"', b",", b"null", b"\xff\xfe", b"1e999"])
                else:
                    datos = datos[:max(1, i)]
            with open(ruta, "wb") as f:
                f.write(bytes(datos))
            self.ejercitar(env, errores, f"bytes, semilla {semilla}")
        self.informar(errores)

    def test_formas_extremas(self):
        env, ruta = self.preparar()
        errores = {}
        extremos = {
            "anidamiento enorme": "[" * 200000,
            "objeto anidado enorme": '{"a":' * 200000,
            "número gigante": '{"nivel": "extremo", "cambios": [], "x": ' + "9" * 100000 + "}",
            "nivel como lista": '{"nivel": ["extremo"], "cambios": []}',
            "nivel como objeto": '{"nivel": {}, "cambios": []}',
            "cambio sin título": '{"nivel":"extremo","cambios":[{"id":"hibernacion","estado":{"estaba":true}}]}',
            "estado que no es objeto": '{"nivel":"extremo","cambios":[{"id":"reg_gaming","estado":"x"}]}',
            "raíz que no es objeto": "[1, 2]",
            "texto unicode inválido": json.dumps({"nivel": "extremo", "cambios": [], "restaurada": False, "x": chr(0xD800)}),
            **{f"anidamiento intermedio {n}": '{"nivel":"extremo","cambios":[],"restaurada":false,"x":' + "[" * n + "]" * n + "}"
               for n in (500, 900, 2000, 5000, 20000)},
            "vacío": "",
        }
        for nombre, texto in extremos.items():
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(texto)
            self.ejercitar(env, errores, nombre)
        self.informar(errores)


class PruebasGuardarManifiesto(unittest.TestCase):
    def test_un_nombre_con_unicode_suelto_se_guarda_y_se_recupera(self):
        ruta = os.path.join(tempfile.mkdtemp(), "manifest.json")
        raro = "entrada " + chr(0xD800) + " de Windows"
        m = {"nivel": "extremo", "cambios": [], "restaurada": False, "x": raro}
        nucleo._guardar(ruta, m)
        self.assertEqual(nucleo._leer_manifest(ruta)["x"], raro)

    def test_los_acentos_se_siguen_guardando_legibles(self):
        ruta = os.path.join(tempfile.mkdtemp(), "manifest.json")
        nucleo._guardar(ruta, {"nivel": "extremo", "cambios": [], "x": "Telemetría"})
        with open(ruta, encoding="utf-8") as f:
            self.assertIn("Telemetría", f.read())


class PruebasFuzzAjustes(unittest.TestCase):
    def test_cualquier_archivo_de_ajustes_da_valores_validos(self):
        ruta = os.path.join(tempfile.mkdtemp(), "ajustes.json")
        textos = ["[" * 200000, '{"a":' * 200000, "", "null", "[]", '{"idioma": []}', '{"tema": {}}', "9" * 100000]
        for semilla in range(CASOS // 4):
            azar = random.Random(semilla)
            textos.append(json.dumps(deformar({"idioma": "es", "tema": "oscuro"}, azar)))
        errores = {}
        for i, texto in enumerate(textos):
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(texto)
            try:
                cfg = ajustes.cargar(ruta)
                if cfg["idioma"] not in ajustes.IDIOMAS_VALIDOS or cfg["tema"] not in ajustes.TEMAS_VALIDOS:
                    errores.setdefault(f"valor no válido: {cfg}", i)
            except Exception as ex:  # noqa: BLE001
                errores.setdefault(f"error sin manejar {type(ex).__name__}", i)
        self.assertFalse(errores, errores)


if __name__ == "__main__":
    unittest.main()
