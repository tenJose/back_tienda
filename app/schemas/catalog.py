from uuid import UUID

from pydantic import BaseModel


class OptionItem(BaseModel):
    id: UUID
    nombre: str
