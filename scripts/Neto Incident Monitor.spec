import json
import os
import sys
from pathlib import Path
import playwright
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
sys.path.insert(0, str(root))
from neto_incident_monitor.analytics_config import lost_incidents_query
from tools.import_dashboard_api import compile_config, read_rows

defaults = compile_config(read_rows(root / 'data' / 'dashboard-api-kafelki.xlsx'))
lost_incidents_query(defaults)  # Require the complete set of current dashboard definitions.
parameter_keys = ('version', 'monthly_group', 'held_metric', 'l1_group_name', 'smartphone_variable',
                  'smartphone_description', 'threatened_group', 'lost_excluded_group')
seed = Path(workpath) / 'dashboard-api.json'
seed.write_text(json.dumps({key: defaults[key] for key in parameter_keys}, ensure_ascii=False), encoding='utf-8')
package = Path(playwright.__file__).parent / "driver" / "package"
metadata = json.loads((package / "browsers.json").read_text(encoding="utf-8"))
cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or
             str(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright"))
browser_data = [(str(path), path.parent.relative_to(root).as_posix())
                for path in sorted((root / "assets").rglob("*"))
                if path.is_file() and path.name != "Cached Theme.pak"]
browser_data.extend((str(root / "icons" / f"icons8-{channel}-48.png"), "icons")
                    for channel in ("windows", "google-chat", "teams"))
browser_data.append((str(seed), 'defaults'))
for name in ("chromium", "ffmpeg"):
    info = next(entry for entry in metadata["browsers"] if entry["name"] == name)
    folder = name + "-" + info["revision"]
    source = cache / folder
    if not source.is_dir():
        raise RuntimeError(f"Brak {source}. Uruchom: python -m playwright install chromium")
    browser_data.append((str(source), "browsers/" + folder))

a = Analysis([str(root / "launcher.pyw")], pathex=[str(root)],
             binaries=[], datas=browser_data,
             hiddenimports=collect_submodules("plyer.platforms.win") + ["pystray._win32"],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name="Neto Incident Monitor", debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, icon=str(root / "assets" / "netology-icon.ico"), disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name="Neto Incident Monitor")

