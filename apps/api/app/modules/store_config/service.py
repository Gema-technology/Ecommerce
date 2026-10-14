from sqlalchemy.orm import Session

from app.modules.store_config.models import StoreConfig
from app.modules.store_config.repository import StoreConfigRepository
from app.modules.store_config.schemas import (
    StoreConfigRead,
    StoreConfigUpdate,
    _parse_province_rates,
    province_rates_to_json,
)


class StoreConfigService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = StoreConfigRepository(db)

    def _to_read(self, row: StoreConfig) -> StoreConfigRead:
        return StoreConfigRead(
            business_name=row.business_name,
            business_ruc=row.business_ruc,
            business_phone=row.business_phone,
            business_address=row.business_address,
            business_email=row.business_email,
            bank_name=row.bank_name,
            bank_account_type=row.bank_account_type,
            bank_account_number=row.bank_account_number,
            bank_account_holder=row.bank_account_holder,
            bank_account_id=row.bank_account_id,
            bank_transfer_instructions=row.bank_transfer_instructions,
            shipping_enabled=bool(row.shipping_enabled),
            shipping_flat_rate=row.shipping_flat_rate,
            shipping_free_threshold=row.shipping_free_threshold,
            shipping_province_rates=_parse_province_rates(row.shipping_province_rates),
            updated_at=row.updated_at,
        )

    def get_read(self) -> StoreConfigRead:
        existed = self.repo.get() is not None
        row = self.repo.get_or_create_from_settings()
        if not existed:
            self.db.commit()
            self.db.refresh(row)
        return self._to_read(row)

    def update(self, payload: StoreConfigUpdate) -> StoreConfigRead:
        row = self.repo.get_or_create_from_settings()
        row.business_name = payload.business_name
        row.business_ruc = payload.business_ruc
        row.business_phone = payload.business_phone
        row.business_address = payload.business_address
        row.business_email = payload.business_email
        row.bank_name = payload.bank_name
        row.bank_account_type = payload.bank_account_type
        row.bank_account_number = payload.bank_account_number
        row.bank_account_holder = payload.bank_account_holder
        row.bank_account_id = payload.bank_account_id
        row.bank_transfer_instructions = payload.bank_transfer_instructions
        row.shipping_enabled = payload.shipping_enabled
        row.shipping_flat_rate = payload.shipping_flat_rate
        row.shipping_free_threshold = payload.shipping_free_threshold
        row.shipping_province_rates = province_rates_to_json(payload.shipping_province_rates)
        self.db.commit()
        self.db.refresh(row)
        return self._to_read(row)
