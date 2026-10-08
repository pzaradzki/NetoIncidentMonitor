import json
import os
from pathlib import Path
import playwright
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
package = Path(playwright.__file__).parent / "driver" / "package"
metadata = json.loads((package / "browsers.json").read_text(encoding="utf-8"))
cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or
             str(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright"))
browser_data = [(str(root / "INSTRUKCJA_TEAMS.md"), "."), (str(root / "assets"), "assets")]
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
