from __future__ import annotations

import json
import runpy
import subprocess
from pathlib import Path


def main() -> None:
    versions_path = Path(__file__).resolve().parent.parent / "versions.json"
    versions = json.loads(versions_path.read_text(encoding="utf-8"))

    print()
    print("HEA version launcher")
    print("====================")
    for item in versions:
        print(f"{item['key']}. {item['name']} - {item['description']}")
    print()

    default_key = versions[0]["key"] if versions else "v2"
    choice = input(f"Choose version [{default_key}]: ").strip() or default_key
    selected = next(
        (
            item
            for item in versions
            if item["key"].lower() == choice.lower()
            or item["name"].lower() == choice.lower()
            or choice.lower() in [alias.lower() for alias in item.get("aliases", [])]
            or choice.lower() == "hea"
        ),
        None,
    )
    if not selected:
        print(f"Unknown version: {choice}")
        raise SystemExit(1)

    working_dir = Path(selected.get("working_dir", "")).expanduser() if selected.get("working_dir") else None
    if working_dir:
        python_path = Path(selected.get("python", working_dir / ".venv" / "Scripts" / "python.exe"))
        module = selected["module"]
        raise SystemExit(subprocess.call([str(python_path), "-m", module], cwd=working_dir))

    runpy.run_module(selected["module"], run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
