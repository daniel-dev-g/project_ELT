"""gui.py — FlowELT Desktop App"""
import asyncio
import uuid
import yaml
import flet as ft

from src.state_manager.core.adapter_db.factory_db import factory_db
from src.validators import check_db_connection
from main import _run_tasks


ENGINES = {
    "postgres": {
        "label": "PostgreSQL",
        "port": "5432",
        "db_engine": "postgres",
    },
    "mariadb": {
        "label": "MariaDB",
        "port": "3306",
        "db_engine": "mariadb",
    },
    "sqlserver": {
        "label": "SQL Server",
        "port": "1433",
        "db_engine": "sqlserver",
    },
}

ACCENT = "#3b82f6"
ACCENT_DIM = "#2563eb"
SUCCESS = "#059669"
SUCCESS_BG = "#d1fae5"
SUCCESS_DIM = "#047857"
ERROR = "#dc2626"
ERROR_BG = "#fee2e2"
BG = "#f8fafc"
SURFACE = "#f0f9ff"
SURFACE_TASK = "#ffffff"
TEXT = "#1e293b"
MUTED = "#64748b"
BORDER = "#bfdbfe"
BORDER_TASK = "#e2e8f0"


def _field(**kwargs) -> ft.TextField:
    return ft.TextField(
        border_color=BORDER,
        focused_border_color=ACCENT,
        cursor_color=ACCENT,
        border_radius=8,
        text_size=14,
        bgcolor="#ffffff",
        filled=True,
        fill_color="#ffffff",
        label_style=ft.TextStyle(color=MUTED),
        **kwargs,
    )


def _small_field(**kwargs) -> ft.TextField:
    return ft.TextField(
        border_color=BORDER_TASK,
        focused_border_color=ACCENT,
        cursor_color=ACCENT,
        border_radius=6,
        text_size=13,
        bgcolor="#ffffff",
        filled=True,
        fill_color="#ffffff",
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        label_style=ft.TextStyle(color=MUTED, size=12),
        **kwargs,
    )


