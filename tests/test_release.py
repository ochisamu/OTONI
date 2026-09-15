import importlib.util
from pathlib import Path
import json
import pytest

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_export_only_allowlist_and_fail_closed(tmp_path,monkeypatch):
    m=module('export_source');root=tmp_path/'source';root.mkdir();monkeypatch.setattr(m,'ROOT',root)
    (root/'app.py').write_text('print("hello")')
    (root/'.env').write_text('private local settings')
    (root/'release-files.txt').write_text('app.py\n')
    output=tmp_path/'out';m.export(output)
    assert not (output/'.env').exists()
    assert list(json.loads((output/'release-manifest.json').read_text()))==['app.py']
    with pytest.raises(ValueError,match='already exists'):m.export(output)
    (root/'app.py').write_text('hf_'+'x'*30)
    with pytest.raises(ValueError,match='sensitive'):m.export(tmp_path/'bad')
    assert not (tmp_path/'bad').exists()
    (root/'release-files.txt').write_text('../outside.txt\n')
    with pytest.raises(ValueError,match='path'):m.export(tmp_path/'traversal')


def test_service_uses_current_checkout():
    text=module('install_service').service_text(Path('/tmp/My Studio%20'))
    assert 'WorkingDirectory=/tmp/My Studio%%20' in text
    assert 'ExecStart="/tmp/My Studio%%20/scripts/start.sh"' in text


def test_release_manifest_includes_runtime_and_excludes_data():
    names=(ROOT/'release-files.txt').read_text().splitlines()
    assert 'web/index.html' in names and 'vendor/SHA256SUMS' in names
    assert 'scripts/install_service.py' in names
    assert not any(n.startswith(('data/','models/','work/','web/quality/','.venv')) for n in names)
    assert '.env' not in names
