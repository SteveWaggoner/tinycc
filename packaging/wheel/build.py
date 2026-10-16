"""Build from a pinned compiler snapshot, in a temporary Windows directory."""

import argparse
import gzip
import hashlib
import json
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def run(*args, cwd=None):
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def snapshot(destination):
    """Use committed compiler sources plus the current wheel recipe."""
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=REPO, text=True
    ).splitlines()
    if any(not name.startswith("packaging/wheel/") for name in changed):
        raise RuntimeError(
            "Commit compiler changes first: binaries must match the source snapshot"
        )
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    archive = destination.parent / "checkout.tar"
    run("git", "archive", "--format=tar", "--output=" + str(archive), commit, cwd=REPO)
    with tarfile.open(archive) as source:
        # git archive contains trusted local repository paths. Still reject links
        # and traversal so extraction never escapes the temporary build root.
        for member in source.getmembers():
            name = Path(member.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or member.issym()
                or member.islnk()
            ):
                raise RuntimeError("Unsupported source archive path: " + member.name)
        source.extractall(destination)
    recipe = destination / "packaging/wheel"
    shutil.rmtree(recipe, ignore_errors=True)
    shutil.copytree(
        HERE,
        recipe,
        ignore=shutil.ignore_patterns(
            "build", "dist", "*.egg-info", "__pycache__", "_payload", "LICENSE"
        ),
    )
    return commit


def source_bundle(source, archive):
    """Ship exact pre-build sources, including this wheel's build recipe."""
    with (
        archive.open("wb") as output,
        gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as bundle,
    ):
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            info = bundle.gettarinfo(
                str(path), "tinycc/" + path.relative_to(source).as_posix()
            )
            info.mtime, info.uid, info.gid = 0, 0, 0
            info.uname = info.gname = ""
            with path.open("rb") as content:
                bundle.addfile(info, content)


def validate_executable(path):
    """Do not label a 32-bit compiler or DLL as a Windows x64 payload."""
    data = path.read_bytes()
    if len(data) < 64 or data[:2] != b"MZ":
        raise RuntimeError("Not a Windows executable: " + str(path))
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if offset + 6 > len(data) or data[offset : offset + 4] != b"PE\0\0":
        raise RuntimeError("Invalid PE header: " + str(path))
    if struct.unpack_from("<H", data, offset + 4)[0] != 0x8664:
        raise RuntimeError(
            "Expected x64 executable; use the x64 MSVC developer shell: " + str(path)
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "dist")
    args = parser.parse_args()
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        parser.error("Build on Windows x64 in an x64 Visual Studio developer shell")
    if not shutil.which("cl"):
        parser.error("cl.exe not found; use the x64 Native Tools Command Prompt")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gum tcc wheel ") as temporary:
        work = Path(temporary)
        source = work / "source"
        commit = snapshot(source)
        corresponding_source = work / "tinycc-source.tar.gz"
        source_bundle(source, corresponding_source)
        run(
            "cmd.exe",
            "/d",
            "/c",
            "build-tcc.bat",
            "-c",
            "cl",
            "-t",
            "x86_64",
            cwd=source / "win32",
        )
        recipe = source / "packaging/wheel"
        payload = recipe / "src/gum_tcc/_payload"
        payload.mkdir(parents=True)
        for name in ("tcc.exe", "libtcc.dll"):
            validate_executable(source / "win32" / name)
            shutil.copy2(source / "win32" / name, payload / name)
        shutil.copytree(source / "win32/include", payload / "include")
        (payload / "lib").mkdir()
        for path in (source / "win32/lib").iterdir():
            if path.suffix in {".a", ".o", ".def"}:
                shutil.copy2(path, payload / "lib" / path.name)
        shutil.copy2(source / "COPYING", payload / "COPYING")
        shutil.copy2(source / "COPYING", recipe / "LICENSE")
        shutil.copy2(source / "win32/tcc-win32.txt", payload / "tcc-win32.txt")
        (payload / "source").mkdir()
        shutil.copy2(
            corresponding_source, payload / "source" / corresponding_source.name
        )
        info = {
            "repository": "https://github.com/SteveWaggoner/tinycc",
            "commit": commit,
            "tcc_version": (source / "VERSION").read_text().strip(),
            "platform": "win_amd64",
            "source_sha256": hashlib.sha256(
                corresponding_source.read_bytes()
            ).hexdigest(),
            "build": "win32/build-tcc.bat -c cl -t x86_64",
        }
        (payload / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
        # No sdist and no PyPI upload. Compiler construction happens here, never
        # while pip installs the resulting wheel.
        run(sys.executable, "-m", "build", "--wheel", "--outdir", output, recipe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
