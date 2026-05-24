from collections.abc import Callable
import json
import unicodedata

import jwt
import requests
from requests import RequestException
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


def _normalize_role(role: str | None) -> str | None:
    if not role:
        return None
    normalized = unicodedata.normalize("NFKD", role.strip().lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    role_aliases = {
        "owner": "dueno",
        "admin": "administrador",
        "manager": "encargado",
        "cashier": "cajero",
        "helper": "ayudante",
    }
    return role_aliases.get(normalized, normalized)


def _get_jwks() -> dict:
    settings = get_settings()
    jwks_url = settings.supabase_jwks_url or f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url, timeout=8)
    except RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo validar el token con Supabase",
        ) from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No se pudo obtener JWKS")
    return response.json()


def _get_supabase_user_claims(token: str) -> dict:
    settings = get_settings()
    try:
        response = requests.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.supabase_publishable_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=8,
        )
    except RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo validar el token con Supabase",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no autorizado")

    user = response.json()
    return {
        "sub": user.get("id"),
        "email": user.get("email"),
        "role": user.get("role"),
        "app_metadata": user.get("app_metadata") if isinstance(user.get("app_metadata"), dict) else {},
        "user_metadata": user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {},
    }


def _decode_supabase_jwt(token: str) -> dict:
    try:
        headers = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido") from exc

    kid = headers.get("kid")
    if not kid:
        return _get_supabase_user_claims(token)

    jwk = next((key for key in _get_jwks().get("keys", []) if key.get("kid") == kid), None)
    if not jwk:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No se encontro llave publica para token")

    try:
        key = jwt.PyJWK.from_json(json.dumps(jwk)).key
        return jwt.decode(
            token,
            key=key,
            algorithms=[jwk.get("alg", "RS256")],
            audience=get_settings().supabase_jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no autorizado") from exc


def _role_from_claims(claims: dict) -> str | None:
    app_metadata = claims.get("app_metadata") if isinstance(claims.get("app_metadata"), dict) else {}
    user_metadata = claims.get("user_metadata") if isinstance(claims.get("user_metadata"), dict) else {}
    return _normalize_role(app_metadata.get("role") or user_metadata.get("role"))


def _user_from_db(db: Session, auth_user_id: str) -> dict | None:
    try:
        row = db.execute(
            text(
                """
                SELECT u.id, u.auth_user_id, u.nombre, u.apellido, u.email, u.telefono,
                       u.activo, r.nombre AS rol,
                       COALESCE(array_agg(p.clave) FILTER (WHERE p.clave IS NOT NULL), '{}') AS permisos
                FROM usuarios u
                LEFT JOIN roles r ON r.id = u.rol_id
                LEFT JOIN rol_permisos rp ON rp.rol_id = r.id
                LEFT JOIN permisos p ON p.id = rp.permiso_id
                WHERE u.auth_user_id = CAST(:auth_user_id AS uuid)
                  AND u.activo = true
                GROUP BY u.id, r.nombre
                LIMIT 1
                """
            ),
            {"auth_user_id": auth_user_id},
        ).mappings().one_or_none()
    except (SQLAlchemyError, Exception):
        try:
            db.rollback()
        except Exception:
            pass
        return _user_from_supabase_rest(auth_user_id)
    if not row:
        return None
    user = dict(row)
    user["rol"] = _normalize_role(user.get("rol"))
    return user


def _user_from_supabase_rest(auth_user_id: str) -> dict | None:
    settings = get_settings()
    if not settings.supabase_service_role_key:
        return None

    try:
        response = requests.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/usuarios",
            params={
                "select": "id,auth_user_id,nombre,apellido,email,telefono,activo,roles(nombre)",
                "auth_user_id": f"eq.{auth_user_id}",
                "activo": "eq.true",
                "limit": "1",
            },
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
            },
            timeout=10,
        )
    except RequestException:
        return None
    if response.status_code >= 400:
        return None

    rows = response.json()
    if not rows:
        return None

    row = rows[0]
    role = row.get("roles", {}).get("nombre") if isinstance(row.get("roles"), dict) else None
    return {
        "id": row.get("id"),
        "auth_user_id": row.get("auth_user_id"),
        "nombre": row.get("nombre"),
        "apellido": row.get("apellido"),
        "email": row.get("email"),
        "telefono": row.get("telefono"),
        "activo": row.get("activo"),
        "rol": _normalize_role(role),
        "permisos": [],
    }


def _role_from_db(db: Session, auth_user_id: str) -> str | None:
    user = _user_from_db(db, auth_user_id)
    return user.get("rol") if user else None


def _user_from_claims(claims: dict) -> dict:
    app_metadata = claims.get("app_metadata") if isinstance(claims.get("app_metadata"), dict) else {}
    user_metadata = claims.get("user_metadata") if isinstance(claims.get("user_metadata"), dict) else {}
    full_name = user_metadata.get("full_name") or user_metadata.get("name") or ""
    name_parts = full_name.split(" ", 1)

    return {
        "id": claims.get("sub"),
        "auth_user_id": claims.get("sub"),
        "nombre": user_metadata.get("nombre") or (name_parts[0] if name_parts else ""),
        "apellido": user_metadata.get("apellido") or (name_parts[1] if len(name_parts) > 1 else ""),
        "email": claims.get("email") or user_metadata.get("email"),
        "telefono": user_metadata.get("telefono") or user_metadata.get("phone"),
        "activo": True,
        "rol": _role_from_claims(claims) or _normalize_role(app_metadata.get("role")) or "ayudante",
        "permisos": [],
    }


def get_current_role(
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
    x_role: str | None = Header(default=None, alias="X-Role"),
) -> str | None:
    settings = get_settings()

    if token:
        claims = _decode_supabase_jwt(token)
        auth_user_id = claims.get("sub")
        role = _role_from_db(db, auth_user_id) if auth_user_id else None
        if not role:
            role = _role_from_claims(claims)
        if role:
            return role

    normalized_header_role = _normalize_role(x_role)
    if normalized_header_role and settings.allow_role_header_fallback:
        return normalized_header_role

    if settings.require_auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Debes enviar token Bearer de Supabase")

    if settings.require_role_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta header X-Role")

    return normalized_header_role


def get_current_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
    x_role: str | None = Header(default=None, alias="X-Role"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> dict:
    settings = get_settings()

    if token:
        claims = _decode_supabase_jwt(token)
        auth_user_id = claims.get("sub")
        if auth_user_id:
            user = _user_from_db(db, auth_user_id)
            if user:
                return user
            return _user_from_claims(claims)

    normalized_header_role = _normalize_role(x_role)
    if normalized_header_role and settings.allow_role_header_fallback:
        return {"id": x_user_id, "rol": normalized_header_role, "permisos": []}

    if settings.require_auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Debes enviar token Bearer de Supabase")

    return {"id": x_user_id, "rol": normalized_header_role, "permisos": []}


def role_guard(allowed_roles: set[str]) -> Callable[[str | None], str | None]:
    allowed = {_normalize_role(role) for role in allowed_roles}

    def dependency(role: str | None = Depends(get_current_role)) -> str | None:
        if not role:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No se pudo resolver rol")
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Rol '{role}' sin permisos")
        return role

    return dependency


CanViewProducts = Depends(role_guard({"dueno", "administrador", "encargado", "cajero", "ayudante"}))
CanManageProducts = Depends(role_guard({"dueno", "administrador", "encargado"}))
