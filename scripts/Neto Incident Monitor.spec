import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
sys.path.insert(0, str(root))
from tools.package_inputs import (browser_files, dashboard_payload, read_manifest, validate_playwright,
                                  verified_browser_folders)

manifest = read_manifest()
if not os.environ.get('NETO_BUILD_DASHBOARD_PARAMETERS') or not os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):
    raise RuntimeError('Use scripts/build_exe.ps1 with explicit package inputs.')
payload = dashboard_payload(Path(os.environ['NETO_BUILD_DASHBOARD_PARAMETERS']), manifest['dashboard']['sha256'])
seed = Path(workpath) / 'dashboard-api.json'
seed.write_bytes(payload)
validate_playwright(manifest['browsers'])
cache = Path(os.environ['PLAYWRIGHT_BROWSERS_PATH'])
assets = (Path("assets/netology-icon.ico"), Path("assets/netology-icon.png"),
          Path("assets/netology-logo.png"), Path("assets/neto-browser-theme/manifest.json"),
          *(Path("icons") / f"icons8-{channel}-48.png" for channel in ("windows", "google-chat", "teams")))
browser_data = [(str(root / path), path.parent.as_posix()) for path in assets]
browser_data.append((str(seed), 'defaults'))
for folder in verified_browser_folders(cache, manifest['browsers']):
    for path in browser_files(folder):
        destination = Path('browsers') / folder.name / path.parent.relative_to(folder)
        browser_data.append((str(path), destination.as_posix()))

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

