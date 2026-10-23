from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Homework, Lesson, Student, User
from app.schemas import HomeworkWrite, LessonWrite, Review, StudentCreate, StudentEdit, Submission, as_utc
from app.security import current_user, hash_password, teacher_only
from app.services import homework_json, lesson_json, owned_record, owned_student, save_lesson, scoped_query, student_json

router = APIRouter(prefix="/api", tags=["Учебный кабинет"])


@router.get("/students")
def students(user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Student).order_by(Student.id)
    query = query.where(Student.teacher_id == user.id) if user.role == "teacher" else query.where(Student.user_id == user.id)
    return [student_json(db, s, user.role == "teacher") for s in db.scalars(query)]


@router.post("/students", status_code=201)
def create_student(data: StudentCreate, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(409, "Этот email уже используется")
    user = User(name=data.name, email=data.email, password_hash=hash_password(data.password), role="student")
    db.add(user)
    db.flush()
    student = Student(teacher_id=teacher.id, user_id=user.id,
                      **data.model_dump(exclude={"name", "email", "password"}))
    db.add(student)
    db.commit()
    return student_json(db, student)


@router.put("/students/{student_id}")
def edit_student(student_id: int, data: StudentEdit, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    student = owned_student(db, teacher, student_id)
    db.get(User, student.user_id).name = data.name.strip()
    for key, value in data.model_dump(exclude={"name"}).items():
        setattr(student, key, value)
    db.commit()
    return student_json(db, student)


@router.get("/lessons")
def lessons(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [lesson_json(db, lesson, user.role == "teacher") for lesson in db.scalars(scoped_query(Lesson, user).order_by(Lesson.starts_at))]


@router.post("/lessons", status_code=201)
def create_lesson(data: LessonWrite, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    return save_lesson(db, teacher, data)


@router.put("/lessons/{lesson_id}")
def edit_lesson(lesson_id: int, data: LessonWrite, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    return save_lesson(db, teacher, data, lesson_id)


@router.get("/homework")
def homework(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [homework_json(db, hw) for hw in db.scalars(scoped_query(Homework, user).order_by(Homework.due_at))]


@router.post("/homework", status_code=201)
def create_homework(data: HomeworkWrite, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    student = owned_student(db, teacher, data.student_id)
    if student.archived:
        raise HTTPException(409, "Сначала восстановите ученика из архива")
    if data.lesson_id:
        lesson = owned_record(db, Lesson, teacher, data.lesson_id)
        if lesson.student_id != data.student_id:
            raise HTTPException(400, "Занятие принадлежит другому ученику")
    hw = Homework(teacher_id=teacher.id, **data.model_dump(exclude={"due_at"}), due_at=as_utc(data.due_at))
    db.add(hw)
    db.commit()
    return homework_json(db, hw)


@router.post("/homework/{homework_id}/submit")
def submit_homework(homework_id: int, data: Submission, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "student":
        raise HTTPException(403, "Ответ отправляет ученик")
    hw = owned_record(db, Homework, user, homework_id)
    if hw.status == "reviewed":
        raise HTTPException(409, "Задание уже проверено")
    if not data.answer.strip():
        raise HTTPException(400, "Напишите ответ")
    hw.answer, hw.status = data.answer.strip(), "submitted"
    db.commit()
    return homework_json(db, hw)


@router.post("/homework/{homework_id}/review")
def review_homework(homework_id: int, data: Review, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    hw = owned_record(db, Homework, teacher, homework_id)
    if hw.status == "assigned":
        raise HTTPException(409, "Ученик ещё не отправил ответ")
    hw.grade, hw.feedback, hw.status = data.grade, data.feedback, "reviewed"
    db.commit()
    return homework_json(db, hw)
