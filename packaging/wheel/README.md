# gumlang-tcc wheel

Build an installable **Windows x64** TinyCC companion package. This directory
builds `gumlang_tcc-0.9.28rc1.dev1-py3-none-win_amd64.whl`; it does not publish to
PyPI or change GUM's dependencies. No C compiler runs during wheel installation.
The initial version is a packaging development version of this repository's
`0.9.28rc` compiler, not an upstream TinyCC release number.

## Build on Windows

Use 64-bit Python 3.9+ and the **x64 Native Tools Command Prompt for Visual
Studio** (MSVC C build tools). Git must be installed. From the repository root:

```bat
py -m venv packaging\wheel\build\venv
packaging\wheel\build\venv\Scripts\python -m pip install build
packaging\wheel\build\venv\Scripts\python packaging\wheel\build.py
```

The wheel appears in `packaging/wheel/dist/`. Build in a checkout of the desired
compiler commit. Commit compiler changes first; the script uses `git archive
HEAD`, overlays the current wheel recipe, and builds in a temporary directory.
It never builds inside the working compiler tree. The archive included in the
wheel contains the exact pre-build snapshot, including this recipe. The embedded
`build-info.json` records the compiler commit, version, command and source hash.
The source archive is deterministic; binary reproducibility is not yet promised.

## Install and test without PyPI

On a Windows x64 machine with Python and **no C compiler installed**:

```bat
py -m venv "C:\temp\gum wheel test"
"C:\temp\gum wheel test\Scripts\python" -m pip install packaging\wheel\dist\gumlang_tcc-0.9.28rc1.dev1-py3-none-win_amd64.whl
"C:\temp\gum wheel test\Scripts\python" packaging\wheel\smoke.py
"C:\temp\gum wheel test\Scripts\gum-tcc" -v
```

The smoke check compiles and executes a program using standard headers, memory,
file I/O, math and Win32 APIs from a path containing spaces. The Windows workflow
also installs the wheel in a fresh environment and hides compiler toolchains from
PATH. It needs access only to this repository.
A hosted build runner with PATH restricted is useful evidence; a separate clean
Windows VM remains the final check for a release's system dependencies.

The Python package exposes `gum_tcc.compiler_path()` and `python -m gum_tcc`;
`gum-tcc` is the console wrapper. Nothing is added to the system PATH. Installed
executables and their `include/` and `lib/` trees remain together. Python versions
share the wheel because this package does not link against the CPython ABI.
Other operating systems/architectures have no compatible wheel, and no source
package is published by this recipe.

## Connecting GUM later

GUM still needs automatic discovery of `gum_tcc.compiler_path()` and a conditional
Windows x64 dependency on `gumlang-tcc`. Users' explicit compiler selections
should retain precedence. Unsupported platforms should continue installing GUM
without this dependency and use their own compiler. For development, install both
projects locally and run the integration smoke check:

```bat
python -m pip install -e C:\path\to\GumLang
python packaging\wheel\smoke_gum.py
```

That script passes the bundled compiler using GUM's `--cc` option. This package
alone does not make the existing `pip install gumlang` self-contained. The GUM
check is kept out of this repository's workflow because `GumLang` is private and
the default Actions token cannot read another private repository. No extra token
is needed to build or download a compiler wheel.

Threading/async, graphics and arbitrary native SDKs are not promised by the
compiler smoke test. GUM currently excludes TCC from its threading path.

## Licenses and corresponding source

The payload includes the repository's `COPYING` (LGPL 2.1), original notices in
headers, the compiler's support files, and `source/tinycc-source.tar.gz` containing
all source files and the wheel/build scripts. Do not strip that source archive or
notices when redistributing a wheel. Support code has its own notices, including
`lib/libtcc1.c`'s GPL terms with a linking exception; those files remain in the
corresponding source. This recipe does not copy an MSVC SDK or redistributable
into the wheel. The compiler is built with the upstream MSVC script's static CRT
option, and `libtcc.dll` accompanies `tcc.exe`.

To rebuild from the bundled source, extract it, enter its `tinycc` directory and
initialize/commit a local Git checkout, then follow the build steps above. That
new local commit will differ in provenance from the original wheel. Run upstream
TinyCC tests as well when changing compiler code.

Run packaging tests on any development host:

```sh
python -m pip install build wheel setuptools
python -m unittest discover -s packaging/wheel/tests -v
```
