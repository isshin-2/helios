"""
Tests — Secret Redactor
========================
Verifies:
- Known key formats are redacted from strings.
- Non-secret text is not modified.
- redact_dict() recurses through nested structures.
- Redaction does not raise on non-string inputs.
- Redacted output contains no original secret values.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.secret_redactor import redact, redact_dict


class TestRedact:
    def test_gemini_key_redacted(self):
        text = "Using key AIzaSyD1234567890abcdefghijklmnopqrstuvwx"
        result = redact(text)
        assert "AIzaSy" not in result
        assert "[REDACTED:" in result

    def test_openai_key_redacted(self):
        text = "Authorization: sk-abcdefghijklmnopqrstuvwxyz123456"
        result = redact(text)
        assert "sk-abcdefghijk" not in result
        assert "[REDACTED:" in result

    def test_groq_key_redacted(self):
        text = "key=gsk_abcdefghijklmnopqrstuvwxyz1234567890abcdefgh"
        result = redact(text)
        assert "gsk_abcde" not in result
        assert "[REDACTED:" in result

    def test_api_key_assignment_redacted(self):
        text = 'api_key="supersecret123456789012345"'
        result = redact(text)
        assert "supersecret" not in result
        assert "[REDACTED:" in result

    def test_env_secret_redacted(self):
        text = "OPENROUTER_API_KEY=sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890"
        result = redact(text)
        assert "sk-or-v1" not in result
        assert "[REDACTED:" in result

    def test_normal_text_unchanged(self):
        text = "Hello, the quick brown fox jumps over the lazy dog."
        assert redact(text) == text

    def test_empty_string_unchanged(self):
        assert redact("") == ""

    def test_none_unchanged(self):
        assert redact(None) is None  # type: ignore

    def test_integer_unchanged(self):
        assert redact(42) == 42  # type: ignore


class TestRedactDict:
    def test_dict_values_redacted(self):
        d = {"api_key": "sk-abcdefghijklmnopqrstuvwxyz123456", "model": "gpt-4"}
        result = redact_dict(d)
        assert "sk-abcdefg" not in result.get("api_key", "")
        assert result["model"] == "gpt-4"

    def test_nested_dict_redacted(self):
        d = {
            "config": {
                "key": "AIzaSyD1234567890abcdefghijklmnopqrstuvwx",
                "normal": "value",
            }
        }
        result = redact_dict(d)
        assert "AIzaSy" not in str(result)

    def test_list_items_redacted(self):
        lst = ["AIzaSyD1234567890abcdefghijklmnopqrstuvwx", "normal text"]
        result = redact_dict(lst)
        assert "AIzaSy" not in result[0]
        assert result[1] == "normal text"

    def test_original_not_mutated(self):
        original = {"key": "sk-abcdefghijklmnopqrstuvwxyz123456"}
        _ = redact_dict(original)
        # Original must be unchanged
        assert original["key"].startswith("sk-")

    def test_non_string_values_pass_through(self):
        d = {"count": 42, "flag": True, "data": None}
        result = redact_dict(d)
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["data"] is None
