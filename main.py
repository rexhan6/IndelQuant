"""IndelQuant application entry point."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import MainWindow


def main():
    """Start the application."""
    app = MainWindow()
    app.run()


if __name__ == '__main__':
    main()
