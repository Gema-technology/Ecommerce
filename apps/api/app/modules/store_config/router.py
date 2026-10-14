from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.store_config.schemas import StoreConfigRead, StoreConfigUpdate
from app.modules.store_config.service import StoreConfigService

router = APIRouter(tags=["store-config"])


@router.get("/admin/store-config", response_model=StoreConfigRead)
def get_store_config(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> StoreConfigRead:
    return StoreConfigService(db).get_read()


@router.put("/admin/store-config", response_model=StoreConfigRead)
def update_store_config(
    payload: StoreConfigUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> StoreConfigRead:
    return StoreConfigService(db).update(payload)
