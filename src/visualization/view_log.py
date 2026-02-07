"""Generador de vista HTML para logs JSON"""
import json
from pathlib import Path

def generar_html_log(log_file: Path, output_file: Path = None, css_file: Path = None):
    """
    Genera un HTML interactivo con estructura anidada expandible.
    
    Args:
        log_file: Ruta al archivo JSON log
        output_file: Ruta de salida HTML (opcional)
        css_file: Ruta al archivo CSS personalizado (opcional)
    """
    # Leer datos
    with open(log_file, 'r', encoding='utf-8') as f:
        data = [json.loads(line) for line in f]
    
    # Nombre de salida
    if output_file is None:
        output_file = log_file.with_suffix('.html')
    
    # CSS por defecto o personalizado
    if css_file is None:
        css_file = Path(__file__).parent / "log_viewer.css"
    
    # Leer CSS
    if css_file.exists():
        with open(css_file, 'r', encoding='utf-8') as f:
            css_content = f.read()
    else:
        css_content = "/* CSS no encontrado */"
        print(f"⚠️  Advertencia: No se encontró {css_file}")
    
    # Generar HTML
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Log Viewer - {log_file.name}</title>
    <style>
{css_content}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <button class="theme-toggle" onclick="toggleTheme()">
                <span id="theme-icon">🌙</span>
                <span id="theme-text">Modo Oscuro</span>
            </button>
            <h1>📊 Visor de Logs</h1>
            <p>{log_file.name}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Total de Eventos</div>
                <div class="stat-value">{len(data)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Primer Evento</div>
                <div class="stat-value">{data[0]['timestamp'].split('T')[1][:8] if data else 'N/A'}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Último Evento</div>
                <div class="stat-value">{data[-1]['timestamp'].split('T')[1][:8] if data else 'N/A'}</div>
            </div>
        </div>
        
        <div class="timeline">
            <button class="expand-all" onclick="toggleAll()">Expandir/Colapsar Todo</button>
"""
    
    # Generar entradas
    for idx, entry in enumerate(data):
        timestamp = entry['timestamp']
        evento = entry['evento']
        detalles = entry['detalles']
        
        html += f"""
            <div class="log-entry" id="entry-{idx}">
                <div class="log-header" onclick="toggleEntry({idx})">
                    <div>
                        <span class="timestamp">{timestamp}</span>
                        <span class="evento">{evento}</span>
                    </div>
                    <span class="toggle-icon">▶</span>
                </div>
                <div class="detalles">
                    <div class="detalles-content">
"""
        
        # Generar detalles
        detalle_items = []
        columnas_item = None

        # Separar columnas del resto
        for key, value in detalles.items():
            if key == 'columnas' and isinstance(value, list):
                columnas_item = (key, value)
            else:
                detalle_items.append((key, value))

        # Primero renderizar todo excepto columnas
        for key, value in detalle_items:
            html += f'                        <div class="detalle-item">\n'
            html += f'                            <div class="detalle-key">{key}</div>\n'
            
            if isinstance(value, list):
                html += f'                            <div class="detalle-list">\n'
                for item in value:
                    html += f'                                <div class="detalle-list-item">{item}</div>\n'
                html += f'                            </div>\n'
            elif isinstance(value, (int, float)):
                html += f'                            <div class="detalle-value">{value:,}</div>\n'
            else:
                html += f'                            <div class="detalle-value">{value}</div>\n'
            
            html += f'                        </div>\n'

        # Al final, renderizar columnas de forma especial
        if columnas_item:
            key, columnas = columnas_item
            html += f'''                        <div class="detalle-item columnas-section">
                            <div class="detalle-key">
                                {key} ({len(columnas)} campos)
                                <button class="toggle-columns" onclick="toggleColumns(event, {idx})">
                                    <span class="toggle-columns-icon">▼</span> Mostrar columnas
                                </button>
                            </div>
                            <div class="columnas-container" id="columnas-{idx}">
                                <div class="columnas-grid">
'''
            for i, col in enumerate(columnas, 1):
                html += f'                                    <div class="columna-item"><span class="col-num">{i}.</span> {col}</div>\n'
            
            html += '''                                </div>
                            </div>
                        </div>
'''
        
        html += """                    </div>
                </div>
            </div>
"""
    
    # Cerrar HTML y agregar JavaScript
    html += """        </div>
    </div>
    
    <script>
        // Cargar tema guardado
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeButton(savedTheme);
        
        function toggleTheme() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeButton(newTheme);
        }
        
        function updateThemeButton(theme) {
            const icon = document.getElementById('theme-icon');
            const text = document.getElementById('theme-text');
            
            if (theme === 'dark') {
                icon.textContent = '☀️';
                text.textContent = 'Modo Claro';
            } else {
                icon.textContent = '🌙';
                text.textContent = 'Modo Oscuro';
            }
        }
        
        function toggleEntry(id) {
            const entry = document.getElementById('entry-' + id);
            entry.classList.toggle('expanded');
        }
        
        function toggleColumns(event, entryId) {
            event.stopPropagation(); // Evitar que se cierre el entry padre
            
            const container = document.getElementById('columnas-' + entryId);
            const button = event.currentTarget;
            
            container.classList.toggle('show');
            button.classList.toggle('active');
            
            if (container.classList.contains('show')) {
                button.innerHTML = '<span class="toggle-columns-icon">▼</span> Ocultar columnas';
            } else {
                button.innerHTML = '<span class="toggle-columns-icon">▼</span> Mostrar columnas';
            }
        }
        
        let allExpanded = false;
        function toggleAll() {
            const entries = document.querySelectorAll('.log-entry');
            allExpanded = !allExpanded;
            
            entries.forEach(entry => {
                if (allExpanded) {
                    entry.classList.add('expanded');
                } else {
                    entry.classList.remove('expanded');
                }
            });
        }
    </script>
</body>
</html>
"""
    
    # Guardar archivo
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ HTML generado: {output_file.absolute()}")
    print(f"🎨 Usando CSS: {css_file.absolute()}")
    return output_file


if __name__ == "__main__":
    import sys
    
    # Buscar el log más reciente si no se especifica
    if len(sys.argv) > 1:
        log_file = Path(sys.argv[1])
    else:
        logs = sorted(Path('.').glob('log_*.json'))
        if not logs:
            print("❌ No se encontraron archivos de log")
            sys.exit(1)
        log_file = logs[-1]
    
    # Permitir especificar CSS personalizado
    css_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    html_file = generar_html_log(log_file, css_file=css_file)
    
    # Abrir en navegador
    import webbrowser
    webbrowser.open(str(html_file.absolute()))