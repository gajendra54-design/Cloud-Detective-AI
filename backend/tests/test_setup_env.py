import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "setup_env", Path(__file__).resolve().parents[2] / "scripts/setup_env.py"
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_setup_replaces_placeholders_and_preserves_existing_secrets(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "POSTGRES_PASSWORD=replace-with-random-password\n"
        "DEMO_CONTROL_TOKEN=existing-private-test-value\nAI_PROVIDER=mock\n"
    )
    setup.configure(path)
    values = dict(line.split("=", 1) for line in path.read_text().splitlines())
    assert len(values["POSTGRES_PASSWORD"]) == 48
    assert values["DEMO_CONTROL_TOKEN"] == "existing-private-test-value"
    assert values["AI_PROVIDER"] == "mock"
    assert all(values[name] for name in setup.SECRET_NAMES)
    original = path.read_text()
    setup.configure(path)
    assert path.read_text() == original
