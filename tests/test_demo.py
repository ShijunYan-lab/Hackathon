from fastapi.testclient import TestClient
from server.main import create_app


def test_demo_assets_and_real_backend_share_origin(tmp_path):
    with TestClient(create_app(tmp_path / 'demo.sqlite3')) as client:
        page = client.get('/demo/')
        assert page.status_code == 200
        assert '世界实验台' in page.text and '合成输入' in page.text
        assert client.get('/demo/app.js').status_code == 200
        assert client.get('/demo/style.css').status_code == 200
        state = client.post('/v1/worlds', json={'request_id': 'demo', 'seed': 42,
            'player_name': '旅人'}).json()['data']['state']
        path = '/v1/worlds/' + state['world_id']
        assert client.get(path + '/story').json()['ok']
        assert client.get(path + '/economy').json()['ok']
        assert client.get('/demo/../../.env').status_code == 404
