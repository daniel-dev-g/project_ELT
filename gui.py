"""gui.py — FlowELT Desktop App"""
import asyncio
import flet as ft

from src.state_manager.core.adapter_db.factory_db import factory_db
from src.validators import check_db_connection


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
ERROR = "#dc2626"
ERROR_BG = "#fee2e2"
BG = "#f1f5f9"
SURFACE = "#ffffff"
TEXT = "#1e293b"
MUTED = "#64748b"
BORDER = "#e2e8f0"


def _field(**kwargs) -> ft.TextField:
    return ft.TextField(
        border_color=BORDER,
        focused_border_color=ACCENT,
        cursor_color=ACCENT,
        border_radius=8,
        text_size=14,
        label_style=ft.TextStyle(color=MUTED),
        **kwargs,
    )


async def main(page: ft.Page):
    page.title = "FlowELT"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = BG
    page.padding = 0
    page.window.width = 520
    page.window.height = 780
    page.window.resizable = False

    # ── Fields ────────────────────────────────────────────────────────────────
    f_host = _field(label="Host", value="localhost", expand=True)
    f_port = _field(label="Puerto", value="5432", width=120)
    f_db = _field(label="Base de datos")
    f_user = _field(label="Usuario")
    f_pass = _field(
        label="Contraseña",
        password=True,
        can_reveal_password=True,
    )

    # ── Status banner ─────────────────────────────────────────────────────────
    status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=18)
    status_msg = ft.Text("", size=13)
    status_box = ft.Container(
        content=ft.Row([status_icon, status_msg], spacing=8),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        visible=False,
    )

    def set_status(ok: bool, msg: str):
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

    # ── Engine dropdown ───────────────────────────────────────────────────────
    engine_dd = ft.Dropdown(
        label="Motor de base de datos",
        value="postgres",
        border_color=BORDER,
        focused_border_color=ACCENT,
        border_radius=8,
        text_size=14,
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

    # ── Button (Container) ────────────────────────────────────────────────────
    btn_icon = ft.Icon(ft.Icons.CABLE, color="#ffffff", size=18)
    btn_spinner = ft.ProgressRing(
        width=16, height=16, stroke_width=2, color="#ffffff", visible=False
    )
    btn_label = ft.Text(
        "Conectar", color="#ffffff", size=14, weight=ft.FontWeight.W_600
    )
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

    def validate_fields() -> str | None:
        if not f_host.value.strip():
            return "El campo Host es obligatorio."
        if not f_port.value.strip():
            return "El campo Puerto es obligatorio."
        if not f_db.value.strip():
            return "Ingresa el nombre de la base de datos."
        if not f_user.value.strip():
            return "Ingresa el usuario."
        return None

    async def do_connect(_):
        err = validate_fields()
        if err:
            set_status(False, err)
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
            addr = (
                f"{f_host.value.strip()}:{f_port.value.strip()}"
            )
            try:
                ok, db_err = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, check_db_connection, adapter.engine
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                set_status(
                    False,
                    "Tiempo de espera agotado — verifica host y puerto",
                )
                return
            if ok:
                set_status(True, f"Conexión exitosa — {label} en {addr}")
            else:
                set_status(False, db_err or "No se pudo conectar")
        except Exception as ex:
            set_status(False, str(ex))
        finally:
            set_loading(False)

    btn.on_click = do_connect

    # ── Layout ────────────────────────────────────────────────────────────────
    page.add(
        ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.Padding.symmetric(horizontal=30, vertical=32),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    ft.Text(
                        "FlowELT",
                        size=34,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT,
                    ),
                    ft.Text(
                        "Carga masiva nativa hacia tu base de datos",
                        size=13,
                        color=MUTED,
                    ),
                    ft.Container(height=24),
                    ft.Container(
                        width=460,
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
                                    "Configurar conexión",
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
                                ft.Row(
                                    [btn],
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                            ],
                        ),
                    ),
                    ft.Container(height=12),
                    ft.Container(
                        width=460,
                        content=status_box,
                    ),
                ],
            ),
        )
    )

ft.run(main)