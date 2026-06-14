"""Shared utilities — PyInstaller-compatible resource paths."""

import os
import sys


def resource_path(relative):
    """Absolute path to *relative*, works in dev and PyInstaller frozen mode."""
    try:
        # PyInstaller unpacks into a temp folder referenced by sys._MEIPASS
        base = sys._MEIPASS
    except AttributeError:
        # Running in source: one level above app/ is the project root
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)
