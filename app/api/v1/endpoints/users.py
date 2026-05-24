import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import role_guard
from app.api.v1.endpoints.auth import _supabase_request
from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/users", tags=["Usuarios"])
AdminOnly = Depends(role_guard({"dueno", "dueño", "administrador"}))


class UserPayload(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    apellido: str | None = None
    email: str = Field(min_length=5, max_length=180)
    telefono: str | None = None
    rol_id: UUID
    activo: bool = True
    password: str | None = Field(default=None, min_length=6)


@router.get("", dependencies=[AdminOnly])
def list_users(db: Session = Depends(get_db)):
    return db.execute(
        text(
            """
            SELECT u.id, u.nombre, u.apellido, u.email, u.telefono, u.activo,
                   u.rol_id, r.nombre AS rol, u.created_at, u.updated_at
            FROM usuarios u
            LEFT JOIN roles r ON r.id = u.rol_id
            ORDER BY u.nombre, u.apellido
            """
        )
    ).mappings().all()


@router.get("/roles", dependencies=[AdminOnly])
def list_roles(db: Session = Depends(get_db)):
    return db.execute(text("SELECT id, nombre FROM roles WHERE activo = true ORDER BY nombre")).mappings().all()


@router.post("", dependencies=[AdminOnly])
def create_user(payload: UserPayload, db: Session = Depends(get_db)):
    settings = get_settings()
    auth_user_id = None
    if settings.supabase_service_role_key:
        if not payload.password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contrasena es obligatoria para crear cuenta Auth")
        created = _supabase_request(
            "/auth/v1/admin/users",
            {"email": payload.email, "password": payload.password, "email_confirm": True},
            settings.supabase_service_role_key,
        )
        auth_user_id = created.get("id")
    row = db.execute(
        text(
            """
            INSERT INTO usuarios (auth_user_id, nombre, apellido, email, telefono, rol_id, activo)
            VALUES (CAST(:auth_user_id AS uuid), :nombre, :apellido, :email, :telefono, :rol_id, :activo)
            RETURNING id
            """
        ),
        {
            "auth_user_id": auth_user_id,
            "nombre": payload.nombre,
            "apellido": payload.apellido,
            "email": payload.email,
            "telefono": payload.telefono,
            "rol_id": str(payload.rol_id),
            "activo": payload.activo,
        },
    ).mappings().one()
    db.commit()
    return {"id": row["id"]}


@router.put("/{user_id}", dependencies=[AdminOnly])
def update_user(user_id: UUID, payload: UserPayload, db: Session = Depends(get_db)):
    db.execute(
        text(
            """
            UPDATE usuarios
            SET nombre = :nombre, apellido = :apellido, email = :email, telefono = :telefono,
                rol_id = :rol_id, activo = :activo, updated_at = now()
            WHERE id = :id
            """
        ),
        {
            "id": str(user_id),
            "nombre": payload.nombre,
            "apellido": payload.apellido,
            "email": payload.email,
            "telefono": payload.telefono,
            "rol_id": str(payload.rol_id),
            "activo": payload.activo,
        },
    )
    db.commit()
    return {"id": user_id, "activo": payload.activo}


@router.patch("/{user_id}/status", dependencies=[AdminOnly])
def update_user_status(user_id: UUID, activo: bool, db: Session = Depends(get_db)):
    db.execute(text("UPDATE usuarios SET activo = :activo, updated_at = now() WHERE id = :id"), {"id": str(user_id), "activo": activo})
    db.commit()
    return {"id": user_id, "activo": activo}
