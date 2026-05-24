import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    apellido: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(180))
    telefono: Mapped[str | None] = mapped_column(String(40))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    rol_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("roles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
