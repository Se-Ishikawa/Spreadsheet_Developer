"""Application metadata for Spreadsheet Developer."""

APP_NAME = "Spreadsheet Developer"
APP_VERSION = "1.0.0"
APP_COPYRIGHT = "© 2026"
APP_TAGLINE = "A lightweight, extensible spreadsheet-like tool with plugin-based architecture."
APP_REPOSITORY_NAME = "spreadsheet-developer"


def about_text() -> str:
    return (
        f"{APP_NAME}\n"
        f"Version {APP_VERSION}\n\n"
        f"{APP_TAGLINE}\n\n"
        f"{APP_COPYRIGHT}"
    )
