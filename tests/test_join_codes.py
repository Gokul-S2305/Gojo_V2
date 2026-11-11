import pytest
from app.routers.dashboard import _JOIN_CODE_CHARS, _title


def test_join_code_characters_exclude_ambiguous():
    # Ambiguous characters must not be in character pool
    ambiguous = {"0", "O", "1", "I", "L"}
    for ch in ambiguous:
        assert ch not in _JOIN_CODE_CHARS, f"Found ambiguous char '{ch}' in join code pool"


def test_title_casing_helper():
    assert _title("goa") == "Goa"
    assert _title("mumbai south") == "Mumbai South"
    assert _title("  new delhi  ") == "New Delhi"
    assert _title(None) is None
    assert _title("") is None
