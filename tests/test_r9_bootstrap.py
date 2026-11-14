"""Static guardrails for the Windows R9 local-runtime startup flow.

These do NOT replace a real Windows PowerShell or Godot run.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_source_zip_missing_venv_has_explicit_repair_button():
    ui = _read("game/ui/play_windows.gd")
    engine = _read("game/maps/network_main.gd")
    assert '安装/修复运行环境' in ui
    assert 'world.install_local_runtime()' in ui
    assert 'func install_local_runtime() -> void:' in engine
    assert 'OS.get_name() != "Windows"' in engine
    assert 'OS.create_process("powershell.exe"' in engine


def test_setup_ready_marker_is_written_only_after_requirements_install():
    setup = _read("release/setup_game.ps1")
    assert 'param([string]$StatusPath' in setup
    assert "Write-GameSetupStatus 'failed'" in setup
    assert 'Set-Content' not in setup or 'pip check' in setup
    assert setup.index('pip install -r requirements.txt') < setup.index("Write-GameSetupStatus 'ready' 'The local Python environment is ready.'")
    assert setup.index('& $python -m pip check') < setup.index("Write-GameSetupStatus 'ready' 'The local Python environment is ready.'")
    engine = _read("game/maps/network_main.gd")
    assert 'runtime/godot-setup-result.json' in engine
    assert 'parsed.get("status", "") == "ready"' in engine
    assert 'local_setup_pending' in engine


def test_batch_start_can_initialize_missing_source_runtime():
    startup = _read("release/start_game.ps1")
    assert "& (Join-Path $PSScriptRoot 'setup_game.ps1')" in startup
    assert 'if (-not (Test-Path -LiteralPath $python))' in startup
    assert 'Automatic setup failed' in startup
