"""
Smoke test: verify the entire Nagstamon package can be loaded without errors.

Strategy
--------
* Non-GUI modules (servers, config, helpers, objects, cookies, thirdparty):
  imported with importlib so that both syntax *and* runtime importability are
  validated.  A broken import (e.g. undefined name, missing internal dependency)
  will be caught here.

* GUI modules (Nagstamon/qui/**):
  Require a Qt installation and a running display which are not available in a
  headless CI environment.  They are therefore validated for *syntax only* using
  py_compile, which is sufficient to catch typos and structural Python errors.

* Vendored Xlib (Nagstamon/thirdparty/Xlib and ewmh):
  A version mismatch between the bundled Xlib and a system-installed python-xlib
  can cause AttributeErrors at import time that are not caused by Nagstamon code.
  These files are therefore also validated for *syntax only* via py_compile.
"""
import importlib
import py_compile
import unittest
from pathlib import Path

# Root of the installed package on disk
_PACKAGE_ROOT = Path(__file__).parent.parent / 'Nagstamon'


def _path_to_module(path: Path) -> str:
    """Convert an absolute .py path inside the Nagstamon package to a dotted module name."""
    rel = path.relative_to(_PACKAGE_ROOT.parent)   # relative to repo root
    parts = list(rel.with_suffix('').parts)
    return '.'.join(parts)


class TestImportNonGuiModules(unittest.TestCase):
    """Each non-GUI .py file is turned into a separate test method at class creation
    time so that failures are reported individually."""


class TestSyntaxGuiModules(unittest.TestCase):
    """Each GUI .py file and vendored Xlib file gets its own syntax-check test method."""


def _make_import_test(module_name: str):
    def test(self):
        # Let any import error propagate so unittest shows the full traceback.
        importlib.import_module(module_name)
    test.__name__ = f'test_import_{module_name.replace(".", "_")}'
    return test
def _make_syntax_test(py_file: Path):
    def test(self):
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as exc:
            self.fail(f'Syntax error in {py_file}: {exc}')
    test.__name__ = f'test_syntax_{_path_to_module(py_file).replace(".", "_")}'
    return test


# Collect and attach test methods at import time so unittest discovers them.
for _py_file in sorted(_PACKAGE_ROOT.rglob('*.py')):
    # Skip compiled cache directories
    if '__pycache__' in _py_file.parts:
        continue

    _module = _path_to_module(_py_file)

    if '.qui.' in _module or _module.endswith('.qui'):
        # GUI module: syntax check only (requires Qt / display)
        _test_fn = _make_syntax_test(_py_file)
        setattr(TestSyntaxGuiModules, _test_fn.__name__, _test_fn)
    elif '.thirdparty.Xlib' in _module or _module == 'Nagstamon.thirdparty.ewmh':
        # Vendored Xlib: syntax check only (version may differ from system python-xlib)
        _test_fn = _make_syntax_test(_py_file)
        setattr(TestSyntaxGuiModules, _test_fn.__name__, _test_fn)
    else:
        # Non-GUI module: full import
        _test_fn = _make_import_test(_module)
        setattr(TestImportNonGuiModules, _test_fn.__name__, _test_fn)


if __name__ == '__main__':
    unittest.main()
