import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def meaningful_text(cls, value, info):
        if info.field_name in {"name", "subject", "title", "description"} and isinstance(value, str):
            if not value.strip():
                raise ValueError("Поле не может состоять только из пробелов")
            return value.strip()
        return value


class Login(Payload):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Укажите корректный email")
        return value


class Register(Login):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Имя не может быть пустым")
        return value.strip()


class StudentCreate(Register):
    subject: str = Field(min_length=1, max_length=100)
    level: str = Field(default="", max_length=100)
    goal: str = Field(default="", max_length=300)
    contact: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=5000)


class StudentEdit(Payload):
    name: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=100)
    level: str = Field(default="", max_length=100)
    goal: str = Field(default="", max_length=300)
    contact: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=5000)
    archived: bool = False


class LessonWrite(Payload):
    student_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    starts_at: AwareDatetime
    duration_minutes: int = Field(default=60, ge=15, le=240)
    price: int = Field(default=0, ge=0, le=100_000)
    status: Literal["scheduled", "completed", "cancelled"] = "scheduled"
    notes: str = Field(default="", max_length=5000)


class HomeworkEdit(Payload):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    due_at: AwareDatetime


class HomeworkWrite(HomeworkEdit):
    student_id: int = Field(gt=0)
    lesson_id: int | None = Field(default=None, gt=0)


class Submission(Payload):
    answer: str = Field(min_length=1, max_length=10000)


class Review(Payload):
    feedback: str = Field(default="", max_length=5000)
    grade: int = Field(ge=0, le=100)


class PasswordChange(Payload):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def as_utc(value: datetime):
    return value.astimezone(timezone.utc).replace(tzinfo=None)
