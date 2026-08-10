import importlib
import os
import sys


ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_normalize_base_url_adds_https_prefix():
    from llm.client import normalize_base_url

    assert normalize_base_url("api.openai.com/v1") == "https://api.openai.com/v1"
    assert normalize_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert normalize_base_url("   ") is None