async def main(page: ft.Page):
    page.title = "FlowELT"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ACCENT,
            surface="#ffffff",
            surface_container_highest="#f1f5f9",
        )
    )
    page.bgcolor = BG
    page.padding = 0
    page.window.width = 600
    page.window.height = 820
    page.window.min_width = 560
    page.window.min_height = 600
    page.window.resizable = True

    # ── Connection fields ────────────────────────────────────────────────────
    f_host = _field(label="Host", value="localhost", expand=True)
    f_port = _field(label="Puerto", value="5432", width=120)
    f_db = _field(label="Base de datos")
    f_user = _field(label="Usuario")
    f_pass = _field(label="Contraseña", password=True, can_reveal_password=True)

    # ── Status banner ────────────────────────────────────────────────────────
    status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=18)
    status_msg = ft.Text("", size=13)
    status_box = ft.Container(
        content=ft.Row([status_icon, status_msg], spacing=8),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        visible=False,
    )

    # ── Engine dropdown ──────────────────────────────────────────────────────
    engine_dd = ft.Dropdown(
        label="Motor de base de datos",
        value="postgres",
        border_color=BORDER,
        focused_border_color=ACCENT,
        border_radius=8,
        text_size=14,
        bgcolor="#ffffff",
        filled=True,
        fill_color="#ffffff",
        label_style=ft.TextStyle(color=MUTED),
        options=[
            ft.dropdown.Option(key=k, text=v["label"])
            for k, v in ENGINES.items()
        ],
    )

    def on_engine_change(e):
        f_port.value = ENGINES[engine_dd.value]["port"]
        status_box.visible = False
        page.update()

    engine_dd.on_change = on_engine_change

    # ── Connect button ───────────────────────────────────────────────────────
    btn_icon = ft.Icon(ft.Icons.CABLE, color="#ffffff", size=18)
    btn_spinner = ft.ProgressRing(
        width=16, height=16, stroke_width=2, color="#ffffff", visible=False
    )
    btn_label = ft.Text("Conectar", color="#ffffff", size=14, weight=ft.FontWeight.W_600)
    btn = ft.Container(
        content=ft.Row(
            [btn_icon, btn_spinner, btn_label],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
        ),
        bgcolor=ACCENT,
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=28, vertical=12),
        ink=True,
    )

    def set_loading(loading: bool):
        btn_icon.visible = not loading
        btn_spinner.visible = loading
        btn_label.value = "Conectando..." if loading else "Conectar"
        btn.bgcolor = ACCENT_DIM if loading else ACCENT
        btn.on_click = None if loading else do_connect
        page.update()

    def validate_conn() -> str | None:
        if not f_host.value.strip():
            return "El campo Host es obligatorio."
        if not f_port.value.strip():
            return "El campo Puerto es obligatorio."
        if not f_db.value.strip():
            return "Ingresa el nombre de la base de datos."
        if not f_user.value.strip():
            return "Ingresa el usuario."
        return None

    # ── Pipeline state ───────────────────────────────────────────────────────
    tasks_data: list[dict] = []
    task_list = ft.Column(spacing=10)
    _adapter: list = []   # [db_adapter] after successful connect
    _db_cfg: list = []    # [db_cfg dict] after successful connect

    # ── Task row builder ─────────────────────────────────────────────────────
    def make_task_row(file_path: str) -> ft.Container:
        f_table = _small_field(label="Tabla destino", expand=True)
        f_schema = _small_field(label="Schema", width=100)
        delim_dd = ft.Dropdown(
            value=";",
            width=100,
            border_color=BORDER_TASK,
            focused_border_color=ACCENT,
            border_radius=6,
            text_size=13,
            bgcolor="#ffffff",
            filled=True,
            fill_color="#ffffff",
            label="Delimitador",
            label_style=ft.TextStyle(color=MUTED, size=12),
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            options=[
                ft.dropdown.Option(key=";", text=";"),
                ft.dropdown.Option(key=",", text=","),
                ft.dropdown.Option(key="|", text="|"),
                ft.dropdown.Option(key="\t", text="\\t"),
            ],
        )
        cb_active = ft.Checkbox(
            label="Activo",
            value=True,
            active_color=ACCENT,
            label_style=ft.TextStyle(size=13, color=TEXT),
        )
        cb_create = ft.Checkbox(
            label="Crear tabla si no existe",
            value=True,
            active_color=ACCENT,
            label_style=ft.TextStyle(size=13, color=TEXT),
        )

        task = {
            "file": file_path,
            "f_table": f_table,
            "f_schema": f_schema,
            "delim_dd": delim_dd,
            "cb_active": cb_active,
            "cb_create": cb_create,
        }
        tasks_data.append(task)

        file_name = file_path.split("/")[-1].split("\\")[-1]
        row_ref: list[ft.Container] = []

        def remove(_):
            tasks_data.remove(task)
            task_list.controls.remove(row_ref[0])
            update_pipeline_ui()

        row = ft.Container(
            bgcolor=SURFACE_TASK,
            border_radius=12,
            border=ft.Border.all(1, BORDER_TASK),
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            shadow=ft.BoxShadow(blur_radius=8, color="#0000000d", offset=ft.Offset(0, 2)),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.INSERT_DRIVE_FILE, color=ACCENT, size=16),
                            ft.Text(
                                file_name,
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color=TEXT,
                                expand=True,
                            ),
                            ft.Text(
                                file_path,
                                size=10,
                                color=MUTED,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color=MUTED,
                                icon_size=16,
                                on_click=remove,
                                tooltip="Eliminar",
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1, color=BORDER_TASK),
                    ft.Row(
                        [f_table, f_schema, delim_dd],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Row([cb_active, cb_create], spacing=24),
                ],
            ),
        )
        row_ref.append(row)
        return row

    # ── File picker ──────────────────────────────────────────────────────────
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    async def open_picker(_):
        files = await file_picker.pick_files(
            allow_multiple=True,
            allowed_extensions=["csv", "txt"],
        )
        if files:
            for f in files:
                row = make_task_row(f.path)
                task_list.controls.append(row)
            update_pipeline_ui()

    # ── Run status banner ────────────────────────────────────────────────────
    run_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=18)
    run_msg = ft.Text("", size=13)
    run_box = ft.Container(
        content=ft.Row([run_icon, run_msg], spacing=8),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        visible=False,
    )

    # ── Action buttons ───────────────────────────────────────────────────────
    btn_save = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SAVE_OUTLINED, color=ACCENT, size=16),
                ft.Text("Guardar YAML", color=ACCENT, size=13, weight=ft.FontWeight.W_500),
            ],
            spacing=6,
            tight=True,
        ),
        bgcolor="#ffffff",
        border_radius=8,
        border=ft.Border.all(1, ACCENT),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        ink=True,
    )

    run_btn_icon = ft.Icon(ft.Icons.PLAY_ARROW, color="#ffffff", size=16)
    run_btn_spinner = ft.ProgressRing(
        width=14, height=14, stroke_width=2, color="#ffffff", visible=False
    )
    run_btn_label = ft.Text(
        "Ejecutar pipeline", color="#ffffff", size=13, weight=ft.FontWeight.W_600
    )
    btn_run = ft.Container(
        content=ft.Row(
            [run_btn_icon, run_btn_spinner, run_btn_label],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
        ),
        bgcolor=SUCCESS,
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        ink=True,
        expand=True,
    )

    action_bar = ft.Container(
        visible=False,
        content=ft.Row([btn_save, btn_run], spacing=10),
    )

    # ── Pipeline section layout ──────────────────────────────────────────────
    pipeline_section = ft.Container(
        visible=False,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Container(height=8),
                ft.Container(
                    width=540,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.FOLDER_COPY_OUTLINED, color=ACCENT, size=18),
                                    ft.Text(
                                        "Pipeline de carga",
                                        size=15,
                                        weight=ft.FontWeight.W_600,
                                        color=TEXT,
                                        expand=True,
                                    ),
                                    ft.Container(
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.ADD, color=ACCENT, size=14),
                                                ft.Text(
                                                    "Agregar CSV",
                                                    color=ACCENT,
                                                    size=12,
                                                    weight=ft.FontWeight.W_500,
                                                ),
                                            ],
                                            spacing=4,
                                            tight=True,
                                        ),
                                        bgcolor="#eff6ff",
                                        border_radius=6,
                                        border=ft.Border.all(1, BORDER),
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                        ink=True,
                                        on_click=open_picker,
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            task_list,
                            action_bar,
                            run_box,
                        ],
                    ),
                ),
            ],
        ),
    )

    # ── Sync action_bar visibility ───────────────────────────────────────────
    def update_pipeline_ui():
        has_tasks = bool(task_list.controls)
        action_bar.visible = has_tasks
        if not has_tasks:
            run_box.visible = False
        page.update()

    # ── Task dict for yaml/pipeline ──────────────────────────────────────────
    def build_task(t: dict) -> dict:
        return {
            "name": f"Carga {t['f_table'].value.strip() or 'sin nombre'}",
            "file": t["file"],
            "delimiter": t["delim_dd"].value,
            "encoding": "utf8",
            "table_destination": t["f_table"].value.strip(),
            "crear_tabla_si_no_existe": t["cb_create"].value,
            "schema": t["f_schema"].value.strip(),
            "active": t["cb_active"].value,
        }

    # ── Connect handler ──────────────────────────────────────────────────────
    async def do_connect(_):
        err = validate_conn()
        if err:
            _show_status(False, err)
            return

        set_loading(True)
        status_box.visible = False
        page.update()

        try:
            key = engine_dd.value
            cfg = {
                "db_engine": ENGINES[key]["db_engine"],
                "host": f_host.value.strip(),
                "port": f_port.value.strip(),
                "database": f_db.value.strip(),
                "username": f_user.value.strip(),
                "password": f_pass.value,
            }
            if key == "sqlserver":
                cfg["server"] = f"{cfg['host']},{cfg['port']}"
                cfg["driver"] = "ODBC Driver 18 for SQL Server"
                cfg["trusted_connection"] = "no"
                cfg["encrypt"] = "no"

            loop = asyncio.get_event_loop()
            adapter = factory_db(cfg)
            label = ENGINES[key]["label"]
            addr = f"{f_host.value.strip()}:{f_port.value.strip()}"
            try:
                ok, db_err = await asyncio.wait_for(
                    loop.run_in_executor(None, check_db_connection, adapter.engine),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                _show_status(False, "Tiempo de espera agotado — verifica host y puerto")
                return

            if ok:
                _show_status(True, f"Conexión exitosa — {label} en {addr}")
                _adapter.clear()
                _adapter.append(adapter)
                _db_cfg.clear()
                _db_cfg.append({
                    "db_engine": ENGINES[key]["db_engine"],
                    "default_schema": None,
                })
                pipeline_section.visible = True
            else:
                _show_status(False, db_err or "No se pudo conectar")
        except Exception as ex:
            _show_status(False, str(ex))
        finally:
            set_loading(False)

    def _show_status(ok: bool, msg: str):
        color = SUCCESS if ok else ERROR
        bg = SUCCESS_BG if ok else ERROR_BG
        status_icon.name = ft.Icons.CHECK_CIRCLE if ok else ft.Icons.ERROR
        status_icon.color = color
        status_msg.value = msg
        status_msg.color = color
        status_box.bgcolor = bg
        status_box.border = ft.Border.all(1, color)
        status_box.visible = True
        page.update()

    # ── Save handler ─────────────────────────────────────────────────────────
    def do_save(_):
        if not tasks_data:
            return
        pipeline_cfg = {"task": [build_task(t) for t in tasks_data]}
        with open("config/pipeline.yaml", "w", encoding="utf-8") as fh:
            yaml.dump(
                pipeline_cfg, fh,
                allow_unicode=True, default_flow_style=False, sort_keys=False
            )
        _show_run_status(True, "Guardado en config/pipeline.yaml")

    # ── Run loading helpers ──────────────────────────────────────────────────
    def set_run_loading(loading: bool):
        run_btn_icon.visible = not loading
        run_btn_spinner.visible = loading
        run_btn_label.value = "Ejecutando..." if loading else "Ejecutar pipeline"
        btn_run.bgcolor = SUCCESS_DIM if loading else SUCCESS
        btn_run.on_click = None if loading else do_run
        btn_save.on_click = None if loading else do_save
        page.update()

    def _show_run_status(ok: bool, msg: str):
        color = SUCCESS if ok else ERROR
        bg = SUCCESS_BG if ok else ERROR_BG
        run_icon.name = ft.Icons.CHECK_CIRCLE if ok else ft.Icons.ERROR
        run_icon.color = color
        run_msg.value = msg
        run_msg.color = color
        run_box.bgcolor = bg
        run_box.border = ft.Border.all(1, color)
        run_box.visible = True
        page.update()

    # ── Execute handler ──────────────────────────────────────────────────────
    async def do_run(_):
        if not _adapter:
            _show_run_status(False, "No hay conexión activa. Vuelve a conectar.")
            return

        missing = [t for t in tasks_data if not t["f_table"].value.strip()]
        if missing:
            _show_run_status(False, "Completa 'Tabla destino' en todas las tareas.")
            return

        pipeline_cfg = {"task": [build_task(t) for t in tasks_data]}
        with open("config/pipeline.yaml", "w", encoding="utf-8") as fh:
            yaml.dump(
                pipeline_cfg, fh,
                allow_unicode=True, default_flow_style=False, sort_keys=False
            )

        execution_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        set_run_loading(True)
        run_box.visible = False
        page.update()

        try:
            summary = await asyncio.wait_for(
                loop.run_in_executor(
                    None, _run_tasks,
                    pipeline_cfg, _adapter[0], execution_id, _db_cfg[0]
                ),
                timeout=300.0,
            )
            ok_count = summary["successful_tasks"]
            total = summary["total_tasks"]
            rows = summary["total_rows"]
            failed = summary["failed_tasks"]
            if failed == 0:
                _show_run_status(
                    True,
                    f"Completado — {ok_count}/{total} tareas · {rows:,} filas insertadas"
                )
            else:
                _show_run_status(
                    False,
                    f"Parcial — {ok_count} OK / {failed} fallidas · {rows:,} filas"
                )
        except asyncio.TimeoutError:
            _show_run_status(False, "Tiempo de espera agotado (>5 min)")
        except Exception as ex:
            _show_run_status(False, str(ex))
        finally:
            set_run_loading(False)

    # ── Wire handlers ────────────────────────────────────────────────────────
    btn.on_click = do_connect
    btn_save.on_click = do_save
    btn_run.on_click = do_run

    # ── Layout ───────────────────────────────────────────────────────────────
    page.add(
        ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.Padding.symmetric(horizontal=30, vertical=28),
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    ft.Text("FlowELT", size=32, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(
                        "Carga masiva nativa hacia tu base de datos",
                        size=13,
                        color=MUTED,
                    ),
                    ft.Container(height=20),
                    ft.Container(
                        width=540,
                        bgcolor=SURFACE,
                        border_radius=16,
                        padding=24,
                        border=ft.Border.all(1, BORDER),
                        shadow=ft.BoxShadow(
                            blur_radius=28,
                            color="#0000001a",
                            offset=ft.Offset(0, 8),
                        ),
                        content=ft.Column(
                            spacing=12,
                            controls=[
                                ft.Text(
                                    "Conexión a base de datos",
                                    size=15,
                                    weight=ft.FontWeight.W_600,
                                    color=TEXT,
                                ),
                                ft.Text(
                                    "Parámetros de acceso al motor de base de datos",
                                    size=12,
                                    color=MUTED,
                                ),
                                ft.Divider(height=1, color=BORDER),
                                engine_dd,
                                ft.Row([f_host, f_port], spacing=12),
                                f_db,
                                f_user,
                                f_pass,
                                ft.Row([btn], alignment=ft.MainAxisAlignment.END),
                            ],
                        ),
                    ),
                    ft.Container(height=10),
                    ft.Container(width=540, content=status_box),
                    pipeline_section,
                    ft.Container(height=16),
                ],
            ),
        )
    )


ft.run(main)