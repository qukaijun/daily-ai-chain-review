# -*- coding: utf-8 -*-
"""Export a generated report as a single self-contained HTML file."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output_files"
DEFAULT_SHARE_DIR = OUTPUT_DIR / "share"
SCRIPT_TAG = '<script src="chartjs.min.js"></script>'


def latest_report() -> Path:
    reports = sorted(OUTPUT_DIR.glob("report_full_*.html"), key=lambda path: path.stat().st_mtime)
    if not reports:
        raise FileNotFoundError(f"No report_full_*.html found in {OUTPUT_DIR}")
    return reports[-1]


def export_single_html(input_path: Path, output_path: Path | None = None) -> Path:
    input_path = input_path.resolve()
    chart_path = input_path.parent / "chartjs.min.js"
    if not chart_path.exists():
        chart_path = ROOT / "templates" / "chartjs.min.js"
    if not chart_path.exists():
        raise FileNotFoundError("chartjs.min.js not found beside report or in templates/")

    html = input_path.read_text(encoding="utf-8")
    chart_js = chart_path.read_text(encoding="utf-8")
    inline_script = f"<script>\n{chart_js}\n</script>"
    if SCRIPT_TAG in html:
        html = html.replace(SCRIPT_TAG, inline_script, 1)
    elif "chartjs.min.js" in html:
        raise ValueError("Found chartjs.min.js reference but not the expected script tag")
    else:
        html = html.replace("</body>", inline_script + "\n</body>", 1)

    if output_path is None:
        DEFAULT_SHARE_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DEFAULT_SHARE_DIR / input_path.name.replace("report_full_", "report_single_")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(html, encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export report_full_*.html as a single self-contained HTML file.")
    parser.add_argument("input", nargs="?", help="Input report HTML. Defaults to latest output_files/report_full_*.html")
    parser.add_argument("-o", "--output", help="Output single-file HTML path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input) if args.input else latest_report()
    output_path = Path(args.output) if args.output else None
    result = export_single_html(input_path, output_path)
    print(f"[OK] Single-file HTML saved: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
