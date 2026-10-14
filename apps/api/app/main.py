from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.brands.router import router as brands_router
from app.modules.cart import models as _cart_models  # noqa: F401
from app.modules.cart.router import router as cart_router

# Ensure ORM models are registered with SQLAlchemy metadata
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.categories.router import router as categories_router
from app.modules.checkout.router import router as checkout_router
from app.modules.employees import models as _employees_models  # noqa: F401
from app.modules.employees.router import router as employees_router
from app.modules.health import router as health_router
from app.modules.inventory import models as _inventory_models  # noqa: F401
from app.modules.inventory.router import router as inventory_router
from app.modules.notifications import models as _notifications_models  # noqa: F401
from app.modules.ops.router import router as ops_router
from app.modules.orders import models as _orders_models  # noqa: F401  # includes status events
from app.modules.orders.router import router as orders_router
from app.modules.payments import models as _payments_models  # noqa: F401
from app.modules.payments.router import router as payments_router
from app.modules.pricing import models as _pricing_models  # noqa: F401
from app.modules.pricing.router import router as pricing_router
from app.modules.products.router import router as products_router
from app.modules.quotes import models as _quotes_models  # noqa: F401
from app.modules.quotes.router import router as quotes_router
from app.modules.search.router import router as search_router
from app.modules.sri import models as _sri_models  # noqa: F401
from app.modules.sri.router import router as sri_router
from app.modules.store_config import models as _store_config_models  # noqa: F401
from app.modules.store_config.router import router as store_config_router
from app.modules.suppliers import models as _supplier_models  # noqa: F401
from app.modules.suppliers.router import router as suppliers_router
from app.modules.users.router import router as users_router


def _docs_urls() -> tuple[str | None, str | None, str | None]:
    """Return (docs_url, redoc_url, openapi_url); None disables the route."""
    if settings.openapi_docs_enabled:
        return "/docs", "/redoc", "/openapi.json"
    return None, None, None


def create_app() -> FastAPI:
    docs_url, redoc_url, openapi_url = _docs_urls()
    application = FastAPI(
        title="GEMA Technology API",
        description="API de la plataforma de comercio electrónico GEMA Technology.",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-GEMA-Payment-Secret",
            "X-GEMA-Internal-Secret",
        ],
    )

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(users_router, prefix="/api/v1")
    application.include_router(employees_router, prefix="/api/v1")
    application.include_router(store_config_router, prefix="/api/v1")
    application.include_router(categories_router, prefix="/api/v1")
    application.include_router(brands_router, prefix="/api/v1")
    application.include_router(products_router, prefix="/api/v1")
    application.include_router(suppliers_router, prefix="/api/v1")
    application.include_router(inventory_router, prefix="/api/v1")
    application.include_router(pricing_router, prefix="/api/v1")
    application.include_router(cart_router, prefix="/api/v1")
    application.include_router(orders_router, prefix="/api/v1")
    application.include_router(ops_router, prefix="/api/v1")
    application.include_router(checkout_router, prefix="/api/v1")
    application.include_router(payments_router, prefix="/api/v1")
    application.include_router(quotes_router, prefix="/api/v1")
    application.include_router(sri_router, prefix="/api/v1")
    application.include_router(search_router, prefix="/api/v1")

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"message": "GEMA Technology API"}

    return application


app = create_app()
