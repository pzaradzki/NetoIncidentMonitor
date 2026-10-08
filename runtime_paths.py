"""Keep packaged user data outside the temporary executable bundle."""
import os
import sys
import shutil
import tempfile
from pathlib import Path


def packaged_data(local_appdata):
    base = Path(local_appdata)
    destination = base / "NetoIncidentMonitor"
    if destination.exists():
        return destination
    for old_name in ("ServiceNow Monitor", "ServiceNowMonitor"):
        legacy = base / old_name
        if not legacy.is_dir():
            continue
        # Complete the copy before publishing the new folder. Keep the old
        # data intact, and never overwrite an existing new configuration.
        with tempfile.TemporaryDirectory(prefix="NetoIncidentMonitor-migration-", dir=base) as temporary:
            staged = Path(temporary) / "data"
            shutil.copytree(legacy, staged)
            try:
                staged.rename(destination)
            except FileExistsError:
                if not destination.is_dir():
                    raise
        break
    return destination


ROOT = Path(__file__).resolve().parent
FROZEN = getattr(sys, "frozen", False)
DATA = packaged_data(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) if FROZEN else ROOT / "data"

if FROZEN:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / "browsers")
