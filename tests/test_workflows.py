from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import LoginSession, User, utcnow
from conftest import add_student, homework, lesson, login, signup


def test_registration_cookie_and_logout(client):
    signup(client, "  TARAS@example.com ")
    me = client.get("/api/auth/me")
    assert me.json()["user"]["email"] == "taras@example.com"
    assert me.json()["user"]["role"] == "teacher"
    assert "password_hash" not in me.text
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_and_duplicate_email(teacher):
    assert teacher.post("/api/auth/login", json={"email": "teacher@example.com", "password": "Incorrect123"}).status_code == 401
    assert teacher.post("/api/auth/register", json={"email": "teacher@example.com", "password": "Password123!", "name": "Другой"}).status_code == 409


def test_validation_does_not_echo_password(client):
    response = client.post("/api/auth/register", json={"email": "wrong", "password": "secret", "name": ""})
    assert response.status_code == 422
    assert "secret" not in response.text


def test_csrf_and_origin(teacher):
    csrf = teacher.headers.pop("X-CSRF-Token")
    assert teacher.post("/api/auth/logout").status_code == 403
    teacher.headers["X-CSRF-Token"] = csrf
    assert teacher.post("/api/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
    assert teacher.get("/api/auth/me").status_code == 200


def test_student_access_and_private_notes(teacher, student):
    teacher.post("/api/lessons", json=lesson(student["id"]))
    login(teacher, "student@example.com")
    profiles = teacher.get("/api/students").json()
    lessons = teacher.get("/api/lessons").json()
    assert len(profiles) == len(lessons) == 1
    assert "notes" not in profiles[0] and "contact" not in profiles[0]
    assert "notes" not in lessons[0]
    assert teacher.post("/api/students", json={"name":"X","email":"x@example.com","password":"Password123!","subject":"Math"}).status_code == 403
    assert teacher.post("/api/lessons", json=lesson(student["id"])).status_code == 403


def test_tenant_isolation(teacher, student):
    l = teacher.post("/api/lessons", json=lesson(student["id"])).json()
    h = teacher.post("/api/homework", json=homework(student["id"])).json()
    signup(teacher, "other@example.com")
    assert teacher.get("/api/students").json() == []
    assert teacher.get("/api/lessons").json() == []
    assert teacher.get("/api/homework").json() == []
    assert teacher.post("/api/lessons", json=lesson(student["id"])).status_code == 404
    assert teacher.put(f"/api/lessons/{l['id']}", json=lesson(student["id"])).status_code == 404
    assert teacher.post(f"/api/homework/{h['id']}/review", json={"grade": 100}).status_code == 404
    assert teacher.put(f"/api/students/{student['id']}", json={"name":"X", "subject":"Math"}).status_code == 404


def test_lesson_overlap_boundary_and_cancel(teacher, student):
    first = teacher.post("/api/lessons", json=lesson(student["id"]))
    assert first.status_code == 201
    assert first.json()["starts_at"] == "2027-01-15T12:00:00+00:00"
    assert teacher.post("/api/lessons", json=lesson(student["id"], starts_at="2027-01-15T15:30:00+03:00")).status_code == 409
    assert teacher.post("/api/lessons", json=lesson(student["id"], starts_at="2027-01-15T16:00:00+03:00")).status_code == 201
    assert teacher.put(f"/api/lessons/{first.json()['id']}", json=lesson(student["id"], status="cancelled")).status_code == 200
    assert teacher.post("/api/lessons", json=lesson(student["id"])).status_code == 201


def test_move_lesson_preserves_old_slot_on_conflict(teacher, student):
    first = teacher.post("/api/lessons", json=lesson(student["id"])).json()
    teacher.post("/api/lessons", json=lesson(student["id"], starts_at="2027-01-15T17:00:00+03:00"))
    conflict = teacher.put(f"/api/lessons/{first['id']}", json=lesson(student["id"], starts_at="2027-01-15T17:15:00+03:00"))
    assert conflict.status_code == 409
    assert teacher.get("/api/lessons").json()[0]["starts_at"] == first["starts_at"]


def test_naive_time_and_negative_price_rejected(teacher, student):
    assert teacher.post("/api/lessons", json=lesson(student["id"], starts_at="2027-01-15T15:00:00")).status_code == 422
    assert teacher.post("/api/lessons", json=lesson(student["id"], price=-1)).status_code == 422
    assert teacher.post("/api/lessons", json=lesson(student["id"], duration_minutes=0)).status_code == 422


def test_concurrent_booking_only_one_succeeds(app, teacher, student):
    cookies = dict(teacher.cookies)
    csrf = teacher.headers["X-CSRF-Token"]
    barrier = Barrier(2)
    def book(_):
        # Приложение уже запущено fixture teacher. Второй lifespan здесь
        # запускал бы миграции параллельно, а не тестировал гонку HTTP-запросов.
        c = TestClient(app)
        try:
            c.cookies.update(cookies)
            barrier.wait(timeout=5)
            return c.post("/api/lessons", json=lesson(student["id"]), headers={"X-CSRF-Token": csrf}).status_code
        finally:
            c.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(book, [0,1]))
    assert sorted(results) == [201,409]
    assert len(teacher.get("/api/lessons").json()) == 1


