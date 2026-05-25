# Backend FastAPI - Tiendita POS

API para gestion de productos, inventario y catalogos con PostgreSQL (Supabase).

## 1) Requisitos

- Python 3.11+
- PostgreSQL de Supabase

## 2) Configuracion

1. Copia variables de entorno:

```bash
cp .env.example .env
```

2. Edita `.env` y completa estos valores:

```env
APP_NAME=Tiendita
APP_ENV=development
APP_DEBUG=true
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres

SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_SUPABASE_PUBLISHABLE_KEY
# Necesaria solo para scripts de admin y fallback REST
# SUPABASE_SERVICE_ROLE_KEY=YOUR_SUPABASE_SERVICE_ROLE_KEY

SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWKS_URL=

REQUIRE_AUTH_TOKEN=true
ALLOW_ROLE_HEADER_FALLBACK=true
REQUIRE_ROLE_HEADER=false
```

Si usas el script [scripts/create_admin_user.py](scripts/create_admin_user.py), entonces `SUPABASE_SERVICE_ROLE_KEY` debe estar definida.

## 3) Instalar dependencias

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Nota: `EmailStr` en Pydantic requiere `email-validator`, y ya queda incluido en `requirements.txt`.

## 4) Crear esquema SQL en Supabase

Ejecuta [sql/schema.sql](sql/schema.sql) en el SQL Editor de Supabase.

## 5) Levantar API

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger:

- http://127.0.0.1:8000/docs

## 6) Seguridad por rol y autenticacion (Supabase JWT)

El backend ahora valida `Authorization: Bearer <token>` emitido por Supabase Auth.

Resolucion de rol:

1. Busca el usuario en `usuarios.auth_user_id = sub` del token.
2. Si existe relacion con `roles`, usa `roles.nombre`.
3. Si no encuentra rol en DB, intenta `app_metadata.role`, `user_metadata.role` o `role` del JWT.

Roles esperados:

- `dueño` / `dueno` / `administrador`
- `encargado`
- `cajero`
- `ayudante`

Fallback para desarrollo:

- Puedes mandar `X-Role` si `ALLOW_ROLE_HEADER_FALLBACK=true`.

Si quieres desactivar autenticacion temporalmente:

```env
REQUIRE_AUTH_TOKEN=false
ALLOW_ROLE_HEADER_FALLBACK=true
REQUIRE_ROLE_HEADER=true
```

Ejemplo header para pruebas manuales:

```http
Authorization: Bearer eyJ...
```

## 7) Variables de entorno

El backend lee `.env` desde la carpeta `back/` mediante `pydantic-settings`.

Obligatorias para arrancar la API:

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`

Opcionales, pero recomendadas:

- `SUPABASE_SERVICE_ROLE_KEY` para crear/sincronizar usuarios admin
- `SUPABASE_JWT_AUDIENCE` si tu proyecto usa otra audiencia
- `SUPABASE_JWKS_URL` si quieres sobrescribir la URL estandar de JWKS
- `REQUIRE_AUTH_TOKEN`, `ALLOW_ROLE_HEADER_FALLBACK`, `REQUIRE_ROLE_HEADER` para ajustar el modo desarrollo

## 8) Endpoints principales

Base: `/api/v1`

- `GET /health`
- `GET /catalogs/departamentos`
- `GET /catalogs/categorias?departamento_id=`
- `GET /catalogs/subcategorias?categoria_id=`
- `GET /catalogs/marcas`
- `GET /catalogs/unidades`
- `GET /catalogs/proveedores`

Productos (4 pantallas):

- `GET /products`
  - Busqueda: `q` (nombre, codigo interno, codigo barras)
  - Filtros: `departamento_id`, `categoria_id`, `activo`, `bajo_stock`, `granel`, `perecedero`
- `POST /products`
  - Alta producto con codigo interno automatico por prefijo de categoria
- `PUT /products/{product_id}`
  - Edicion de producto (sin editar stock directo)
- `PATCH /products/{product_id}/status`
  - Activar/Inactivar
- `POST /products/{product_id}/adjust-inventory`
  - Ajuste inventario con motivo y movimiento
- `GET /products/{product_id}`
  - Detalle completo (datos, margen, stock, movimientos, historial precios, ultimas compras/ventas)

## 8) Flujo de codigo interno automatico

Al crear producto, se toma `categorias.prefijo_codigo` y se usa la tabla `folios`:

- `AZU-0001`
- `REF-0001`
- `ATU-0001`

Si no hay prefijo en categoria, usa `PRO-0001`.

## 9) Validaciones de negocio incluidas

- Costo y precio no pueden ser negativos.
- Precio de venta no puede ser menor al costo (si ocurre, responde error).
- No se elimina producto: se inactiva con endpoint de estado.
- Stock no se edita en formulario: solo por `adjust-inventory`.
