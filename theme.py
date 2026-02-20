# theme.py
import qdarktheme
from enum import Enum
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette
import sys

class Theme(Enum):
    AUTO = "auto"
    LIGHT = "light"
    DARK = "dark"

class ThemeManager:
    def __init__(self, theme: Theme):
        self._theme = theme
        print(f"ThemeManager: Initializing with theme: {theme.value}")
        try:
            qdarktheme.setup_theme(theme.value)
            print(f"ThemeManager: Initial theme '{theme.value}' applied successfully.")
        except Exception as e:
             print(f"ERROR applying initial theme '{theme.value}': {e}", file=sys.stderr)
             import traceback
             traceback.print_exc()


    def set_theme(self, theme: Theme) -> bool:
        print(f"ThemeManager: Attempting to set theme to: {theme.value}")
        self._theme = theme
        try:
            qdarktheme.setup_theme(theme.value)
            print(f"ThemeManager: Theme '{theme.value}' applied successfully.")
            return True
        except Exception as e:
            print(f"ERROR applying theme '{theme.value}': {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def is_white_theme() -> bool:
        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            raise RuntimeError("QApplication is not initialized")

        palette = app.palette()
        color = palette.color(QPalette.ColorRole.Text)
        y = 0.2126 * color.red() + 0.7152 * color.green() + 0.0722 * color.blue()
        return y < 128
