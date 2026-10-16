"""Create the small manifest that must accompany every updatable GitHub release."""
import argparse
import hashlib
import json
from pathlib import Path
from neto_incident_monitor import __version__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('zip', type=Path)
    parser.add_argument('--asset-name', default='Neto.Incident.Monitor.zip')
    parser.add_argument('--output', type=Path, default=Path('dist/update-manifest.json'))
    args = parser.parse_args()
    with args.zip.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    result = {'version': __version__, 'asset_name': args.asset_name,
              'size': args.zip.stat().st_size, 'sha256': digest}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(str(args.output))


if __name__ == '__main__':
    main()
