from datetime import date

from pydantic import BaseModel, ConfigDict


class IndexDailyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    value: float
