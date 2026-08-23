import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from database import engine, Base
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def teardown_module(module):
    if os.path.exists("test.db"):
        os.remove("test.db")


def signup(email="ada@example.com", username="ada", password="secret123"):
    return client.post(
        "/api/auth/signup",
        json={"username": username, "email": email, "password": password},
    )


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_signup_creates_user_and_returns_token():
    res = signup()
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["email"] == "ada@example.com"
    assert "access_token" in body


def test_signup_rejects_duplicate_email():
    signup()
    res = signup(username="ada2")
    assert res.status_code == 400


def test_login_with_correct_credentials():
    signup()
    res = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "secret123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_with_wrong_password_fails():
    signup()
    res = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "wrong"})
    assert res.status_code == 401


def test_create_and_list_boards():
    token = signup().json()["access_token"]
    headers = auth_headers(token)

    res = client.post("/api/boards", json={"name": "Sprint 1", "description": "First sprint"}, headers=headers)
    assert res.status_code == 201

    res = client.get("/api/boards", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "Sprint 1"


def test_task_lifecycle_on_a_board():
    token = signup().json()["access_token"]
    headers = auth_headers(token)

    board = client.post("/api/boards", json={"name": "Backend"}, headers=headers).json()

    res = client.post(
        f"/api/boards/{board['id']}/tasks",
        json={"title": "Set up FastAPI project"},
        headers=headers,
    )
    assert res.status_code == 201
    task = res.json()
    assert task["status"] == "todo"

    res = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "done"

    res = client.delete(f"/api/tasks/{task['id']}", headers=headers)
    assert res.status_code == 204

    res = client.get(f"/api/boards/{board['id']}/tasks", headers=headers)
    assert res.json() == []


def test_unauthenticated_request_is_rejected():
    res = client.get("/api/boards")
    assert res.status_code == 401


def test_user_cannot_access_another_users_board():
    token_a = signup(email="a@example.com", username="usera").json()["access_token"]
    token_b = signup(email="b@example.com", username="userb").json()["access_token"]

    board = client.post("/api/boards", json={"name": "Private"}, headers=auth_headers(token_a)).json()

    res = client.get(f"/api/boards/{board['id']}", headers=auth_headers(token_b))
    assert res.status_code == 403
