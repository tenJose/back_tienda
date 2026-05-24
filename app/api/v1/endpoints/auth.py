import requests
from requests import RequestException
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["Autenticacion"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str


def _supabase_request(path: str, payload: dict, key: str) -> dict:
    settings = get_settings()
    try:
        response = requests.post(
            f"{settings.supabase_url.rstrip('/')}{path}",
            json=payload,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
    except RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo conectar con Supabase Auth",
        ) from exc

    if response.status_code >= 400:
        detail = "Credenciales invalidas"
        try:
            body = response.json()
            detail = body.get("msg") or body.get("message") or body.get("error_description") or detail
        except ValueError:
            pass
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
    return response.json()


@router.post("/login")
def login(payload: LoginRequest):
    settings = get_settings()
    return _supabase_request(
        "/auth/v1/token?grant_type=password",
        {"email": payload.email, "password": payload.password},
        settings.supabase_publishable_key,
    )


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    if not user.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no identificado")
    return user
