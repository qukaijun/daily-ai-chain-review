# -*- coding: utf-8 -*-
"""Build a green customer delivery package for Daily AI Chain Review."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
DEFAULT_PACKAGE_NAME = "DailyAIChainReview-V1"
EXCLUDED_DIRS = {
    ".git",
    ".cache",
    ".codex-threads",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "output_files",
    "secrets",
}
EXCLUDED_FILES = {
    ".env",
    ".env.local",
    "secrets.env",
    "llm.env",
}


def _ignore(_: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in EXCLUDED_DIRS or name in EXCLUDED_FILES:
            ignored.add(name)
        elif name.endswith((".pyc", ".pyo")):
            ignored.add(name)
    return ignored


def _write_launcher(path: Path, command: str) -> None:
    body = f"""@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not defined DAA_GLOBAL_ENV_FILE set DAA_GLOBAL_ENV_FILE=%CD%\\secrets\\llm.env
echo.
echo Daily AI Chain Review
echo ------------------------------------------------------------
{command}
echo.
if errorlevel 1 (
  echo [FAIL] Command failed. Please run 06_export_diagnostics.bat and send diagnostics to support.
) else (
  echo [OK] Done.
)
pause
"""
    path.write_text(body, encoding="utf-8")


def _write_env_example(path: Path) -> None:
    body = """# Daily AI Chain Review customer config
# Copy this file to .env.local and fill in your own keys.
# Do not send .env.local to anyone.

# Optional Perplexity sources: search / research / rumors
PERPLEXITY_API_KEY=
PERPLEXITY_BASE_URL=https://api.perplexity.ai
PERPLEXITY_MODEL=sonar

# Optional LLM deep multi-agent review
DAA_LLM_PROVIDER=openai
DAA_LLM_API_KEY=
DAA_LLM_BASE_URL=https://api.openai.com/v1
DAA_DEEP_MODEL=gpt-4o
DAA_ENABLE_DEEP_AGENTS=0

# Optional notification, disabled by default
DAA_NOTIFY_ENABLED=0
DAA_NOTIFY_PROVIDER=console
DAA_NOTIFY_WEBHOOK_URL=
"""
    path.write_text(body, encoding="utf-8")


def _prepare_runtime_dirs(package_dir: Path) -> None:
    for relative in (
        "output_files",
        "output_files/share",
        "output_files/daily_runs",
        "output_files/diagnostics",
        "output_files/screenshots",
        "secrets",
    ):
        (package_dir / relative).mkdir(parents=True, exist_ok=True)


def build_package(package_name: str, make_zip: bool = True) -> tuple[Path, Path | None]:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    package_dir = DIST_DIR / package_name
    if package_dir.exists():
        shutil.rmtree(package_dir)
    shutil.copytree(ROOT, package_dir, ignore=_ignore)
    _prepare_runtime_dirs(package_dir)
    _write_env_example(package_dir / ".env.local.example")
    _write_launcher(
        package_dir / "01_install_dependencies.bat",
        "python -m pip install --upgrade pip\npython -m pip install -r requirements.txt",
    )
    _write_launcher(package_dir / "02_check_environment.bat", "python scripts\\customer_diagnostics.py --quick")
    _write_launcher(package_dir / "03_generate_review.bat", "python scripts\\run_daily_review.py")
    _write_launcher(
        package_dir / "03_generate_review_local_only.bat",
        "python scripts\\run_daily_review.py --no-fetch-market --skip-postflight",
    )
    _write_launcher(package_dir / "04_export_single_html.bat", "python scripts\\export_single_html.py")
    _write_launcher(package_dir / "05_open_reports.bat", "start \"\" \"%CD%\\output_files\"")
    _write_launcher(package_dir / "06_export_diagnostics.bat", "python scripts\\customer_diagnostics.py")
    zip_path = None
    if make_zip:
        zip_base = DIST_DIR / package_name
        zip_file = Path(shutil.make_archive(str(zip_base), "zip", root_dir=DIST_DIR, base_dir=package_name))
        zip_path = zip_file
    return package_dir, zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a customer green package")
    parser.add_argument("--name", default=DEFAULT_PACKAGE_NAME, help="Package directory and zip base name")
    parser.add_argument("--no-zip", action="store_true", help="Only build the folder, skip zip")
    args = parser.parse_args()

    package_dir, zip_path = build_package(args.name, make_zip=not args.no_zip)
    print(f"[OK] Package folder: {package_dir}")
    if zip_path:
        print(f"[OK] Package zip: {zip_path}")
    print(f"[INFO] Built at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
