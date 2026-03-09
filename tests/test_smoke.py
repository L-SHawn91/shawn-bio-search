from pathlib import Path
import subprocess
import json


def test_cli_help():
    r = subprocess.run(["shawn-bio-search", "-h"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "usage" in r.stdout.lower() or "usage" in r.stderr.lower()


def test_search_bundle_smoke(tmp_path: Path):
    out = tmp_path / "bundle.json"
    cmd = [
        "python3",
        "scripts/search_bundle.py",
        "--query",
        "adenomyosis",
        "--claim",
        "adenomyosis affects fertility outcomes",
        "--hypothesis",
        "adenomyosis may reduce IVF success",
        "--fast",
        "--out",
        str(out),
    ]
    r = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert "papers" in data
