from fastapi import APIRouter

from app.api.v1.endpoints.catalogs import router as catalogs_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.inventory import router as inventory_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.sales import router as sales_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.clients import router as clients_router
from app.api.v1.endpoints.credits import router as credits_router
from app.api.v1.endpoints.reportes import router as reportes_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(catalogs_router)
api_router.include_router(inventory_router)
api_router.include_router(products_router)
api_router.include_router(sales_router)
api_router.include_router(users_router)
api_router.include_router(clients_router)
api_router.include_router(credits_router)
api_router.include_router(reportes_router, prefix="/reportes", tags=["reportes"])
