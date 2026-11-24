"""Entornos simulados (Windows falso) para probar sin tocar nada real."""
import copy
import json

from bottimint import instalador, nucleo


class Entrada:
    def __init__(self, nombre, comando, origen):
        self.nombre, self.comando, self.origen, self.habilitado = nombre, comando, origen, True


class EntornoFalso(nucleo.Entorno):
    def __init__(self, base_dir, punto_ok=True, admin=True):
        super().__init__(base_dir)
        S = nucleo.SVC_KEY
        self.reg = {("HKLM", S + "DiagTrack", "Start"): (2, 4), ("HKLM", S + "Spooler", "Start"): (2, 4),
                    ("HKLM", S + "SysMain", "Start"): (2, 4), ("HKLM", S + "Fax", "Start"): (3, 4),
                    ("HKCU", "Software\\Microsoft\\GameBar", "AutoGameModeEnabled"): (0, 4),
                    ("HKLM", r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled"): (1, 4)}
        self.corriendo = {"DiagTrack", "Spooler"}
        self.tareas = {("\\Microsoft\\Windows\\Customer Experience Improvement Program\\", "Consolidator"): "Ready",
                       ("\\Microsoft\\Windows\\Application Experience\\", "ProgramDataUpdater"): "Disabled"}
        self.apps = [{"Name": "Microsoft.BingNews", "PackageFullName": "BN_1", "InstallLocation": "C:\\a"},
                     {"Name": "Microsoft.WindowsStore", "PackageFullName": "WS_1", "InstallLocation": "C:\\b"},
                     {"Name": "king.com.CandyCrush", "PackageFullName": "CC_1", "InstallLocation": "C:\\c"}]
        self.inicio = [Entrada("Spotify", "spotify.exe", "Usuario"), Entrada("Realtek", "rtk.exe", "Sistema"),
                       Entrada("Discord", "discord.exe", "Usuario")]
        self.punto_ok, self.admin, self.cmds, self.puntos = punto_ok, admin, [], []
        self.spi = {g: 1 for _c, g, _s, _v, _d in nucleo.SPI_AJUSTES}  # todo activado al principio
        self.spi[0x200A] = 1  # suavizado estándar (no ClearType)
        self.fondos = []
        self.reg[("HKCU", r"Control Panel\Desktop", "WallPaper")] = ("C:\\Users\\x\\foto.jpg", 1)
        self.reg[("HKCU", r"Control Panel\Colors", "Background")] = ("10 20 30", 1)

    def is_admin(self): return self.admin
    def pausa(self, s): pass

    def reg_get(self, h, p, n):
        k = (h, p, n)
        return (True,) + self.reg[k] if k in self.reg else (False, None, None)

    def reg_set(self, h, p, n, t, v): self.reg[(h, p, n)] = (v, t)
    def reg_del(self, h, p, n): self.reg.pop((h, p, n), None)
    def servicio_corriendo(self, n): return n in self.corriendo

    def spi_get(self, accion): return self.spi.get(accion)

    def spi_set(self, accion, valor, via="pv"):
        sets = {s: g for _c, g, s, _v, _d in nucleo.SPI_AJUSTES}
        if accion not in sets: return False
        self.spi[sets[accion]] = valor
        return True

    def fondo_aplicar(self, ruta, color): self.fondos.append((ruta, color))

    def run(self, cmd, timeout=None):
        self.cmds.append(cmd)
        if cmd[:2] == ["sc", "stop"]: self.corriendo.discard(cmd[2])
        if cmd[:2] == ["sc", "start"]: self.corriendo.add(cmd[2])
        if cmd[:2] == ["powercfg", "/getactivescheme"]:
            return 0, "GUID del plan de energía: 381b4222-f694-41f0-9685-ff5bb260df2e (Equilibrado)"
        return 0, ""

    def ps(self, sc, t=300):
        if "Checkpoint-Computer" in sc and self.punto_ok: self.puntos.append(sc)
        if "Get-ComputerRestorePoint" in sc: return 0, str(len(self.puntos))
        return 0, ""

    def tarea_estado(self, r, n): return self.tareas.get((r, n), "NOEXISTE")
    def tarea_set(self, r, n, h): self.tareas[(r, n)] = "Ready" if h else "Disabled"; return True
    def listar_appx(self): return list(self.apps)
    def quitar_appx(self, f): self.apps = [a for a in self.apps if a["PackageFullName"] != f]; return True
    def registrar_appx(self, l): return False
    def listar_inicio(self): return self.inicio
    def set_inicio(self, e, h): e.habilitado = h
    def detectar_equipo(self): return {"media": "SSD", "bateria": False, "impresoras": 0, "ram_gb": 8, "windows": "10.0"}

    def instantanea(self):
        return copy.deepcopy((self.reg, self.corriendo, self.tareas, [(i.nombre, i.habilitado) for i in self.inicio], self.spi))


class WingetFalso:
    """Imita winget: instalados, existencia de IDs y códigos de salida."""
    def __init__(self, presente=True, registra=False, descarga_ok=False):
        self.inst = {"google.chrome"}
        self.log = []
        self.presente, self.registra, self.descarga_ok = presente, registra, descarga_ok

    def __call__(self, cmd, timeout=None):
        self.log.append(cmd)
        if cmd[:2] == ["winget", "--version"]: return (0, "v1.9.0") if self.presente else (127, "no se encontró")
        if cmd[:2] == ["winget", "export"]:
            ruta = cmd[cmd.index("-o") + 1]
            with open(ruta, "w") as f:
                json.dump({"Sources": [{"Packages": [{"PackageIdentifier": i} for i in self.inst]}]}, f)
            return 0, ""
        if cmd[:2] == ["winget", "show"]:
            return (0, "") if cmd[3] != "Microsoft.DotNet.DesktopRuntime.9" else (0x8A150014, "No package")
        if cmd[:2] == ["winget", "install"]:
            i = cmd[3]
            if i == "Valve.Steam": return 3010, ""
            if i == "Discord.Discord": return 1603, "fallo del instalador"
            return 0, ""
        if cmd[0] == "powershell":
            texto = " ".join(cmd)
            if "RegisterByFamilyName" in texto and self.registra: self.presente = True
            if "msixbundle" in texto and self.descarga_ok: self.presente = True
            return 0, ""
        return 1, ""
