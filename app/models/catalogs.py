import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text())
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departamentos.id"))
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    prefijo_codigo: Mapped[str | None] = mapped_column(String(10))
    descripcion: Mapped[str | None] = mapped_column(Text())
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Subcategoria(Base):
    __tablename__ = "subcategorias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categorias.id"))
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text())
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Marca(Base):
    __tablename__ = "marcas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UnidadMedida(Base):
    __tablename__ = "unidades_medida"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    abreviatura: Mapped[str] = mapped_column(String(20), nullable=False)
    permite_decimal: Mapped[bool] = mapped_column(Boolean, default=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    contacto: Mapped[str | None] = mapped_column(String(120))
    telefono: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(180))
    direccion: Mapped[str | None] = mapped_column(Text())
    rfc: Mapped[str | None] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Sucursal(Base):
    __tablename__ = "sucursales"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    direccion: Mapped[str | None] = mapped_column(Text())
    telefono: Mapped[str | None] = mapped_column(String(30))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
