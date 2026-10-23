"""Начальная схема. Снимок независим от будущих изменений ORM-моделей."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('teacher', 'student')", name="valid_role"))
    op.create_table("login_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])
    op.create_table("students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("level", sa.String(100), nullable=False),
        sa.Column("goal", sa.String(300), nullable=False),
        sa.Column("contact", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False))
    op.create_index("ix_students_teacher_id", "students", ["teacher_id"])
    op.create_table("lessons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="positive_duration"),
        sa.CheckConstraint("price >= 0", name="nonnegative_price"),
        sa.CheckConstraint("status IN ('scheduled','completed','cancelled')", name="valid_lesson_status"))
    op.create_index("ix_lessons_student_id", "lessons", ["student_id"])
    op.create_index("ix_lessons_teacher_time", "lessons", ["teacher_id", "starts_at"])
    op.create_table("homework",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('assigned','submitted','reviewed')", name="valid_homework_status"),
        sa.CheckConstraint("grade IS NULL OR (grade >= 0 AND grade <= 100)", name="valid_grade"))
    op.create_index("ix_homework_teacher_id", "homework", ["teacher_id"])
    op.create_index("ix_homework_student_id", "homework", ["student_id"])


def downgrade():
    for table in ("homework", "lessons", "students", "login_sessions", "users"):
        op.drop_table(table)
