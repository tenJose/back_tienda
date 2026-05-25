import os
import sys
from argparse import ArgumentParser
from typing import List

from sqlalchemy import create_engine, text


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


def ensure_role(conn, nombre: str) -> str:
    q = text("SELECT id FROM roles WHERE lower(nombre) = lower(:nombre) LIMIT 1")
    row = conn.execute(q, {"nombre": nombre}).fetchone()
    if row:
        return str(row[0])
    ins = text(
        "INSERT INTO roles (nombre, descripcion, activo) VALUES (:nombre, :descripcion, true) RETURNING id"
    )
    new_id = conn.execute(ins, {"nombre": nombre, "descripcion": nombre}).scalar_one()
    return str(new_id)


def list_roles_and_users(conn):
    roles = conn.execute(text("SELECT id, nombre FROM roles ORDER BY nombre")).fetchall()
    roles = [(str(r[0]), r[1]) for r in roles]
    print("Roles en la BD:")
    for rid, nombre in roles:
        print(f" - {nombre} ({rid})")

    # find administrador and cajero ids if present
    admin_id = None
    cajero_id = None
    for rid, nombre in roles:
        if nombre and nombre.lower() == "administrador":
            admin_id = rid
        if nombre and nombre.lower() == "cajero":
            cajero_id = rid

    if not admin_id:
        print("No existe rol 'administrador'. Se creará si se aplica.")
    if not cajero_id:
        print("No existe rol 'cajero'. Se creará si se aplica.")

    protected = {"administrador", "cajero"}
    other_roles = [r for r in roles if (r[1] or "").lower() not in protected]
    if not other_roles:
        print("No hay roles extra para eliminar.")
        return roles, []

    print("\nRoles que serían eliminados (dry-run):")
    for rid, nombre in other_roles:
        print(f" - {nombre} ({rid})")

    # list users that belong to those roles
    affected_users = []
    for rid, nombre in other_roles:
        users = conn.execute(
            text(
                "SELECT id, nombre, apellido, email FROM usuarios WHERE rol_id = :rid"
            ),
            {"rid": rid},
        ).fetchall()
        if users:
            print(f"\nUsuarios con rol {nombre}:")
            for u in users:
                uid, nombre_u, apellido_u, email_u = u
                display = f"{nombre_u or ''} {apellido_u or ''}".strip() or email_u or str(uid)
                print(f"  - {display} | {email_u} | id={uid}")
                affected_users.append({"id": str(uid), "name": display, "email": email_u, "role_id": rid})

    return roles, affected_users


def perform_changes(conn, admin_emails: List[str], jose_identifier: str):
    # ensure roles exist
    admin_id = ensure_role(conn, "administrador")
    cajero_id = ensure_role(conn, "cajero")

    print(f"Using administrador id={admin_id}, cajero id={cajero_id}")

    # assign admins by email
    if admin_emails:
        for email in admin_emails:
            print(f"Asignando administrador a {email}")
            conn.execute(
                text("UPDATE usuarios SET rol_id = CAST(:rid AS uuid), activo = true WHERE lower(email) = lower(:email)"),
                {"rid": admin_id, "email": email},
            )

    # assign jose
    if jose_identifier:
        print(f"Buscando y asignando cajero a identificador '{jose_identifier}' (email o nombre)")
        conn.execute(
            text(
                "UPDATE usuarios SET rol_id = CAST(:rid AS uuid), activo = true WHERE lower(email) = lower(:ident) OR lower(nombre) LIKE lower(:like_ident)"
            ),
            {"rid": cajero_id, "ident": jose_identifier, "like_ident": f"{jose_identifier}%"},
        )

    # find other roles
    other = conn.execute(
        text("SELECT id FROM roles WHERE lower(nombre) NOT IN ('administrador','cajero')")
    ).fetchall()
    other_ids = [str(r[0]) for r in other]
    if other_ids:
        print(f"Reasignando usuarios de roles {other_ids} a 'administrador' por defecto")
        # build a safe SQL list of uuid literals (they come from the DB)
        other_ids_sql = ",".join([f"'{oid}'::uuid" for oid in other_ids])
        conn.execute(
            text(f"UPDATE usuarios SET rol_id = CAST(:admin_id AS uuid) WHERE rol_id IN ({other_ids_sql})"),
            {"admin_id": admin_id},
        )

        print("Eliminando roles no deseados")
        conn.execute(text(f"DELETE FROM roles WHERE id IN ({other_ids_sql})"))


def main():
    parser = ArgumentParser(description="Cleanup roles: keep only 'administrador' and 'cajero' and assign users.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. If not set, runs dry-run.")
    parser.add_argument("--admin-emails", help="Comma-separated admin emails to ensure have administrador role")
    parser.add_argument("--jose", help="Identifier (email or name prefix) for Jose to assign cajero role", default="jose")
    args = parser.parse_args()

    load_env(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL missing in .env", file=sys.stderr)
        return 1

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    with engine.begin() as conn:
        roles, affected = list_roles_and_users(conn)
        print("\nResumen:")
        print(f"Total roles: {len(roles)}")
        print(f"Usuarios afectados por eliminación potencial: {len(affected)}")

        if not args.apply:
            print("\nDry-run completado. Ejecuta con --apply --admin-emails a@b.com --jose jose@example.com para aplicar cambios.")
            return 0

        # parse admin emails
        admin_emails = [e.strip() for e in args.admin_emails.split(",")] if args.admin_emails else []
        perform_changes(conn, admin_emails, args.jose)
        print("Cambios aplicados.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
