import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def signup(client, email="teacher@example.com", name="Тарас"):
    result = client.post("/api/auth/register", json={"email": email, "name": name, "password": "Password123!"})
    assert result.status_code == 201, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result.json()


def login(client, email, password="Password123!"):
    result = client.post("/api/auth/login", json={"email": email, "password": password})
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result.json()


def add_student(client, email="student@example.com"):
    response = client.post("/api/students", json={"name": "Анна", "email": email, "password": "Password123!",
                         "subject": "Математика", "level": "11 класс", "notes": "Личная заметка", "contact": "Личный контакт"})
    assert response.status_code == 201, response.text
    return response.json()


def lesson(student_id, **overrides):
    return {"student_id": student_id, "title": "Производные", "starts_at": "2027-01-15T15:00:00+03:00",
            "duration_minutes": 60, "price": 1800, "notes": "Закрытая заметка", **overrides}


def homework(student_id, **overrides):
    return {"student_id": student_id, "title": "Практика", "description": "Решить пять задач",
            "due_at": "2027-01-20T20:00:00+03:00", **overrides}


@pytest.fixture
def teacher(client):
    signup(client)
    return client


@pytest.fixture
def student(teacher):
    return add_student(teacher)
