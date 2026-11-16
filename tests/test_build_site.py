import importlib.util
from pathlib import Path


def test_pages_artifact_contains_only_application_and_data(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('build_site', root / 'scripts/build_site.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    count = module.build_site(tmp_path)
    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file())
    assert files == sorted(module.FILES)
    assert count == 14
    assert (tmp_path / 'data/history.csv').read_bytes() == (root / 'data/history.csv').read_bytes()
    assert not (tmp_path / 'data/raw').exists()
    assert not (tmp_path / '.git').exists()
