"""Generate local credentials; preserve existing non-placeholder values."""

from pathlib import Path
import secrets

SECRET_NAMES = (
    "POSTGRES_PASSWORD",
    "DEMO_CONTROL_TOKEN",
    "INVESTIGATOR_TOKEN",
    "APPROVER_TOKEN",
    "GRAFANA_PASSWORD",
)


def configure(path):
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for name in SECRET_NAMES:
        indices = [i for i, line in enumerate(lines) if line.startswith(name + "=")]
        if len(indices) > 1:
            raise ValueError(
                f"Duplicate {name} entries; resolve them privately in .env"
            )
        if indices:
            index = indices[0]
            value = lines[index].split("=", 1)[1].strip().strip("\"'")
            if value and not value.startswith(("replace-", "CHANGE_ME", "your-")):
                continue
            lines[index] = name + "=" + secrets.token_hex(24)
        else:
            lines.append(name + "=" + secrets.token_hex(24))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    configure(Path(__file__).resolve().parents[1] / ".env")
    print("Local environment configured. Existing non-placeholder values preserved.")
    print(
        "Existing database volumes retain their passwords; see README before rotation."
    )
