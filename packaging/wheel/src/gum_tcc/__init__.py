"""Find and invoke the compiler without modifying the machine's PATH."""

import platform
import subprocess
import sys
from pathlib import Path


def compiler_path():
    """Absolute bundled compiler path; headers/libraries live alongside it."""
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("gumlang-tcc currently supports Windows x64 only")
    executable = Path(__file__).resolve().parent / "_payload/tcc.exe"
    if not executable.is_file():
        raise RuntimeError(
            "Bundled TCC is missing; reinstall the Windows gumlang-tcc wheel"
        )
    return executable


def main():
    try:
        executable = compiler_path()
        return subprocess.call(
            [str(executable), "-B" + str(executable.parent), *sys.argv[1:]]
        )
    except (OSError, RuntimeError) as error:
        print("gum-tcc: " + str(error), file=sys.stderr)
        return 1
