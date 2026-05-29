"""Test configuration: patch pypdf dependency for offline test environment."""
import sys
import types

# pypdf is not available in this environment; provide a minimal stub
# so the rest of the import chain loads successfully.
if "pypdf" not in sys.modules:
    fake_module = types.ModuleType("pypdf")
    fake_module.__file__ = "<pypdf-stub>"

    class FakePdfReader:
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            pass

    fake_module.PdfReader = FakePdfReader
    sys.modules["pypdf"] = fake_module
