"""Veri toplama takvimi ve yonetim audit kayitlari."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CollectorSchedule(Base):
    __tablename__ = "collector_schedule"
    __table_args__ = (
        CheckConstraint(
            "interval_minutes >= minimum_interval_minutes",
            name="ck_schedule_interval_minimum",
        ),
        CheckConstraint("minimum_interval_minutes >= 1", name="ck_schedule_minimum_positive"),
    )

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    job_name: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_enqueued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScheduleAuditLog(Base):
    __tablename__ = "schedule_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    schedule_name: Mapped[str] = mapped_column(
        String(64), ForeignKey("collector_schedule.name", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    old_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    new_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
