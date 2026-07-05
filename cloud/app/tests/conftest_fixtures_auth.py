import uuid

import pytest

from shared.auth import hash_password
from shared.conftest_base import get_pg_url, is_pg

from .conftest_fixtures_core import TEST_DB


def _register_and_login(client, username, password):
    resp = client.post("/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201, resp.text
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


@pytest.fixture
def auth_token(client):
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    return _register_and_login(client, username, "testpass123")


@pytest.fixture
def admin_token(client):
    username = f"admin_{uuid.uuid4().hex[:8]}"
    password = "CHANGE_ME"
    hashed = hash_password(password)

    if is_pg():
        import psycopg

        pg_url = get_pg_url(TEST_DB)
        conn = psycopg.connect(pg_url)
        conn.autocommit = True
        conn.cursor().execute(
            "INSERT INTO users (username, hashed_password, role) VALUES (%s, %s, %s)",
            (username, hashed, "admin"),
        )
        conn.close()
    else:
        import sqlite3

        with sqlite3.connect(TEST_DB) as conn:
            conn.execute(
                "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
                (username, hashed, "admin"),
            )
            conn.commit()

    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]
