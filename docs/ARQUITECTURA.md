# Arquitectura

```text
              ┌──────────────┐
              │   gui.py     │  interfaz (tkinter) - hilos + cola
              └──────┬───────┘
        ┌────────────┼───────────────┐
        ▼            ▼               ▼
  ┌───────────┐ ┌───────────┐ ┌────────────────┐
  │ nucleo.py │ │instalador │ │  __main__.py   │ (consola)
  │ (niveles) │ │  .py      │ └────────────────┘
  └─────┬─────┘ └─────┬─────┘
        │             │
        └──────┬──────┘
               ▼
        ┌──────────────┐        ┌────────────┐
        │ limpieza.py  │ ◄───── │ config.py  │
        └──────────────┘        └────────────┘
```

## Módulos

- **`limpieza.py`**: funciones de bajo nivel. Expansión segura de rutas (descarta raíces de disco, perfil de usuario y carpetas del sistema), borrado del *contenido* de carpetas sin seguir enlaces simbólicos, papelera, `info_sistema()`, y la lista `TAREAS` (limpiezas y acciones de mantenimiento).
- **`nucleo.py`**: el motor.
  - `Entorno`: **única** puerta hacia Windows (registro, `sc`, PowerShell, tareas programadas, apps de la Tienda, inicio). En las pruebas se reemplaza por `EntornoFalso`.
  - `Cambio` y sus subtipos: `CambioLimpieza`, `CambioRegistro`, `CambioServicios`, `CambioTareas`, `CambioApps`, `CambioInicio`, `CambioEnergia`, `CambioHibernacion`. Cada uno sabe **`aplica()`** (¿tiene sentido en este equipo?), **`aplicar()`** (guarda el estado previo) y **`revertir()`**.
  - `CATALOGO`: lista ordenada de cambios. Cada uno declara su `nivel` mínimo, riesgo, texto de «qué hace» y «consecuencia», y si viene marcado por defecto (puede depender del equipo).
  - `plan()` (vista previa), `aplicar()`, `restaurar()`, `crear_punto_restauracion()`.
- **`instalador.py`**: `CATALOGO` de programas, `PERFILES`, y `Winget` (wrapper con `run` inyectable): `disponible`, `instalados` (vía `winget export`, JSON independiente del idioma), `existe`, `instalar` (mapea códigos de salida), `actualizar_todo`.
- **`gui.py`**: `App` (pestañas), `ListaCheck` (tabla con casillas), `DialogoConfirmacion`. Las tareas largas corren en hilos y se comunican por una `queue`; los diálogos son métodos reemplazables para poder probar la GUI.
- **`ajustes.py`**: idioma y tema, guardados por usuario y validados contra listas cerradas.
- **`i18n.py` + `idiomas/`**: traducciones (la clave es el texto en español; hay fallback a inglés).
- **`temas.py`**: paletas claro/oscuro con acento mint.

## Flujo de `aplicar(nivel)`

1. Verifica que haya permisos de administrador.
2. `plan()` → lista de cambios del nivel (acumulativo) que **aplican** a este equipo, filtrada por lo que el usuario dejó marcado.
3. **Punto de restauración**: `Enable-ComputerRestore`, baja temporalmente el límite de «uno cada 24 h», `Checkpoint-Computer`, y **verifica** con `Get-ComputerRestorePoint` que existe. Si falla → aborta sin cambios.
4. Crea la sesión `sesiones/<AAAAMMDD_HHMMSS>/` y `manifest.json`.
5. Por cada cambio: `aplicar()` va llenando un `estado` (valores previos) y el manifiesto **se guarda después de cada cambio**. Un error en un cambio no frena a los demás.
6. Genera `informe.txt` (también copia al Escritorio).

`restaurar()` lee el manifiesto y llama a `revertir()` en **orden inverso**.

### Formato del manifiesto (resumen)

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

## Cómo agregar un cambio

1. Elegí el subtipo adecuado (o creá uno heredando de `Cambio` con `aplica/aplicar/revertir`).
2. Agregalo a `_catalogo()` en `nucleo.py` con `nivel`, `riesgo`, texto claro de **qué hace** y **consecuencia**, y `defecto` (bool o función del equipo).
3. `aplicar()` debe guardar en `estado` **todo** lo necesario para revertir.
4. Agregá una prueba en `tests/test_nucleo.py` (el test de «aplicar y restaurar deja todo igual» ya cubre cualquier cambio nuevo que no borre archivos).
5. `python scripts/generar_docs.py`.

## Decisiones de diseño

- **Reversibilidad antes que potencia:** no se incluyó nada que no se pueda deshacer o que sea dudoso (por ejemplo, limpiadores de registro).
- **Un solo punto de contacto con el sistema (`Entorno`)** para poder probar toda la lógica sin Windows.
- **Sin dependencias externas** en tiempo de ejecución: solo biblioteca estándar.
- **Opciones según el equipo** en lugar de un único perfil fijo, para evitar que «optimizar» deje a alguien sin impresora o sin Bluetooth.

## Widgets redondeados
`bottimint/widgets.py` dibuja con Canvas: `BotonRedondo`, `SelectorNivel`, `Tarjeta` y `DialogoSiNo`. Las pestañas, filas del Treeview, el Combobox y el marco de la ventana del sistema siguen con esquinas rectas (límite de tkinter/ttk).
