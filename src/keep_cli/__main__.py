"""Allow ``python -m keep_cli`` and serve as the PyInstaller entry point."""

from keep_cli.cli import main

if __name__ == "__main__":
    main(prog_name="keep")
