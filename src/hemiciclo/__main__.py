"""Entry-point para ``python -m hemiciclo``."""

from __future__ import annotations

from hemiciclo.cli import app


def main() -> None:
    """Executa o app Typer."""
    app()


if __name__ == "__main__":
    main()
