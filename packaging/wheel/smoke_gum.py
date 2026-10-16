"""Optional integration check: install this wheel and a local GumLang checkout first."""

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from gum_tcc import compiler_path


def main():
    compiler = compiler_path()
    if importlib.util.find_spec("gum") is None:
        raise SystemExit(
            "Install a local GumLang checkout first: python -m pip install -e PATH_TO_GUMLANG"
        )
    with tempfile.TemporaryDirectory(prefix="gum wheel app ") as temporary:
        root = Path(temporary)
        source = root / "main.gum"
        source.write_text(
            'def main() -> int32 {print("GUM bundled TCC passed")\nreturn 0}\n'
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "gum",
                "run",
                str(source),
                "--target",
                "windows-console",
                "--cc",
                str(compiler),
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
        assert result.stdout.strip() == "GUM bundled TCC passed", (
            result.stdout + result.stderr
        )
        print(result.stdout, end="")


if __name__ == "__main__":
    main()
