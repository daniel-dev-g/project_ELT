"""gui.py — FlowELT Desktop App"""
import asyncio
import os
import subprocess
import sys
import time
import uuid
import webbrowser
import yaml
import flet as ft

from src.state_manager.core.adapter_db.factory_db import factory_db
from src.validators import check_db_connection
from main import _run_tasks
from src.csv_analisys import CSVAnalysis
from src.log_csv import get_log_path, registrar_log
from src.visualization.log_dashboard import generate_dashboard


ENGINES = {
    "postgres": {"label": "PostgreSQL", "port": "5432", "db_engine": "postgres"},
    "mariadb":  {"label": "MariaDB",    "port": "3306", "db_engine": "mariadb"},
    "sqlserver":{"label": "SQL Server", "port": "1433", "db_engine": "sqlserver"},
}

ACCENT      = "#3b82f6"
ACCENT_DIM  = "#2563eb"
SUCCESS     = "#3b82f6"
SUCCESS_BG  = "#eff6ff"
SUCCESS_DIM = "#2563eb"
RUN_BTN     = "#00B427"
RUN_BTN_DIM = "#21D321"
ERROR       = "#dc2626"
ERROR_BG    = "#fee2e2"
BG          = "#f8fafc"
SURFACE     = "#f0f9ff"
SURFACE_ROW = "#ffffff"
HEADER_BG   = "#f1f5f9"
TEXT        = "#1e293b"
MUTED       = "#64748b"
BORDER      = "#bfdbfe"
BORDER_ROW  = "#e2e8f0"

CONTENT_W   = 920   # usable width inside 30px horizontal padding


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


