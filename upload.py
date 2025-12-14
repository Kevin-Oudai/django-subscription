"""
Build and upload mroudai-django-subscriptions to PyPI.

Usage:
    python upload.py

Prerequisites:
    python install_upload_dependencies.py
    Set TWINE_USERNAME and TWINE_PASSWORD (or TWINE_TOKEN) in env.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()


def run(cmd):
    subprocess.check_call(cmd, shell=False)


def ensure_tools():
    try:
        import build  # noqa: F401
        import twine  # noqa: F401
    except ImportError:
        run([sys.executable, "-m", "pip", "install", "--upgrade", "build", "twine"])


def clean_build_artifacts():
    for path in ["build", "dist"]:
        shutil.rmtree(ROOT / path, ignore_errors=True)
    for egg_info in ROOT.glob("*.egg-info"):
        shutil.rmtree(egg_info, ignore_errors=True)


def main():
    ensure_tools()
    clean_build_artifacts()
    run([sys.executable, "-m", "build"])
    run([sys.executable, "-m", "twine", "upload", "dist/*"])


if __name__ == "__main__":
    main()