def test_homework_full_cycle(teacher, student):
    h = teacher.post("/api/homework", json=homework(student["id"])).json()
    assert teacher.post(f"/api/homework/{h['id']}/review", json={"grade":90}).status_code == 409
    login(teacher,"student@example.com")
    assert teacher.post(f"/api/homework/{h['id']}/submit",json={"answer":"   "}).status_code == 400
    answer=teacher.post(f"/api/homework/{h['id']}/submit",json={"answer":"x = 5"})
    assert answer.json()["status"] == "submitted"
    login(teacher,"teacher@example.com")
    review=teacher.post(f"/api/homework/{h['id']}/review",json={"grade":92,"feedback":"Верно!"})
    assert review.json()["status"] == "reviewed"
    login(teacher,"student@example.com")
    assert teacher.get("/api/homework").json()[0]["grade"] == 92
    assert teacher.post(f"/api/homework/{h['id']}/submit",json={"answer":"Другой ответ"}).status_code == 409


def test_student_cannot_read_or_submit_other_homework(teacher, student):
    other = add_student(teacher, "second@example.com")
    hw = teacher.post("/api/homework",json=homework(other["id"])).json()
    login(teacher,"student@example.com")
    assert teacher.get("/api/homework").json() == []
    assert teacher.post(f"/api/homework/{hw['id']}/submit",json={"answer":"hack"}).status_code == 404


def test_linked_homework_must_match_student(teacher, student):
    other = add_student(teacher,"second@example.com")
    l = teacher.post("/api/lessons",json=lesson(student["id"])).json()
    assert teacher.post("/api/homework",json=homework(other["id"],lesson_id=l["id"])).status_code == 400
    assert teacher.post("/api/homework",json=homework(student["id"],lesson_id=l["id"])).status_code == 201
    assert teacher.put(f"/api/lessons/{l['id']}",json=lesson(other["id"])).status_code == 409


def test_archive_preserves_history_and_blocks_new_assignments(teacher, student):
    teacher.post("/api/lessons",json=lesson(student["id"]))
    response=teacher.put(f"/api/students/{student['id']}",json={"name":"Анна","subject":"Математика","archived":True})
    assert response.status_code == 200
    assert len(teacher.get("/api/lessons").json()) == 1
    assert teacher.post("/api/lessons",json=lesson(student["id"],starts_at="2027-02-01T12:00:00+03:00")).status_code == 409
    assert teacher.post("/api/homework",json=homework(student["id"])).status_code == 409


def test_password_change_revokes_all_sessions(app, teacher):
    with TestClient(app) as other:
        login(other,"teacher@example.com")
        assert teacher.post("/api/auth/password",json={"current_password":"Password123!","new_password":"NewPassword123!"}).status_code == 204
        assert teacher.get("/api/auth/me").status_code == 401
        assert other.get("/api/auth/me").status_code == 401
        login(teacher,"teacher@example.com","NewPassword123!")


def test_expired_session_and_password_storage(app, teacher):
    with app.state.sessions() as db:
        user=db.scalar(select(User))
        assert user.password_hash != "Password123!"
        assert user.password_hash.startswith("pbkdf2_sha256$")
        record=db.scalar(select(LoginSession))
        record.expires_at=utcnow()-timedelta(seconds=1)
        db.commit()
    assert teacher.get("/api/auth/me").status_code == 401


def test_data_survives_restart(tmp_path):
    url=f"sqlite:///{tmp_path / 'persistent.db'}"
    with TestClient(create_app(url)) as c:
        signup(c)
        add_student(c)
    with TestClient(create_app(url)) as c:
        login(c,"teacher@example.com")
        assert len(c.get("/api/students").json()) == 1


def test_health_frontend_and_openapi(client):
    assert client.get("/health").json()["status"] == "ok"
    assert "TutorDesk" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert "/api/lessons" in client.get("/openapi.json").json()["paths"]


def test_session_cookie_flags(client):
    response=client.post("/api/auth/register",json={"name":"Тарас","email":"taras@example.com","password":"Password123!"})
    cookie=response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_user_cannot_self_assign_student_role(client):
    response=client.post("/api/auth/register",json={"name":"X","email":"x@example.com","password":"Password123!","role":"student"})
    assert response.status_code == 422


def test_whitespace_only_fields_rejected(teacher, student):
    assert teacher.put(f"/api/students/{student['id']}", json={"name":"   ","subject":"Math"}).status_code == 422
    assert teacher.post("/api/lessons", json=lesson(student["id"],title="   ")).status_code == 422
    assert teacher.post("/api/homework", json=homework(student["id"],description="  ")).status_code == 422
