from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import time
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.database import connect

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'test.db')
    with TestClient(app) as c:
        c.db_path = tmp_path / 'test.db'
        yield c

def auth(c, email='alice@example.com'):
    data = dict(name='Alice', email=email, password='StrongPass123!')
    assert c.post('/signup', json=data).status_code == 201
    result = c.post('/login', json={k: data[k] for k in ('email', 'password')})
    return {'Authorization': 'Bearer ' + result.json()['access_token']}, result.json()

def class_data(slots=2):
    return dict(name='Yoga', dateTime=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(), instructor='Jane', availableSlots=slots)

def make_class(c, headers, slots=2):
    r = c.post('/classes', headers=headers, json=class_data(slots))
    assert r.status_code == 201
    return r.json()['id']

def book(c, h, cid):
    return c.post('/book', headers=h, json=dict(class_id=cid, client_name='Guest', client_email='guest@example.com'))

def test_auth_and_refresh(client):
    h, tokens = auth(client)
    assert client.post('/signup', json=dict(name='Alice', email='ALICE@example.com', password='StrongPass123!')).status_code == 409
    assert client.post('/login', json=dict(email='alice@example.com', password='WrongPass123')).status_code == 401
    assert client.get('/bookings').status_code == 401
    assert client.get('/bookings', headers={'Authorization': 'Bearer invalid'}).status_code == 401
    assert client.post('/classes', json=class_data()).status_code == 401
    assert book(client, {}, 1).status_code == 401
    r = client.post('/refresh', json={'refresh_token': tokens['refresh_token']})
    assert r.status_code == 200
    assert client.post('/refresh', json={'refresh_token': tokens['refresh_token']}).status_code == 401
    with connect(client.db_path) as db:
        db.execute('UPDATE tokens SET expires=?', (time.time()-1,))
    assert client.get('/bookings', headers=h).status_code == 401
    assert client.post('/refresh', json={'refresh_token': r.json()['refresh_token']}).status_code == 401

def test_booking_ownership_duplicates_and_capacity(client):
    a, _ = auth(client)
    b, _ = auth(client, 'bob@example.com')
    cid = make_class(client, a, 1)
    assert book(client, a, cid).status_code == 201
    assert book(client, a, cid).status_code == 409
    assert book(client, b, cid).status_code == 409
    assert book(client, b, 999).status_code == 404
    assert len(client.get('/bookings', headers=a).json()) == 1
    assert client.get('/bookings', headers=b).json() == []
    assert client.get('/classes').json()[0]['availableSlots'] == 0

def test_timezone_and_past_classes(client):
    h, _ = auth(client)
    cid = make_class(client, h)
    ist = client.get('/classes').json()[0]['dateTime']
    utc = client.get('/classes?timezone=UTC').json()[0]['dateTime']
    assert ist.endswith('+05:30')
    assert datetime.fromisoformat(ist) == datetime.fromisoformat(utc)
    assert client.get('/classes?timezone=Invalid/Zone').status_code == 422
    with connect(client.db_path) as db:
        assert db.execute('SELECT date_time FROM classes').fetchone()[0].endswith('+05:30')
        db.execute("UPDATE classes SET date_time='2000-01-01T10:00:00+05:30'")
    assert client.get('/classes').json() == []
    assert book(client, h, cid).status_code == 409

@pytest.mark.parametrize('change', [{'availableSlots':0}, {'availableSlots':-1}, {'availableSlots':True}, {'name':' '}, {'dateTime':'2027-01-01T10:00:00'}, {'dateTime':'2000-01-01T10:00:00Z'}])
def test_class_validation(client, change):
    h, _ = auth(client)
    assert client.post('/classes', headers=h, json={**class_data(), **change}).status_code == 422

def test_invalid_inputs(client):
    assert client.post('/signup', json={}).status_code == 422
    assert client.post('/signup', json=dict(name='A', email='bad', password='123')).status_code == 422
    h, _ = auth(client)
    assert client.post('/book', headers=h, json={}).status_code == 422
    assert client.post('/book', headers=h, json=dict(class_id=1, client_name='A', client_email='bad')).status_code == 422

def test_concurrent_last_slot(client):
    headers = [auth(client, f'user{i}@example.com')[0] for i in range(6)]
    cid = make_class(client, headers[0], 1)
    with ThreadPoolExecutor(max_workers=6) as executor:
        statuses = list(executor.map(lambda h: book(client, h, cid).status_code, headers))
    assert statuses.count(201) == 1
    assert statuses.count(409) == 5
    with connect(client.db_path) as db:
        assert db.execute('SELECT COUNT(*) FROM bookings').fetchone()[0] == 1
        assert db.execute('SELECT available_slots FROM classes').fetchone()[0] == 0

def test_docs(client):
    assert client.get('/docs').status_code == 200
    assert set(['/signup','/login','/classes','/book','/bookings','/refresh']) <= client.get('/openapi.json').json()['paths'].keys()
