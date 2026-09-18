# Rebuilding the release with a modified libscca

The release ZIP includes `sources/libscca_python-20260527.tar.gz`, the source
used to build its pyscca extension, and `sources/prefetch2es-source.tar.gz`,
the application's release commit including its lockfile and build workflow.
The libscca archive includes its bundled C libraries and build scripts.
GPL v3 and LGPL v3 texts are included in `LICENSES.txt` and the libscca source.

You may modify libscca and rebuild the application with it. The project's MIT
license does not prohibit modification or reverse engineering for debugging
such library modifications. No signing key or activation step is required.

1. Install Python 3.13 and uv. On Linux install a C compiler, Python development
   headers if your Python distribution needs them, and patchelf. On Windows
   install Visual Studio Build Tools with the C++ workload and Windows SDK.
2. Extract both source archives. Edit the libscca sources as desired.
3. In the extracted `prefetch2es` directory run:

   ```sh
   uv sync --locked
   uv pip install --python .venv/bin/python --reinstall --no-deps ../libscca_python-20260527
   uv run --no-sync python -c "import pyscca; print(pyscca.get_version())"
   uv run --no-sync python -m nuitka --standalone --onefile --follow-imports -o prefetch2es --output-dir=dist --assume-yes-for-downloads src/prefetch2es/views/Prefetch2esView.py
   uv run --no-sync python -m nuitka --standalone --onefile --follow-imports -o prefetch2json --output-dir=dist --assume-yes-for-downloads src/prefetch2es/views/Prefetch2jsonView.py
   uv run --no-sync python .github/collect_runtime_licenses.py dist/LICENSES.txt
   ```

   On Windows replace `.venv/bin/python` with `.venv/Scripts/python.exe`.
   Adjust the relative path to the extracted libscca directory if necessary.
   Keep `--no-sync`: synchronizing again can replace your modified extension.

The rebuilt commands are in `dist/` (with `.exe` on Windows). This procedure
recompiles the onefile application; it does not depend on replacing a library
inside Nuitka's temporary extraction directory. It requires internet access
to obtain the remaining dependencies and build tools. Bit-identical output
is not required to run a modified library.
