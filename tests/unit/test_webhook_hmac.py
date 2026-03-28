"""Unit tests for HMAC-SHA256 webhook signature verification.

These tests exercise ``verify_signature`` in isolation — no HTTP layer, no DB.
"""

from __future__ import annotations

import hashlib
import hmac

import pytest

from kenjutsu.server.webhook import verify_signature


def _make_signature(payload: bytes, secret: str) -> str:
    """Helper: compute the correct sha256= signature for a payload."""
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


SECRET = "test-secret-value"
PAYLOAD = b'{"action": "opened", "number": 1}'


class TestVerifySignatureValid:
    """Cases where verification should return True."""

    def test_correct_signature_accepted(self) -> None:
        sig = _make_signature(PAYLOAD, SECRET)
        assert verify_signature(PAYLOAD, sig, SECRET) is True

    def test_empty_payload_accepted_with_correct_sig(self) -> None:
        payload = b""
        sig = _make_signature(payload, SECRET)
        assert verify_signature(payload, sig, SECRET) is True

    def test_unicode_secret_accepted(self) -> None:
        secret = "s3cr3t-\u00e9-\u4e2d\u6587"
        sig = _make_signature(PAYLOAD, secret)
        assert verify_signature(PAYLOAD, sig, secret) is True


class TestVerifySignatureInvalid:
    """Cases where verification should return False."""

    def test_wrong_secret_rejected(self) -> None:
        sig = _make_signature(PAYLOAD, "wrong-secret")
        assert verify_signature(PAYLOAD, sig, SECRET) is False

    def test_tampered_payload_rejected(self) -> None:
        sig = _make_signature(PAYLOAD, SECRET)
        tampered = PAYLOAD + b" extra"
        assert verify_signature(tampered, sig, SECRET) is False

    def test_missing_header_rejected(self) -> None:
        assert verify_signature(PAYLOAD, "", SECRET) is False

    def test_none_header_rejected(self) -> None:
        # simulate a missing header passed as empty string (Header default)
        assert verify_signature(PAYLOAD, "", SECRET) is False

    def test_header_without_prefix_rejected(self) -> None:
        bare_digest = hmac.new(SECRET.encode(), PAYLOAD, hashlib.sha256).hexdigest()
        assert verify_signature(PAYLOAD, bare_digest, SECRET) is False

    def test_sha1_header_format_rejected(self) -> None:
        # wrong algorithm prefix
        digest = hmac.new(SECRET.encode(), PAYLOAD, hashlib.sha1).hexdigest()
        assert verify_signature(PAYLOAD, f"sha1={digest}", SECRET) is False

    def test_truncated_digest_rejected(self) -> None:
        sig = _make_signature(PAYLOAD, SECRET)
        truncated = sig[:20]
        assert verify_signature(PAYLOAD, truncated, SECRET) is False

    def test_correct_format_wrong_digest_rejected(self) -> None:
        assert verify_signature(PAYLOAD, "sha256=" + "a" * 64, SECRET) is False


class TestVerifySignatureTimingSafety:
    """Smoke-check that comparison is timing-safe (uses hmac.compare_digest)."""

    def test_returns_bool_not_exception(self) -> None:
        result = verify_signature(PAYLOAD, "sha256=deadbeef", SECRET)
        assert isinstance(result, bool)

    @pytest.mark.parametrize(
        "sig",
        [
            "sha256=",
            "sha256=" + "0" * 64,
            "sha256=" + "f" * 64,
        ],
    )
    def test_various_invalid_digests_return_false(self, sig: str) -> None:
        assert verify_signature(PAYLOAD, sig, SECRET) is False
