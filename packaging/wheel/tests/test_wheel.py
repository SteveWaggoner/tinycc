"""Packaging contract tests. Synthetic binaries here are never executed."""

import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wheel_builder", HERE / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
spec = importlib.util.spec_from_file_location(
    "gum_tcc", HERE / "src/gum_tcc/__init__.py"
)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class WheelTests(unittest.TestCase):
    def test_source_archive_is_complete_and_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "COPYING").write_text("license notices")
            (source / "compiler.c").write_text("/* source */")
            first, second = root / "a.gz", root / "b.gz"
            builder.source_bundle(source, first)
            (source / "compiler.c").touch()
            builder.source_bundle(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first) as archive:
                self.assertEqual(
                    set(archive.getnames()), {"tinycc/COPYING", "tinycc/compiler.c"}
                )

    def test_binary_architecture_must_match_wheel_tag(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tcc.exe"
            data = bytearray(128)
            data[:2] = b"MZ"
            struct.pack_into("<I", data, 0x3C, 64)
            data[64:68] = b"PE\0\0"
            struct.pack_into("<H", data, 68, 0x8664)
            path.write_bytes(data)
            builder.validate_executable(path)
            struct.pack_into("<H", data, 68, 0x14C)
            path.write_bytes(data)
            with self.assertRaisesRegex(RuntimeError, "Expected x64 executable"):
                builder.validate_executable(path)

    def test_unsupported_host_has_actionable_error(self):
        with (
            patch.object(api.sys, "platform", "linux"),
            self.assertRaisesRegex(RuntimeError, "Windows x64 only"),
        ):
            api.compiler_path()

    def test_cli_uses_absolute_paths_and_preserves_arguments_and_exit_code(self):
        with (
            patch.object(
                api, "compiler_path", return_value=Path("C:/path with spaces/tcc.exe")
            ),
            patch.object(
                api.sys, "argv", ["gum-tcc", "file with spaces.c", "-o", "out.exe"]
            ),
            patch.object(api.subprocess, "call", return_value=7) as call,
        ):
            self.assertEqual(api.main(), 7)
            compiler = Path("C:/path with spaces/tcc.exe")
            self.assertEqual(
                call.call_args.args[0],
                [
                    str(compiler),
                    "-B" + str(compiler.parent),
                    "file with spaces.c",
                    "-o",
                    "out.exe",
                ],
            )

    def build(self, project, output):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                str(output),
                str(project),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_platform_tag_and_payload_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "recipe"
            shutil.copytree(
                HERE,
                project,
                ignore=shutil.ignore_patterns(
                    "build", "dist", "*.egg-info", "__pycache__", "_payload"
                ),
            )
            (project / "LICENSE").write_text((builder.REPO / "COPYING").read_text())
            payload = project / "src/gum_tcc/_payload"
            # These are layout fixtures, not usable Windows executables.
            files = {
                "tcc.exe": b"MZ-test-fixture",
                "libtcc.dll": b"MZ-test-fixture",
                "include/stdio.h": b"/* header */",
                "include/winapi/windows.h": b"/* header */",
                "lib/libtcc1.a": b"archive fixture",
                "lib/kernel32.def": b"LIBRARY KERNEL32.DLL",
                "COPYING": b"license",
                "source/tinycc-source.tar.gz": b"source fixture",
                "build-info.json": json.dumps({"commit": "test"}).encode(),
            }
            for name, data in files.items():
                path = payload / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            output = root / "wheels"
            result = self.build(project, output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            wheels = list(output.glob("*.whl"))
            self.assertEqual(len(wheels), 1)
            self.assertTrue(wheels[0].name.endswith("-py3-none-win_amd64.whl"))
            with zipfile.ZipFile(wheels[0]) as wheel:
                for name, data in files.items():
                    self.assertEqual(wheel.read("gum_tcc/_payload/" + name), data)
                metadata = next(
                    name
                    for name in wheel.namelist()
                    if name.endswith(".dist-info/WHEEL")
                )
                self.assertIn("Root-Is-Purelib: false", wheel.read(metadata).decode())
                self.assertTrue(
                    any(name.endswith("licenses/LICENSE") for name in wheel.namelist())
                )
            shutil.rmtree(payload)
            shutil.rmtree(project / "build")
            result = self.build(project, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing compiler bundle", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
