"""This wheel carries Windows programs, not a CPython extension."""

from pathlib import Path

from setuptools import Distribution, setup
from setuptools.command.build_py import build_py
from wheel.bdist_wheel import bdist_wheel


class PlatformDistribution(Distribution):
    def has_ext_modules(self):
        return True


class WindowsWheel(bdist_wheel):
    def get_tag(self):
        # No Python ABI dependency; do not accidentally advertise a universal wheel.
        return "py3", "none", "win_amd64"


class BundleBuild(build_py):
    def run(self):
        root = Path(__file__).parent / "src/gum_tcc/_payload"
        required = (
            "tcc.exe",
            "libtcc.dll",
            "include/stdio.h",
            "include/winapi/windows.h",
            "lib/libtcc1.a",
            "lib/kernel32.def",
            "COPYING",
            "source/tinycc-source.tar.gz",
            "build-info.json",
        )
        missing = [name for name in required if not (root / name).is_file()]
        if missing:
            raise RuntimeError(
                "Missing compiler bundle; use build.py from Windows x64: "
                + ", ".join(missing)
            )
        super().run()


setup(
    distclass=PlatformDistribution,
    cmdclass={"bdist_wheel": WindowsWheel, "build_py": BundleBuild},
)
