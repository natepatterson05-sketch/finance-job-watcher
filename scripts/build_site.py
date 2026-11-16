"""Stage only the public browser application and its two data files."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FILES = ['index.html', 'browse.html', 'market.html', 'sw.js',
         'manifest.webmanifest', '.nojekyll', 'assets/app.mjs',
         'assets/metrics.mjs', 'assets/style.css', 'assets/icon.svg',
         'assets/icon-192.png', 'assets/icon-512.png',
         'data/history.csv', 'data/status.json']


def build_site(destination):
    for filename in FILES:
        source = ROOT / filename
        if not source.is_file():
            raise FileNotFoundError(source)
    for filename in FILES:
        target = Path(destination) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, target)
    return len(FILES)


if __name__ == '__main__':
    print(f'Staged {build_site(ROOT / "_site")} public files in _site/')