def _row_field(**kwargs) -> ft.TextField:
    return ft.TextField(
        border_color=BORDER_ROW,
        focused_border_color=ACCENT,
        cursor_color=ACCENT,
        border_radius=6,
        text_size=12,
        bgcolor="#ffffff",
        filled=True,
        fill_color="#ffffff",
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        label_style=ft.TextStyle(color=MUTED, size=11),
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
    page.window.width = 980
    page.window.height = 820
    page.window.min_width = 800
    page.window.min_height = 500
    page.window.resizable = True

    # ── Connection fields ────────────────────────────────────────────────────
    f_host = _field(label="Host", value="localhost", expand=True)
    f_port = _field(label="Puerto", value="5432", width=110)
    f_db   = _field(label="Base de datos")
    f_user = _field(label="Usuario")
    f_pass = _field(label="Contraseña", password=True, can_reveal_password=True)

    # ── Engine pill selector ─────────────────────────────────────────────────
    _selected_engine: list[str] = ["postgres"]
    _pill_refs: dict = {}

    def select_engine(key: str):
        _selected_engine[0] = key
        f_port.value = ENGINES[key]["port"]
        for k, r in _pill_refs.items():
            on = k == key
            r["c"].bgcolor = "#eff6ff" if on else "#f8fafc"
            r["c"].border  = ft.Border.all(1.5 if on else 1,
                                           ACCENT if on else BORDER_ROW)
            r["t"].color   = ACCENT if on else MUTED
            r["d"].color   = ACCENT if on else "#cbd5e1"
        page.update()

    engine_pills = []
    for _k, _v in ENGINES.items():
        _on = _k == "postgres"
        _dot = ft.Icon(ft.Icons.CIRCLE, size=7,
                       color=ACCENT if _on else "#cbd5e1")
        _lbl = ft.Text(_v["label"], size=12, weight=ft.FontWeight.W_600,
                       color=ACCENT if _on else MUTED)
        _pill = ft.Container(
            content=ft.Row([_dot, _lbl], spacing=6, tight=True),
            bgcolor="#eff6ff" if _on else "#f8fafc",
            border_radius=10,
            border=ft.Border.all(1.5 if _on else 1,
                                 ACCENT if _on else BORDER_ROW),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            ink=True, expand=True,
            on_click=lambda e, k=_k: select_engine(k),
        )
        _pill_refs[_k] = {"c": _pill, "t": _lbl, "d": _dot}
        engine_pills.append(_pill)

    # ── Connect button ───────────────────────────────────────────────────────
    btn_icon    = ft.Icon(ft.Icons.ARROW_FORWARD, color="#ffffff", size=18)
    btn_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2,
                                  color="#ffffff", visible=False)
    btn_label   = ft.Text("Conectar", color="#ffffff", size=14,
                          weight=ft.FontWeight.W_600)
    btn = ft.Container(
        content=ft.Row(
            [btn_icon, btn_spinner, btn_label], spacing=8,
            alignment=ft.MainAxisAlignment.CENTER, tight=True,
        ),
        bgcolor=ACCENT, border_radius=10,
        padding=ft.Padding.symmetric(horizontal=28, vertical=14),
        ink=True,
    )

    def set_loading(loading: bool):
        btn_icon.visible    = not loading
        btn_spinner.visible = loading
        btn_label.value     = "Conectando..." if loading else "Conectar"
        btn.bgcolor         = ACCENT_DIM if loading else ACCENT
        btn.on_click        = None if loading else do_connect
        page.update()

    def validate_conn() -> str | None:
        if not f_host.value.strip(): return "El campo Host es obligatorio."
        if not f_port.value.strip(): return "El campo Puerto es obligatorio."
        if not f_db.value.strip():   return "Ingresa el nombre de la base de datos."
        if not f_user.value.strip(): return "Ingresa el usuario."
        return None

    # ── Connection card (View 1) ─────────────────────────────────────────────
    status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16)
    status_msg  = ft.Text("", size=12)
    status_box  = ft.Container(
        content=ft.Row([status_icon, status_msg], spacing=8),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        visible=False,
    )

    conn_card = ft.Container(
        width=480,
        bgcolor="#ffffff",
        border_radius=20,
        padding=ft.Padding(left=36, right=36, top=32, bottom=32),
        border=ft.Border.all(1, "#e2e8f0"),
        shadow=ft.BoxShadow(
            blur_radius=48, color="#00000012", offset=ft.Offset(0, 12),
        ),
        content=ft.Column(
            spacing=0,
            tight=True,
            controls=[
                # Header
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.STORAGE_ROUNDED,
                                            color=ACCENT, size=20),
                            bgcolor="#eff6ff",
                            border_radius=12,
                            padding=10,
                        ),
                        ft.Column(
                            [
                                ft.Text("Conexión a base de datos",
                                        size=16, weight=ft.FontWeight.BOLD,
                                        color=TEXT),
                                ft.Text("Define los parámetros de acceso al motor",
                                        size=12, color=MUTED),
                            ],
                            spacing=2, tight=True,
                        ),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=24),
                # Engine pills
                ft.Row(engine_pills, spacing=8),
                ft.Container(height=20),
                ft.Divider(height=1, color="#f1f5f9"),
                ft.Container(height=20),
                # Fields
                ft.Row([f_host, f_port], spacing=12),
                ft.Container(height=12),
                f_db,
                ft.Container(height=12),
                f_user,
                ft.Container(height=12),
                f_pass,
                ft.Container(height=16),
                status_box,
                ft.Container(height=16),
                btn,
            ],
        ),
    )

    # ── Connected bar (View 2 — top) ─────────────────────────────────────────
    conn_info = ft.Text("", size=13, color=TEXT, expand=True)
    connected_bar = ft.Container(
        width=CONTENT_W,
        visible=False,
        bgcolor=SUCCESS_BG,
        border_radius=10,
        border=ft.Border.all(1, SUCCESS),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        content=ft.Row(
            [
                ft.Icon(ft.Icons.CIRCLE, color=SUCCESS, size=10),
                conn_info,
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.LOGOUT, color=MUTED, size=14),
                            ft.Text("Desconectar", color=MUTED, size=12),
                        ],
                        spacing=4, tight=True,
                    ),
                    on_click=lambda _: do_disconnect(),
                    ink=True,
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    # ── Pipeline state ───────────────────────────────────────────────────────
    tasks_data: list[dict] = []
    task_list = ft.Column(spacing=4)
    _adapter: list = []
    _db_cfg:  list = []

    # ── Task row ─────────────────────────────────────────────────────────────
    def make_task_row(
        file_path: str,
        table: str = "",
        schema: str = "",
        delimiter: str = ";",
        active: bool = True,
        create_table: bool = True,
        truncate: bool = False,
    ) -> ft.Container:
        f_table  = _row_field(label="Tabla destino", expand=True, value=table)
        f_schema = _row_field(label="Schema", width=88, value=schema)

        delim_dd = ft.Dropdown(
            value=delimiter, width=90,
            border_color=BORDER_ROW, focused_border_color=ACCENT,
            border_radius=6, text_size=12,
            bgcolor="#ffffff", filled=True, fill_color="#ffffff",
            label="Delimitador", label_style=ft.TextStyle(color=MUTED, size=11),
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            options=[
                ft.dropdown.Option(key=";",  text=";"),
                ft.dropdown.Option(key=",",  text=","),
                ft.dropdown.Option(key="|",  text="|"),
                ft.dropdown.Option(key="\t", text="\\t"),
            ],
        )
        cb_active   = ft.Checkbox(
            value=active, active_color=ACCENT, tooltip="Activo"
        )
        cb_create   = ft.Checkbox(
            value=create_table, active_color=ACCENT, tooltip="Crear tabla si no existe"
        )
        truncate_cont_ref: list = []

        def on_truncate_change(e):
            if truncate_cont_ref:
                truncate_cont_ref[0].border = (
                    None if e.control.value
                    else ft.Border.all(1, "#fca5a5")
                )
                page.update()

        cb_truncate = ft.Checkbox(
            value=truncate, active_color=ERROR,
            tooltip="Truncar tabla antes de cargar (elimina todos los registros)",
            on_change=on_truncate_change,
        )
        truncate_cont = ft.Container(
            content=cb_truncate, width=80,
            alignment=ft.Alignment.CENTER,
            border=ft.Border.all(1, "#fca5a5") if not truncate else None,
            border_radius=6,
        )
        truncate_cont_ref.append(truncate_cont)

        task = {
            "file": file_path, "f_table": f_table, "f_schema": f_schema,
            "delim_dd": delim_dd, "cb_active": cb_active,
            "cb_create": cb_create, "cb_truncate": cb_truncate,
        }
        tasks_data.append(task)

        file_name = file_path.split("/")[-1].split("\\")[-1]
        row_ref: list[ft.Container] = []

        def remove(_):
            tasks_data.remove(task)
            task_list.controls.remove(row_ref[0])
            update_pipeline_ui()

        row = ft.Container(
            bgcolor=SURFACE_ROW,
            border_radius=8,
            border=ft.Border.all(1, BORDER_ROW),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.INSERT_DRIVE_FILE, color=ACCENT, size=14),
                    ft.Text(
                        file_name, size=12, color=TEXT,
                        weight=ft.FontWeight.W_500,
                        expand=2, no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        tooltip=file_path,
                    ),
                    f_table,
                    f_schema,
                    delim_dd,
                    ft.Container(
                        content=cb_active, width=52,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=cb_create, width=110,
                        alignment=ft.Alignment.CENTER,
                    ),
                    truncate_cont,
                    ft.IconButton(
                        icon=ft.Icons.CLOSE, icon_color=MUTED,
                        icon_size=14, on_click=remove, tooltip="Eliminar",
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        row_ref.append(row)
        return row

    # ── File picker ──────────────────────────────────────────────────────────
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def _get_defaults() -> dict:
        base = {"schema": "", "delimiter": ";",
                "crear_tabla_si_no_existe": True, "active": True,
                "truncate_before_load": False}
        try:
            if os.path.exists("config/pipeline.yaml"):
                with open("config/pipeline.yaml", "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
                base.update(data.get("_defaults", {}))
        except Exception:
            pass
        return base

    async def open_picker(_):
        files = await file_picker.pick_files(
            allow_multiple=True, allowed_extensions=["csv", "txt"],
        )
        if files:
            d = _get_defaults()
            existing_paths = {t["file"] for t in tasks_data}
            added = 0
            for f in files:
                if f.path in existing_paths:
                    continue
                existing_paths.add(f.path)
                task_list.controls.append(make_task_row(
                    f.path,
                    schema=d.get("schema", ""),
                    delimiter=d.get("delimiter", ";"),
                    active=d.get("active", True),
                    create_table=d.get("crear_tabla_si_no_existe", True),
                    truncate=d.get("truncate_before_load", False),
                ))
                added += 1
            if added:
                update_pipeline_ui()

    # ── Column header row ────────────────────────────────────────────────────
    task_header = ft.Container(
        visible=False,
        bgcolor=HEADER_BG,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        content=ft.Row(
            [
                ft.Container(width=14),
                ft.Text("Archivo",                   size=13, color=MUTED, expand=2,
                        weight=ft.FontWeight.W_500),
                ft.Text("Tabla destino",             size=13, color=MUTED, expand=True,
                        weight=ft.FontWeight.W_500),
                ft.Text("Schema",                    size=13, color=MUTED, width=88,
                        weight=ft.FontWeight.W_500),
                ft.Text("Delimitador",               size=13, color=MUTED, width=90,
                        weight=ft.FontWeight.W_500),
                ft.Text("Activo",                    size=13, color=MUTED, width=52,
                        weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
                ft.Text("Crear tabla si no existe",  size=13, color=MUTED, width=110,
                        weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER,
                        no_wrap=False),
                ft.Text("Truncar tabla", size=13, color=ERROR, width=80,
                        weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER,
                        no_wrap=False),
                ft.Container(width=36),
            ],
            spacing=6,
        ),
    )

    # ── Run status banner ────────────────────────────────────────────────────
    run_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=18)
    run_msg  = ft.Text("", size=13, expand=True)
    _dashboard_path: list = []   # [Path] tras ejecución exitosa

    dash_link = ft.Container(
        visible=False,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.OPEN_IN_BROWSER, size=14, color=ACCENT),
                ft.Text("Ver dashboard", size=12, color=ACCENT,
                        weight=ft.FontWeight.W_500),
            ],
            spacing=4, tight=True,
        ),
        ink=True,
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        on_click=lambda _: _open_dashboard(),
    )
    run_box  = ft.Container(
        content=ft.Row([run_icon, run_msg, dash_link], spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        visible=False,
    )

    # ── Action buttons ───────────────────────────────────────────────────────
    btn_save = ft.Container(
        content=ft.Row(
            [ft.Icon(ft.Icons.SAVE_OUTLINED, color=ACCENT, size=16),
             ft.Text("Guardar YAML", color=ACCENT, size=13, weight=ft.FontWeight.W_500)],
            spacing=6, tight=True,
        ),
        bgcolor="#ffffff", border_radius=8,
        border=ft.Border.all(1, ACCENT),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        ink=True,
    )

    run_btn_icon    = ft.Icon(ft.Icons.PLAY_ARROW, color="#ffffff", size=16)
    run_btn_spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color="#ffffff", visible=False)
    run_btn_label   = ft.Text("Ejecutar pipeline", color="#ffffff", size=13, weight=ft.FontWeight.W_600)
    btn_run = ft.Container(
        content=ft.Row(
            [run_btn_icon, run_btn_spinner, run_btn_label],
            spacing=6, alignment=ft.MainAxisAlignment.CENTER, tight=True,
        ),
        bgcolor=RUN_BTN, border_radius=8,
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        ink=True, expand=True,
    )

    action_bar = ft.Container(
        visible=False,
        content=ft.Row([btn_save, btn_run], spacing=10),
    )

    # ── Pipeline section (View 2 — main) ─────────────────────────────────────
    pipeline_section = ft.Container(
        width=CONTENT_W,
        visible=False,
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    [
                        ft.Icon(ft.Icons.FOLDER_COPY_OUTLINED, color=ACCENT, size=16),
                        ft.Text("Pipeline de carga", size=14,
                                weight=ft.FontWeight.W_600, color=TEXT, expand=True),
                        ft.Container(
                            content=ft.Row(
                                [ft.Icon(ft.Icons.DELETE_OUTLINE, color=MUTED, size=14),
                                 ft.Text("Limpiar", color=MUTED, size=12,
                                         weight=ft.FontWeight.W_500)],
                                spacing=4, tight=True,
                            ),
                            bgcolor="#f8fafc", border_radius=6,
                            border=ft.Border.all(1, BORDER_ROW),
                            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                            ink=True, on_click=lambda _: do_clear(),
                        ),
                        ft.Container(
                            content=ft.Row(
                                [ft.Icon(ft.Icons.ADD, color=ACCENT, size=14),
                                 ft.Text("Agregar CSV", color=ACCENT, size=12,
                                         weight=ft.FontWeight.W_500)],
                                spacing=4, tight=True,
                            ),
                            bgcolor="#eff6ff", border_radius=6,
                            border=ft.Border.all(1, BORDER),
                            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                            ink=True, on_click=open_picker,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=1, color=BORDER_ROW),
                task_header,
                task_list,
                action_bar,
                run_box,
            ],
        ),
    )

    # ── Sync header / action_bar visibility ──────────────────────────────────
    def _open_dashboard():
        if not _dashboard_path:
            return
        url = f"file://{_dashboard_path[0].resolve()}"
        if sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "", url])
            return
        for browser in ("firefox", "brave", "google-chrome", "chromium", "msedge"):
            if subprocess.run(["which", browser], capture_output=True).returncode == 0:
                subprocess.Popen([browser, url])
                return
        webbrowser.open(url)

    def update_pipeline_ui():
        has_tasks = bool(task_list.controls)
        task_header.visible = has_tasks
        action_bar.visible  = has_tasks
        if not has_tasks:
            run_box.visible = False
        page.update()

    def do_clear():
        cfg = _build_pipeline_cfg([])   # preserves _defaults, task: []
        with open("config/pipeline.yaml", "w", encoding="utf-8") as fh:
            yaml.dump(cfg, fh, allow_unicode=True,
                      default_flow_style=False, sort_keys=False)
        tasks_data.clear()
        task_list.controls.clear()
        _dashboard_path.clear()
        update_pipeline_ui()

    # ── Task dict for yaml ───────────────────────────────────────────────────
    def build_task(t: dict) -> dict:
        return {
            "name":                    f"Carga {t['f_table'].value.strip() or 'sin nombre'}",
            "file":                    t["file"],
            "delimiter":               t["delim_dd"].value,
            "encoding":                "utf8",
            "table_destination":       t["f_table"].value.strip(),
            "crear_tabla_si_no_existe": t["cb_create"].value,
            "truncate_before_load":    t["cb_truncate"].value,
            "schema":                  t["f_schema"].value.strip(),
            "active":                  t["cb_active"].value,
        }

    def _build_pipeline_cfg(tasks: list[dict]) -> dict:
        """Builds full pipeline config including _defaults from current tasks."""
        if tasks:
            first = tasks[0]
            defaults = {
                "schema":                  first["schema"],
                "delimiter":               first["delimiter"],
                "crear_tabla_si_no_existe": first["crear_tabla_si_no_existe"],
                "truncate_before_load":    first["truncate_before_load"],
                "active":                  first["active"],
            }
        else:
            try:
                if os.path.exists("config/pipeline.yaml"):
                    with open("config/pipeline.yaml", "r", encoding="utf-8") as fh:
                        defaults = (yaml.safe_load(fh) or {}).get("_defaults", {})
                else:
                    defaults = {}
            except Exception:
                defaults = {}
        return {"_defaults": defaults, "task": tasks}

    # ── Load existing pipeline.yaml ──────────────────────────────────────────
    def _load_existing_pipeline():
        if not os.path.exists("config/pipeline.yaml") or task_list.controls:
            return
        try:
            with open("config/pipeline.yaml", "r", encoding="utf-8") as fh:
                existing = yaml.safe_load(fh)
            for t in existing.get("task", []):
                row = make_task_row(
                    file_path=t.get("file", ""),
                    table=t.get("table_destination", ""),
                    schema=t.get("schema", ""),
                    delimiter=t.get("delimiter", ";"),
                    active=t.get("active", True),
                    create_table=t.get("crear_tabla_si_no_existe", True),
                    truncate=t.get("truncate_before_load", False),
                )
                task_list.controls.append(row)
            if task_list.controls:
                update_pipeline_ui()
        except Exception:
            pass

    # ── Disconnect ───────────────────────────────────────────────────────────
    def do_disconnect():
        _adapter.clear()
        _db_cfg.clear()
        tasks_data.clear()
        task_list.controls.clear()
        task_header.visible   = False
        action_bar.visible    = False
        run_box.visible       = False
        connected_bar.visible = False
        pipeline_section.visible = False
        conn_card.visible     = True
        status_box.visible    = False
        page.update()

    # ── Status helpers ───────────────────────────────────────────────────────
    def _show_status(ok: bool, msg: str):
        color = SUCCESS if ok else ERROR
        status_icon.name  = ft.Icons.CHECK_CIRCLE if ok else ft.Icons.ERROR
        status_icon.color = color
        status_msg.value  = msg
        status_msg.color  = color
        status_box.bgcolor = SUCCESS_BG if ok else ERROR_BG
        status_box.border  = ft.Border.all(1, color)
        status_box.visible = True
        page.update()

    def set_run_loading(loading: bool):
        run_btn_icon.visible    = not loading
        run_btn_spinner.visible = loading
        run_btn_label.value     = "Ejecutando..." if loading else "Ejecutar pipeline"
        btn_run.bgcolor         = RUN_BTN_DIM if loading else RUN_BTN
        btn_run.on_click        = None if loading else do_run
        btn_save.on_click       = None if loading else do_save
        page.update()

    def _show_run_status(ok: bool, msg: str, show_dash: bool = False):
        color = SUCCESS if ok else ERROR
        run_icon.name   = ft.Icons.CHECK_CIRCLE if ok else ft.Icons.ERROR
        run_icon.color  = color
        run_msg.value   = msg
        run_msg.color   = color
        run_box.bgcolor = SUCCESS_BG if ok else ERROR_BG
        run_box.border  = ft.Border.all(1, color)
        run_box.visible = True
        dash_link.visible = show_dash
        page.update()

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
            key = _selected_engine[0]
            cfg = {
                "db_engine": ENGINES[key]["db_engine"],
                "host":      f_host.value.strip(),
                "port":      f_port.value.strip(),
                "database":  f_db.value.strip(),
                "username":  f_user.value.strip(),
                "password":  f_pass.value,
            }
            if key == "sqlserver":
                cfg["server"]             = f"{cfg['host']},{cfg['port']}"
                cfg["driver"]             = "ODBC Driver 18 for SQL Server"
                cfg["trusted_connection"] = "no"
                cfg["encrypt"]            = "no"

            loop    = asyncio.get_running_loop()
            adapter = factory_db(cfg)
            label   = ENGINES[key]["label"]
            addr    = f"{f_host.value.strip()}:{f_port.value.strip()}"
            try:
                ok, db_err = await asyncio.wait_for(
                    loop.run_in_executor(None, check_db_connection, adapter.engine),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                _show_status(False, "Tiempo de espera agotado — verifica host y puerto")
                return

            if ok:
                _adapter.clear(); _adapter.append(adapter)
                _db_cfg.clear();  _db_cfg.append({
                    "db_engine": ENGINES[key]["db_engine"],
                    "default_schema": None,
                })
                conn_info.value = (
                    f"{label}  ·  {f_db.value.strip()} @ {addr}  ·  {f_user.value.strip()}"
                )
                conn_card.visible     = False
                status_box.visible    = False
                connected_bar.visible = True
                pipeline_section.visible = True
                _load_existing_pipeline()
                page.update()
            else:
                _show_status(False, db_err or "No se pudo conectar")
        except Exception as ex:
            _show_status(False, str(ex))
        finally:
            set_loading(False)

    # ── Save handler ─────────────────────────────────────────────────────────
    def do_save(_):
        if not tasks_data:
            return
        pipeline_cfg = _build_pipeline_cfg([build_task(t) for t in tasks_data])
        with open("config/pipeline.yaml", "w", encoding="utf-8") as fh:
            yaml.dump(pipeline_cfg, fh, allow_unicode=True,
                      default_flow_style=False, sort_keys=False)
        _show_run_status(True, "Guardado en config/pipeline.yaml")

    # ── Execute handler ──────────────────────────────────────────────────────
    async def do_run(_):
        if not _adapter:
            _show_run_status(False, "No hay conexión activa. Vuelve a conectar.")
            return
        if not tasks_data:
            _show_run_status(False, "Agrega al menos un archivo al pipeline.")
            return
        missing = [t for t in tasks_data if not t["f_table"].value.strip()]
        if missing:
            _show_run_status(False, "Completa 'Tabla destino' en todas las tareas.")
            return

        pipeline_cfg = _build_pipeline_cfg([build_task(t) for t in tasks_data])
        with open("config/pipeline.yaml", "w", encoding="utf-8") as fh:
            yaml.dump(pipeline_cfg, fh, allow_unicode=True,
                      default_flow_style=False, sort_keys=False)

        execution_id = str(uuid.uuid4())
        start_time   = time.time()
        loop = asyncio.get_running_loop()
        set_run_loading(True)
        run_box.visible = False
        page.update()

        registrar_log("process_start", {"execution_id": execution_id})

        try:
            summary = await asyncio.wait_for(
                loop.run_in_executor(
                    None, _run_tasks,
                    pipeline_cfg, _adapter[0], execution_id, _db_cfg[0],
                ),
                timeout=300.0,
            )
            ok_count = summary["successful_tasks"]
            total    = summary["total_tasks"]
            rows     = summary["total_rows"]
            failed   = summary["failed_tasks"]

            # Análisis CSV (pipeline_init, file_analysis_metadata, pipeline_summary)
            try:
                await loop.run_in_executor(
                    None,
                    lambda: CSVAnalysis(
                        execution_id=execution_id, start_time=start_time
                    ).run_csv_analysis(),
                )
            except Exception:
                pass

            # process_complete
            final_status = "COMPLETED" if failed == 0 else "PARTIAL"
            registrar_log("process_complete", {
                "execution_id": execution_id,
                "status":            final_status,
                "total_tasks":       total,
                "successful_tasks":  ok_count,
                "failed_tasks":      failed,
                "total_rows":        rows,
                "duration_seconds":  round(time.time() - start_time, 2),
            })

            try:
                log_path = get_log_path()
                dash_path = await loop.run_in_executor(
                    None, generate_dashboard,
                    log_path, log_path.with_suffix(".html"), execution_id,
                )
                _dashboard_path.clear()
                _dashboard_path.append(dash_path)
                show_dash = True
            except Exception:
                show_dash = False

            if failed == 0:
                _show_run_status(
                    True,
                    f"Completado — {ok_count}/{total} tareas · {rows:,} filas insertadas",
                    show_dash=show_dash,
                )
            else:
                _show_run_status(
                    False,
                    f"Parcial — {ok_count} OK / {failed} fallidas · {rows:,} filas",
                    show_dash=show_dash,
                )
        except asyncio.TimeoutError:
            _show_run_status(False, "Tiempo de espera agotado (>5 min)")
        except Exception as ex:
            _show_run_status(False, str(ex))
        finally:
            set_run_loading(False)

    # ── Wire handlers ────────────────────────────────────────────────────────
    btn.on_click      = do_connect
    btn_save.on_click = do_save
    btn_run.on_click  = do_run

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
                    ft.Text("FlowELT", size=28, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(
                        "Carga masiva nativa hacia tu base de datos",
                        size=13, color=MUTED,
                    ),
                    ft.Container(height=16),
                    conn_card,
                    ft.Container(height=8),
                    connected_bar,
                    ft.Container(height=12),
                    pipeline_section,
                    ft.Container(height=16),
                ],
            ),
        )
    )


ft.run(main)