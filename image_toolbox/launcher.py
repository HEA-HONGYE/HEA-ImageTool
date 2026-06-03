from __future__ import annotations

import runpy


def main() -> None:
    runpy.run_module("image_toolbox", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
