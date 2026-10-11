"""Pytest configuration: add the project root to sys.path so tests can import
app modules (database, finance_ml, etc.) without installing them as a package.
Also stubs the 'streamlit' module so app modules that import it at the top
level (utils, auth, etc.) can be imported in a plain-Python test environment."""

import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Streamlit stub – provides only the surface area used by app modules during
# import and in helpers called by tests. Real Streamlit features are not needed
# in unit / integration tests.
# ---------------------------------------------------------------------------
def _make_st_stub() -> types.ModuleType:
    stub = types.ModuleType("streamlit")

    # Bare minimum attributes accessed at module-import time
    stub.secrets = {}
    stub.session_state = {}

    # Common st.* functions used by utils/auth at import (must not raise)
    _noop = lambda *a, **kw: None
    for _name in (
        "set_page_config", "markdown", "write", "warning", "error", "info",
        "success", "stop", "rerun", "sidebar", "columns", "expander",
        "text_input", "button", "selectbox", "radio", "number_input",
        "text_area", "form", "form_submit_button", "metric", "divider",
        "spinner", "cache_data", "cache_resource", "dialog",
    ):
        setattr(stub, _name, _noop)

    # st.sidebar needs to support attribute access for sub-calls
    class _Sidebar:
        def __getattr__(self, name):
            return lambda *a, **kw: None
    stub.sidebar = _Sidebar()

    # st.columns should return iterable context managers
    class _Col:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def __getattr__(self, name): return lambda *a, **kw: None
    stub.columns = lambda n, **kw: [_Col() for _ in range(n if isinstance(n, int) else len(n))]

    # decorators that must return the original function unchanged
    stub.cache_data = lambda f=None, **kw: (f if f else lambda fn: fn)
    stub.cache_resource = lambda f=None, **kw: (f if f else lambda fn: fn)

    return stub


if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = _make_st_stub()

# ---------------------------------------------------------------------------
# google-genai stub – allows `patch("google.genai.Client")` in tests without
# the real google-genai package installed.
# ---------------------------------------------------------------------------
def _make_genai_stub() -> None:
    """Register minimal google.genai and google.genai.types stubs."""
    # Ensure the `google` namespace package exists
    if "google" not in sys.modules:
        google_mod = types.ModuleType("google")
        google_mod.__path__ = []  # make it a namespace package
        sys.modules["google"] = google_mod
    google_mod = sys.modules["google"]

    # google.genai
    genai_mod = types.ModuleType("google.genai")

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        class models:
            @staticmethod
            def generate_content(*a, **kw): return None

    genai_mod.Client = _FakeClient

    # google.genai.types
    types_mod = types.ModuleType("google.genai.types")

    class _Content:
        def __init__(self, *a, **kw): pass

    class _GenerateContentConfig:
        def __init__(self, *a, **kw): pass

    types_mod.Content = _Content
    types_mod.GenerateContentConfig = _GenerateContentConfig
    genai_mod.types = types_mod

    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.types"] = types_mod
    setattr(google_mod, "genai", genai_mod)


if "google.genai" not in sys.modules:
    _make_genai_stub()

# Add the project root (parent of tests/) to the Python path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
