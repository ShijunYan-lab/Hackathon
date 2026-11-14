"""Ordinary pytest must never spend the user's live-model quota."""
import pytest

@pytest.fixture(autouse=True)
def no_real_provider_credentials(monkeypatch):
    monkeypatch.setenv('LLM_API_KEY', '')
    monkeypatch.setenv('LLM_BASE_URL', 'https://example.invalid')
    monkeypatch.setenv('LLM_MODEL', 'test')
