from pydantic import BaseModel
from datetime import datetime


class Heatbeat(BaseModel):
  host: str
  component: str
  sent_at: datetime

