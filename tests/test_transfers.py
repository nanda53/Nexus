"""Run: pip install -r requirements-dev.txt && pytest -v
Uses SQLite + an in-memory fake Redis, so no Docker is needed."""
import os
import tempfile

_db = os.path.join(tempfile.gettempdir(), "nexus_test.db")
if os.path.exists(_db):
    os.remove(_db)
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"

import uuid
import pytest
from fastapi.testclient import TestClient
from app import main


class FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)


@pytest.fixture(scope="module")
def client():
    main.redis_client = FakeRedis()
    with TestClient(main.app) as c:  # runs lifespan -> create tables + seed
        yield c


def login(client, email):
    r = client.post("/login", data={"username": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def accounts(client, headers):
    return client.get("/accounts", headers=headers).json()


def body(src, dest_number, amount, key=None):
    return {"source_account_id": src, "destination_account_number": dest_number,
            "amount": amount, "idempotency_key": key or str(uuid.uuid4())}


def test_login_wrong_password(client):
    r = client.post("/login", data={"username": "alice@bank.com", "password": "nope"})
    assert r.status_code == 400


def test_transfer_moves_money(client):
    h = login(client, "alice@bank.com")
    alice = accounts(client, h)[0]
    r = client.post("/transfers", json=body(alice["id"], "456", 100), headers=h)
    assert r.status_code == 200 and r.json()["status"] == "SUCCESS"
    assert accounts(client, h)[0]["balance"] == alice["balance"] - 100


def test_duplicate_click_moves_money_once(client):
    """The headline feature: same idempotency key twice => one transfer."""
    h = login(client, "alice@bank.com")
    alice = accounts(client, h)[0]
    payload = body(alice["id"], "456", 50, key="dup-key-12345")
    first = client.post("/transfers", json=payload, headers=h)
    second = client.post("/transfers", json=payload, headers=h)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["reference"] == second.json()["reference"]
    assert accounts(client, h)[0]["balance"] == alice["balance"] - 50  # not -100


def test_in_progress_duplicate_is_blocked(client):
    h = login(client, "alice@bank.com")
    alice = accounts(client, h)[0]
    main.redis_client.set(f"idempotency:{_user_id(client, h)}:busy-key-1234", "processing", nx=True)
    r = client.post("/transfers", json=body(alice["id"], "456", 10, key="busy-key-1234"), headers=h)
    assert r.status_code == 409


def _user_id(client, headers):
    from jose import jwt
    from app import security
    token = headers["Authorization"].split()[1]
    return jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])["sub"]


def test_insufficient_funds(client):
    h = login(client, "bob@bank.com")
    bob = accounts(client, h)[0]
    r = client.post("/transfers", json=body(bob["id"], "123", 9_999_999), headers=h)
    assert r.status_code == 400 and "Insufficient" in r.json()["detail"]


def test_cannot_spend_from_someone_elses_account(client):
    h_bob = login(client, "bob@bank.com")
    alice = accounts(client, login(client, "alice@bank.com"))[0]
    r = client.post("/transfers", json=body(alice["id"], "456", 10), headers=h_bob)
    assert r.status_code == 403


def test_same_account_rejected(client):
    h = login(client, "alice@bank.com")
    alice = accounts(client, h)[0]
    r = client.post("/transfers", json=body(alice["id"], alice["account_number"], 10), headers=h)
    assert r.status_code == 400


def test_failed_transfer_can_be_retried_with_same_key(client):
    h = login(client, "bob@bank.com")
    bob = accounts(client, h)[0]
    payload = body(bob["id"], "123", 9_999_999, key="retry-key-1234")
    assert client.post("/transfers", json=payload, headers=h).status_code == 400
    payload["amount"] = 5
    assert client.post("/transfers", json=payload, headers=h).status_code == 200


def test_requires_auth(client):
    assert client.get("/accounts").status_code == 401
