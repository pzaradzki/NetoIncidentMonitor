"""Keep packaged user data outside the temporary executable bundle."""
from hashlib import sha256
import os
import sys
from pathlib import Path


def packaged_data(local_appdata):
    return Path(local_appdata) / "NetoIncidentMonitor"


def source_log_dir(local_appdata, checkout):
    # Separate worktrees also have separate runtime data and instance locks.
    canonical = os.path.normcase(str(Path(checkout).resolve()))
    checkout_id = sha256(os.fsencode(canonical)).hexdigest()[:24]
    return Path(local_appdata) / "NetoIncidentMonitor-SourceLogs" / checkout_id


ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
FROZEN = getattr(sys, "frozen", False)
LOCAL_DATA = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
DATA = packaged_data(LOCAL_DATA) if FROZEN else ROOT / "data"
LOG_DIR = DATA if FROZEN else source_log_dir(LOCAL_DATA, ROOT)

if FROZEN:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / "browsers")
