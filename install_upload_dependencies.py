"""
Install tools required to build and upload the package to PyPI.

Usage:
    python install_upload_dependencies.py
"""
import subprocess
import sys


def main():
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", "build", "twine"]
    )


if __name__ == "__main__":
    main()
