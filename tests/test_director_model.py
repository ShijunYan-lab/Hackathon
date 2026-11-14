import asyncio
import json
import httpx
import pytest
from server.world.model_gateway import DirectorModel, ModelUnavailable
from test_world_director import context


def test_model_receives_real_history_and_validates_json_without_exposing_key():
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        assert request.headers['authorization'] == 'Bearer test-secret'
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({
            'summary': '发生货物损失', 'source_event_ids': ['evt_test'], 'proposals': []})}}]})
    provider = DirectorModel('https://model.example/v1', 'test-model', 'test-secret', httpx.MockTransport(handler))
    result = asyncio.run(provider(context()))
    assert result.source_event_ids == ['evt_test']
    assert 'cargo_lost' in captured[0]['messages'][1]['content']
    assert 'test-secret' not in json.dumps(captured)


@pytest.mark.parametrize('status,body,code', [(401, {'secret': 'must-not-leak'}, 'MODEL_AUTH_FAILED'),
    (429, {}, 'MODEL_RATE_LIMITED'), (200, {'choices': []}, 'MODEL_INVALID_OUTPUT')])
def test_provider_errors_are_sanitized(status, body, code):
    provider = DirectorModel('https://model.example/v1', 'test', 'secret',
                             httpx.MockTransport(lambda request: httpx.Response(status, json=body)))
    with pytest.raises(ModelUnavailable) as error:
        asyncio.run(provider(context()))
    assert str(error.value) == code


def test_unconfigured_transport_never_contacts_model(monkeypatch):
    for key in ('WORLD_MODEL_BASE_URL', 'WORLD_MODEL_NAME', 'WORLD_MODEL_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    assert DirectorModel.from_environment() is None
