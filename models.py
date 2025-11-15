from pydantic import BaseModel
from typing import Optional

class Movietop(BaseModel):
    name: str
    id: int
    cost: int
    director: str
    name_en: Optional[str] = None  # Опционально, для английского названия
    year: Optional[int] = None     # Опционально, для года
    is_classic: Optional[bool] = None  # Опционально, для классики





