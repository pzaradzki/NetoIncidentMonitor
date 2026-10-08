"""Keep packaged user data outside the temporary executable bundle."""
import os
import sys
from pathlib import Path


def packaged_data(local_appdata):
    return Path(local_appdata) / "NetoIncidentMonitor"


ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
FROZEN = getattr(sys, "frozen", False)
DATA = packaged_data(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) if FROZEN else ROOT / "data"

if FROZEN:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / "browsers")
