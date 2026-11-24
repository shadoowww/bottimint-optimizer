# Architecture

Module, class and function names are in Spanish (as is the code base); this document explains them in English.

```text
              ┌──────────────┐
              │   gui.py     │  interface (tkinter) - threads + queue
              └──────┬───────┘
        ┌────────────┼───────────────┐
        ▼            ▼               ▼
  ┌───────────┐ ┌───────────┐ ┌────────────────┐
  │ nucleo.py │ │instalador │ │  __main__.py   │ (command line)
  │ (levels)  │ │  .py      │ └────────────────┘
  └─────┬─────┘ └─────┬─────┘
        │             │
        └──────┬──────┘
               ▼
        ┌──────────────┐
        │ limpieza.py  │
        └──────────────┘
```

## Modules

- **`limpieza.py`** (cleanup): low-level functions. Safe path expansion (discards drive roots, the user profile and system folders), deleting the *contents* of folders without following symbolic links, recycle bin, `info_sistema()` (system info), and the `TAREAS` list (cleanups and maintenance actions).
- **`nucleo.py`** (core): the engine.
  - `Entorno` (environment): the **only** gateway to Windows (registry, `sc`, PowerShell, scheduled tasks, Store apps, startup). In tests it is replaced by `EntornoFalso`.
  - `Cambio` (change) and its subtypes: `CambioLimpieza`, `CambioRegistro`, `CambioServicios`, `CambioTareas`, `CambioApps`, `CambioInicio`, `CambioEnergia`, `CambioHibernacion`. Each one knows **`aplica()`** (does it make sense on this machine?), **`aplicar()`** (saves the previous state) and **`revertir()`** (undo).
  - `CATALOGO`: ordered list of changes. Each declares its minimum level (`nivel`), risk, "what it does" and "consequence" texts, and whether it is checked by default (it may depend on the machine).
  - `plan()` (preview), `aplicar()`, `restaurar()`, `crear_punto_restauracion()`.
- **`instalador.py`** (installer): program `CATALOGO`, `PERFILES` (profiles) and `Winget` (wrapper with an injectable `run`): `disponible`, `instalados` (via `winget export`, language-independent JSON), `existe`, `instalar` (maps exit codes), `actualizar_todo`.
- **`gui.py`**: `App` (tabs), `ListaCheck` (table with checkboxes), `DialogoConfirmacion`. Long tasks run in threads and talk through a `queue`; dialogs are replaceable methods so the GUI can be tested.
- **`widgets.py`**: Canvas-drawn rounded widgets: `BotonRedondo`, `SelectorNivel`, `Tarjeta` and `DialogoSiNo`. Tabs, Treeview rows, the Combobox and the operating-system window frame keep square corners (a tkinter/ttk limit).
- **`ajustes.py`**: language and theme, stored per user and validated against closed lists.
- **`i18n.py` + `idiomas/`**: translations (the key is the Spanish text; falls back to English, then to the original).
- **`temas.py`**: light/dark palettes with a mint accent.

## Flow of `aplicar(nivel)`

1. Checks for administrator rights.
2. `plan()` → list of changes of the level (cumulative) that **apply** to this machine, filtered by what the user left checked.
3. **Restore point**: `Enable-ComputerRestore`, temporarily lowers the "one every 24 h" limit, `Checkpoint-Computer`, and **verifies** with `Get-ComputerRestorePoint` that it exists. If that fails → abort with no changes.
4. Creates the session `sesiones/<YYYYMMDD_HHMMSS>/` and `manifest.json`.
5. For each change: `aplicar()` fills in an `estado` (previous values) and the manifest is **saved after every change**. An error in one change does not stop the others.
6. Generates `informe.txt` (also copied to the Desktop).

`restaurar()` reads the manifest and calls `revertir()` in **reverse order**.

### Manifest format (summary)

```json
{
  "sesion": "20261124_130000",
  "nivel": "extremo",
  "punto_restauracion": "BottiMint 20261124_130000 extremo",
  "equipo": {"media": "SSD", "bateria": false, "impresoras": 0, "ram_gb": 16},
  "cambios": [
    {"id": "svc_sysmain", "ok": true, "reversible": true, "resultado": "1 servicios ajustados",
     "estado": {"servicios": [{"nombre": "SysMain", "start": 2, "corriendo": true}]}}
  ],
  "restaurada": false
}
```

## How to add a change

1. Pick the right subtype (or create one inheriting from `Cambio` with `aplica/aplicar/revertir`).
2. Add it to `_catalogo()` in `nucleo.py` with `nivel`, `riesgo`, clear **what it does** and **consequence** texts, and `defecto` (a bool or a function of the machine).
3. `aplicar()` must store in `estado` **everything** needed to revert.
4. Add a test in `tests/test_nucleo.py` (the "apply and restore leaves everything the same" test already covers any new change that does not delete files).
5. Add the translations of the new texts in `bottimint/idiomas/` (`test_idiomas` fails if one is missing).
6. `python scripts/generar_docs.py`.

## Design decisions

- **Reversibility before power:** nothing that cannot be undone or that is dubious was included (for example, registry cleaners).
- **A single point of contact with the system (`Entorno`)** so all the logic can be tested without Windows.
- **No external dependencies** at runtime: standard library only.
- **Machine-dependent options** instead of one fixed profile, so that "optimizing" does not leave someone without a printer or Bluetooth.
