import pytest

from conftest import homework, lesson, login, signup


def changes(**overrides):
    return {"title": "Производные", "description": "Решить задачи 1–5",
            "due_at": "2027-01-22T18:30:00+03:00", **overrides}


def test_edit_preserves_assignment_and_is_visible_to_student(teacher, student):
    linked = teacher.post("/api/lessons", json=lesson(student["id"])).json()
    original = teacher.post("/api/homework", json=homework(student["id"], lesson_id=linked["id"])).json()
    response = teacher.put(f"/api/homework/{original['id']}", json=changes())
    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Производные"
    assert updated["description"] == "Решить задачи 1–5"
    assert updated["due_at"] == "2027-01-22T15:30:00+00:00"
    for key in ("id", "student_id", "lesson_id", "status", "answer", "grade", "feedback"):
        assert updated[key] == original[key]
    login(teacher, "student@example.com")
    assert teacher.get("/api/homework").json() == [updated]


@pytest.mark.parametrize("reviewed", [False, True])
def test_cannot_change_assignment_after_submission(teacher, student, reviewed):
    hw = teacher.post("/api/homework", json=homework(student["id"])).json()
    login(teacher, "student@example.com")
    teacher.post(f"/api/homework/{hw['id']}/submit", json={"answer": "x = 5"})
    login(teacher, "teacher@example.com")
    if reviewed:
        teacher.post(f"/api/homework/{hw['id']}/review", json={"grade": 90, "feedback": "Верно"})
    before = teacher.get("/api/homework").json()
    assert teacher.put(f"/api/homework/{hw['id']}", json=changes()).status_code == 409
    assert teacher.get("/api/homework").json() == before


def test_only_owning_teacher_can_edit(teacher, student):
    hw = teacher.post("/api/homework", json=homework(student["id"])).json()
    login(teacher, "student@example.com")
    assert teacher.put(f"/api/homework/{hw['id']}", json=changes()).status_code == 403
    signup(teacher, "other@example.com")
    assert teacher.put(f"/api/homework/{hw['id']}", json=changes()).status_code == 404
    login(teacher, "teacher@example.com")
    assert teacher.get("/api/homework").json() == [hw]
    assert teacher.put("/api/homework/999999", json=changes()).status_code == 404


@pytest.mark.parametrize("invalid", [
    {"title": "   "}, {"description": "  "}, {"due_at": "2027-01-22T18:30:00"},
    {"student_id": 999}, {"lesson_id": None}, {"status": "reviewed"},
])
def test_invalid_edit_leaves_homework_unchanged(teacher, student, invalid):
    hw = teacher.post("/api/homework", json=homework(student["id"])).json()
    assert teacher.put(f"/api/homework/{hw['id']}", json=changes(**invalid)).status_code == 422
    assert teacher.get("/api/homework").json() == [hw]
