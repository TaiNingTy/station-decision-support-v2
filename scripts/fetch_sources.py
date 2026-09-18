"""Fetch declared public sources; leave existing files intact and keep TLS checks on."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "sources.json").read_text())
    raw = ROOT / "raw"
    raw.mkdir(exist_ok=True)
    for entry in manifest["downloads"]:
        name = entry["file"]
        if Path(name).name != name or not entry["url"].startswith("https://"):
            raise ValueError("Expected a plain filename and HTTPS public source")
        output = raw / name
        if output.exists():
            print(f"Kept existing {name}")
            continue
        temporary = output.with_suffix(output.suffix + ".part")
        subprocess.run(["curl", "--fail", "--location", "--max-time", "60", "--silent", "--show-error",
                        entry["url"], "--output", str(temporary)], check=True)
        if temporary.stat().st_size == 0:
            raise ValueError(f"Empty response: {name}")
        temporary.replace(output)
        print(f"Downloaded {name}")


if __name__ == "__main__":
    main()
