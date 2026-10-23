"""python -m app.seed — добавить вымышленные данные, не удаляя существующие."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import DATABASE_URL, ROOT
from app.database import build_engine, migrate, session_factory
from app.models import Homework, Lesson, Student, User
from app.schemas import as_utc
from app.security import hash_password


def main():
    (ROOT / "data").mkdir(exist_ok=True)
    engine = build_engine(DATABASE_URL)
    migrate(engine)
    with session_factory(engine)() as db:
        if db.scalar(select(User.id).where(User.email == "teacher@tutordesk.local")):
            print("Демо уже создано. Существующие данные сохранены.")
            return
        teacher = User(name="Тарас", email="teacher@tutordesk.local", role="teacher", password_hash=hash_password("TutorDemo123!"))
        db.add(teacher)
        db.flush()
        examples = [
            ("Аня Смирнова", "anna@tutordesk.local", "Математика", "11 класс · ЕГЭ", "85+ баллов на ЕГЭ", "Производная и экстремумы"),
            ("Миша Волков", "misha@tutordesk.local", "Информатика", "10 класс · ЕГЭ", "Уверенно писать на Python", "Циклы и списки в Python"),
            ("Соня Орлова", "sonya@tutordesk.local", "Математика", "9 класс · ОГЭ", "Пятёрка на ОГЭ", "Квадратные уравнения"),
            ("Артём Соколов", "artem@tutordesk.local", "Информатика", "11 класс · ЕГЭ", "90+ баллов на ЕГЭ", "Два указателя и строки"),
        ]
        now = datetime.now(ZoneInfo("Europe/Moscow"))
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for i, (name, email, subject, level, goal, topic) in enumerate(examples):
            account = User(name=name, email=email, role="student", password_hash=hash_password("Student123!"))
            db.add(account)
            db.flush()
            student = Student(teacher_id=teacher.id, user_id=account.id, subject=subject, level=level,
                              goal=goal, notes="Демонстрационная карточка. Все данные вымышлены.")
            db.add(student)
            db.flush()
            upcoming = today + timedelta(days=i // 3, hours=14 + (i % 3) * 2)
            lesson = Lesson(teacher_id=teacher.id, student_id=student.id, title=topic,
                            starts_at=as_utc(upcoming), ends_at=as_utc(upcoming + timedelta(hours=1)),
                            price=1800 if subject == "Математика" else 2000, status="scheduled", notes="Разобрать ошибки прошлого занятия")
            db.add(lesson)
            db.flush()
            for week in range(1, 4):
                past = upcoming - timedelta(days=7 * week)
                db.add(Lesson(teacher_id=teacher.id, student_id=student.id, title="Практика и разбор задач",
                              starts_at=as_utc(past), ends_at=as_utc(past + timedelta(hours=1)), price=1800, status="completed"))
            db.add(Homework(teacher_id=teacher.id, student_id=student.id, lesson_id=lesson.id, title=topic,
                            description="Решите 5 задач по теме занятия. Запишите ход решения и отметьте вопросы, которые хотите обсудить.",
                            due_at=as_utc(today + timedelta(days=1 + i, hours=20)),
                            status="submitted" if i == 0 else "assigned",
                            answer="Решила задания 1–4. В пятом не уверена в выборе интервала." if i == 0 else ""))
            db.add(Homework(teacher_id=teacher.id, student_id=student.id, title="Повторение прошлой темы",
                            description="Короткая самостоятельная работа", due_at=as_utc(today - timedelta(days=3)),
                            status="reviewed", answer="Решение отправлено", feedback="Хорошая работа! Обрати внимание на оформление.", grade=80 + i * 5))
        db.commit()
    engine.dispose()
    print("Демо готово: teacher@tutordesk.local / TutorDemo123!")
    print("Ученик: anna@tutordesk.local / Student123!")


if __name__ == "__main__":
    main()
