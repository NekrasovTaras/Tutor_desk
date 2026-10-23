from datetime import timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Homework, Lesson, Student, User
from app.schemas import as_utc


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat()


def owned_student(db, user, student_id):
    query = select(Student).where(Student.id == student_id)
    query = query.where(Student.teacher_id == user.id) if user.role == "teacher" else query.where(Student.user_id == user.id)
    student = db.scalar(query)
    if student is None:
        raise HTTPException(404, "Ученик не найден")
    return student


def student_json(db, student, private=True):
    user = db.get(User, student.user_id)
    result = {"id": student.id, "name": user.name, "email": user.email,
              "subject": student.subject, "level": student.level, "goal": student.goal,
              "archived": student.archived}
    if private:
        result.update(contact=student.contact, notes=student.notes)
    return result


def lesson_json(db, lesson, private=True):
    student = db.get(Student, lesson.student_id)
    user = db.get(User, student.user_id)
    result = {"id": lesson.id, "student_id": student.id, "student_name": user.name,
              "subject": student.subject, "title": lesson.title, "starts_at": iso(lesson.starts_at),
              "ends_at": iso(lesson.ends_at), "duration_minutes": int((lesson.ends_at - lesson.starts_at).total_seconds() / 60),
              "status": lesson.status, "price": lesson.price}
    if private:
        result["notes"] = lesson.notes
    return result


def homework_json(db, hw):
    student = db.get(Student, hw.student_id)
    return {"id": hw.id, "student_id": hw.student_id, "student_name": db.get(User, student.user_id).name,
            "lesson_id": hw.lesson_id, "title": hw.title, "description": hw.description,
            "due_at": iso(hw.due_at), "status": hw.status, "answer": hw.answer,
            "feedback": hw.feedback, "grade": hw.grade}


def scoped_query(model, user):
    query = select(model)
    if user.role == "teacher":
        return query.where(model.teacher_id == user.id)
    return query.where(model.student_id.in_(select(Student.id).where(Student.user_id == user.id)))


def owned_record(db, model, user, record_id):
    record = db.scalar(scoped_query(model, user).where(model.id == record_id).with_for_update())
    if record is None:
        raise HTTPException(404, "Запись не найдена")
    return record


def save_lesson(db, teacher, data, lesson_id=None):
    # PostgreSQL: все изменения расписания одного преподавателя сериализуются
    # блокировкой его строки. В SQLite блокировка уже взята в get_db.
    db.execute(select(User.id).where(User.id == teacher.id).with_for_update()).first()
    lesson = owned_record(db, Lesson, teacher, lesson_id) if lesson_id else None
    student = owned_student(db, teacher, data.student_id)
    if student.archived and (lesson is None or data.status == "scheduled"):
        raise HTTPException(409, "Сначала восстановите ученика из архива")
    start = as_utc(data.starts_at)
    end = start + timedelta(minutes=data.duration_minutes)
    if data.status != "cancelled":
        query = select(Lesson.id).where(Lesson.teacher_id == teacher.id, Lesson.status != "cancelled",
                                        Lesson.starts_at < end, Lesson.ends_at > start)
        if lesson:
            query = query.where(Lesson.id != lesson.id)
        if db.scalar(query) is not None:
            raise HTTPException(409, "На это время уже назначено занятие. Выберите другой интервал.")
    if lesson is None:
        lesson = Lesson(teacher_id=teacher.id)
        db.add(lesson)
    elif lesson.student_id != student.id:
        if db.scalar(select(Homework.id).where(Homework.lesson_id == lesson.id)) is not None:
            raise HTTPException(409, "У занятия есть ДЗ: менять ученика нельзя")
    for key in ("student_id", "title", "price", "status", "notes"):
        setattr(lesson, key, getattr(data, key))
    lesson.starts_at, lesson.ends_at = start, end
    db.commit()
    return lesson_json(db, lesson)
