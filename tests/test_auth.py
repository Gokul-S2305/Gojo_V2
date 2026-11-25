from app.auth_utils import (
    validate_password_strength,
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_password_strength_validation():
    # Too short (< 8 chars)
    assert validate_password_strength("Short1A") is not None

    # Missing uppercase
    assert validate_password_strength("nouppercase123") is not None

    # Missing digit
    assert validate_password_strength("NoDigitsHere") is not None

    # Valid password
    assert validate_password_strength("ValidPassword123") is None


def test_password_hashing():
    pw = "SuperSecureTrip123"
    hashed = get_password_hash(pw)

    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_jwt_token_creation_and_decoding():
    data = {"sub": "traveler@example.com", "user_id": 42}
    token = create_access_token(data)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload.get("sub") == "traveler@example.com"
    assert payload.get("user_id") == 42


def test_jwt_invalid_token():
    payload = decode_access_token("invalid.token.string")
    assert payload is None
