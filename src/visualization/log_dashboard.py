"""DataBridge — HTML Dashboard Generator for JSON logs"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Template location next to this file
_TEMPLATE = Path(__file__).parent / "log_viewer.html"


def generate_dashboard(log_file: Path, output_file: Path = None) -> Path:
    """
    Generates an interactive HTML dashboard from a JSON log file.

    Args:
        log_file:    Path to the JSON log file (one JSON object per line)
        output_file: Output HTML path (default: same name as log, .html extension)

    Returns:
        Path to the generated HTML file
    """
    log_file = Path(log_file)

    if not log_file.exists():
        raise FileNotFoundError(f"Log file not found: {log_file}")

    # Read log entries (one JSON per line)
    entries = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning("Skipping invalid JSON line: %s", e)

    if not entries:
        logger.warning("Log file is empty: %s", log_file)

    # Output path
    if output_file is None:
        output_file = log_file.with_suffix(".html")
    output_file = Path(output_file)

    # Read template
    if not _TEMPLATE.exists():
        raise FileNotFoundError(f"HTML template not found: {_TEMPLATE}")

    with open(_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()

    # Inject data — replace placeholder with actual JSON array
    json_data = json.dumps(entries, ensure_ascii=False, indent=2)
    html = template.replace("__LOG_DATA__", json_data)

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard generated: %s (%d events)", output_file, len(entries))
    return output_file


def generate_latest_dashboard(logs_dir: str = "logs", output_dir: str = "logs") -> Path:
    """
    Finds the most recent JSON log and generates its dashboard.

    Args:
        logs_dir:   Directory to search for log_*.json files
        output_dir: Directory to save the HTML output

    Returns:
        Path to the generated HTML file
    """
    logs_path = Path(logs_dir)
    log_files = sorted(logs_path.glob("log_*.json"))

    if not log_files:
        raise FileNotFoundError(f"No log_*.json files found in: {logs_dir}")

    latest = log_files[-1]
    output_file = Path(output_dir) / latest.with_suffix(".html").name

    return generate_dashboard(latest, output_file)


if __name__ == "__main__":
    import sys
    import webbrowser

    if len(sys.argv) > 1:
        log_path = Path(sys.argv[1])
        html_path = generate_dashboard(log_path)
    else:
        html_path = generate_latest_dashboard()
        webbrowser.open(str(html_path.absolute()))
