"""Run after installing the wheel into a fresh Windows x64 virtual environment."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from gum_tcc import compiler_path


def main():
    compiler = compiler_path()
    payload = compiler.parent
    info = json.loads((payload / "build-info.json").read_text())
    source = payload / "source/tinycc-source.tar.gz"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == info["source_sha256"]
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in (payload / "COPYING").read_text()
    with tempfile.TemporaryDirectory(prefix="gum tcc smoke with spaces ") as temporary:
        root = Path(temporary)
        (root / "hello.c").write_text(r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <windows.h>
int main(void) {
    char *copy = malloc(16);
    FILE *file;
    volatile double input = 9.0;
    if (!copy || sizeof(void*) != 8 || GetCurrentProcessId() == 0) return 1;
    strcpy(copy, "bundled tcc");
    file = fopen("roundtrip.txt", "wb");
    if (!file || fwrite(copy, 1, strlen(copy), file) != strlen(copy)) return 2;
    fclose(file);
    free(copy);
    if (sqrt(input) != 3.0) return 3;
    puts("bundled tcc passed");
    return 0;
}
""")
        executable = root / "hello.exe"
        subprocess.run(
            [sys.executable, "-m", "gum_tcc", root / "hello.c", "-o", executable],
            cwd=root,
            check=True,
        )
        result = subprocess.run(
            [executable], cwd=root, check=True, capture_output=True, text=True
        )
        assert result.stdout.strip() == "bundled tcc passed", result.stdout
        assert (root / "roundtrip.txt").read_text() == "bundled tcc"
        # Exercise the directly discoverable executable too: its own relative
        # headers/library search must survive installation/relocation.
        subprocess.run(
            [compiler, root / "hello.c", "-o", executable], cwd=root, check=True
        )
        subprocess.run([executable], cwd=root, check=True)
    print("Installed Windows x64 compiler smoke test passed")


if __name__ == "__main__":
    main()
