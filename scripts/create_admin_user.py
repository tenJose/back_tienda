import json
import os
import sys
from argparse import ArgumentParser
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text


DEFAULT_NAME = "Administrador"


def load_env(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def supabase_request(method: str, path: str, payload: dict | None = None) -> dict:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{supabase_url}{path}",
        data=data,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:  # nosec B310 - URL comes from local env.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"Supabase Auth error {exc.code}: {detail}") from exc


def supabase_rest_request(method: str, path: str, payload: dict | list[dict] | None = None) -> dict | list[dict]:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{supabase_url}/rest/v1{path}",
        data=data,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:  # nosec B310 - URL comes from local env.
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"Supabase REST error {exc.code}: {detail}") from exc


def find_auth_user_id(email: str) -> str | None:
    page = 1
    while True:
        result = supabase_request("GET", f"/auth/v1/admin/users?page={page}&per_page=100")
        users = result.get("users", result if isinstance(result, list) else [])
        for user in users:
            if str(user.get("email", "")).lower() == email.lower():
                return user.get("id")
        if len(users) < 100:
            return None
        page += 1


def create_auth_user(email: str, password: str) -> str:
    existing_id = find_auth_user_id(email)
    if existing_id:
        return existing_id
    created = supabase_request(
        "POST",
        "/auth/v1/admin/users",
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"role": "administrador"},
            "app_metadata": {"role": "administrador"},
        },
    )
    return created["id"]


def upsert_local_user(auth_user_id: str, email: str, name: str) -> str:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, connect_args={"connect_timeout": 10})
    with engine.begin() as conn:
        role_id = conn.execute(
            text(
                """
                INSERT INTO roles (nombre, descripcion, activo)
                VALUES ('administrador', 'Administrador del sistema', true)
                ON CONFLICT (nombre)
                DO UPDATE SET activo = true
                RETURNING id
                """
            )
        ).scalar_one()
        user_id = conn.execute(
            text(
                """
                INSERT INTO usuarios (auth_user_id, nombre, apellido, email, telefono, rol_id, activo)
                VALUES (CAST(:auth_user_id AS uuid), :nombre, NULL, :email, NULL, :rol_id, true)
                ON CONFLICT (email)
                DO UPDATE SET
                    auth_user_id = EXCLUDED.auth_user_id,
                    nombre = EXCLUDED.nombre,
                    rol_id = EXCLUDED.rol_id,
                    activo = true,
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                "auth_user_id": auth_user_id,
                "nombre": name,
                "email": email,
                "rol_id": str(role_id),
            },
        ).scalar_one()
    return str(user_id)


def upsert_local_user_rest(auth_user_id: str, email: str, name: str) -> str:
    roles = supabase_rest_request("GET", "/roles?select=id&nombre=eq.administrador")
    if not roles:
        roles = supabase_rest_request(
            "POST",
            "/roles",
            {"nombre": "administrador", "descripcion": "Administrador del sistema", "activo": True},
        )
    role_id = roles[0]["id"]

    users = supabase_rest_request(
        "POST",
        "/usuarios?on_conflict=email",
        {
            "auth_user_id": auth_user_id,
            "nombre": name,
            "apellido": None,
            "email": email,
            "telefono": None,
            "rol_id": role_id,
            "activo": True,
        },
    )
    return users[0]["id"]


def main() -> int:
    parser = ArgumentParser(description="Create or synchronize an administrator user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default=DEFAULT_NAME)
    args = parser.parse_args()

    load_env(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

    required = ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    auth_user_id = create_auth_user(args.email, args.password)
    try:
        local_user_id = upsert_local_user(auth_user_id, args.email, args.name)
    except Exception as exc:
        print(f"Database connection failed, using Supabase REST fallback: {exc}", file=sys.stderr)
        local_user_id = upsert_local_user_rest(auth_user_id, args.email, args.name)
    print(f"Admin user ready: email={args.email} auth_user_id={auth_user_id} usuario_id={local_user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
