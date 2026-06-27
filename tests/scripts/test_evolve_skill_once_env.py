import os
import shutil
import subprocess
from pathlib import Path


def _copy_script_fixture(tmp_path: Path) -> Path:
    repo = Path(__file__).parents[2]
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    script = script_dir / "evolve_skill_once.sh"
    shutil.copy(repo / "scripts" / "evolve_skill_once.sh", script)
    script.chmod(0o755)

    activate = tmp_path / ".venv" / "bin" / "activate"
    activate.parent.mkdir(parents=True)
    activate.write_text("# dummy activate\n")

    return script


def _write_fake_python(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"${OPENAI_API_KEY:-}\" == \"${EXPECTED_OPENAI_VALUE:-}\" ]]; then\n"
        "  printf 'OPENAI_MATCH_TRUE\\n'\n"
        "else\n"
        "  printf 'OPENAI_MATCH_FALSE\\n'\n"
        "fi\n"
    )
    fake_python.chmod(0o755)
    return fake_bin


def test_evolve_skill_once_loads_hermes_env_file(tmp_path):
    script = _copy_script_fixture(tmp_path)
    fake_bin = _write_fake_python(tmp_path)

    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    expected = "sentinel-from-hermes-env"
    (hermes_home / ".env").write_text(f"OPENAI_API_KEY={expected}\n")

    env = {
        "HOME": str(tmp_path),
        "HERMES_HOME": str(hermes_home),
        "EXPECTED_OPENAI_VALUE": expected,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        [str(script), "github-code-review", "3", "synthetic", "openai/gpt-5-mini", "openai/gpt-5-nano"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "OPENAI_MATCH_TRUE" in result.stdout


def test_evolve_skill_once_does_not_override_existing_env(tmp_path):
    script = _copy_script_fixture(tmp_path)
    fake_bin = _write_fake_python(tmp_path)

    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    (hermes_home / ".env").write_text("OPENAI_API_KEY=sentinel-from-hermes-env\n")
    expected = "explicit-env-wins"

    env = {
        "HOME": str(tmp_path),
        "HERMES_HOME": str(hermes_home),
        "OPENAI_API_KEY": expected,
        "EXPECTED_OPENAI_VALUE": expected,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        [str(script), "github-code-review"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "OPENAI_MATCH_TRUE" in result.stdout
