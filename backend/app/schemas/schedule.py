"""Collector takvimi API semalari."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    label: str
    job_name: str
    interval_minutes: int
    minimum_interval_minutes: int
    enabled: bool
    next_run_at: datetime | None
    last_enqueued_at: datetime | None
    updated_at: datetime


class ScheduleUpdate(BaseModel):
    interval_minutes: int | None = Field(None, ge=1, le=43_200)
    enabled: bool | None = None

    @model_validator(mode="after")
    def at_least_one_change(self):
        if self.interval_minutes is None and self.enabled is None:
            raise ValueError("En az bir alan guncellenmeli")
        return self


class ScheduleRunOut(BaseModel):
    name: str
    enqueued: bool
    job_id: str
    enqueued_at: datetime
