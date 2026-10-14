from sqlalchemy.orm import Session

from app.modules.store_config.models import StoreConfig
from app.modules.store_config.schemas import StoreConfigRead, province_rates_to_json


class StoreConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> StoreConfig | None:
        return self.db.get(StoreConfig, 1)

    def get_or_create_from_settings(self) -> StoreConfig:
        row = self.get()
        if row is not None:
            return row
        seed = StoreConfigRead.from_settings()
        row = StoreConfig(
            id=1,
            business_name=seed.business_name,
            business_ruc=seed.business_ruc,
            business_phone=seed.business_phone,
            business_address=seed.business_address,
            business_email=seed.business_email,
            bank_name=seed.bank_name,
            bank_account_type=seed.bank_account_type,
            bank_account_number=seed.bank_account_number,
            bank_account_holder=seed.bank_account_holder,
            bank_account_id=seed.bank_account_id,
            bank_transfer_instructions=seed.bank_transfer_instructions,
            shipping_enabled=seed.shipping_enabled,
            shipping_flat_rate=seed.shipping_flat_rate,
            shipping_free_threshold=seed.shipping_free_threshold,
            shipping_province_rates=province_rates_to_json(seed.shipping_province_rates),
        )
        self.db.add(row)
        self.db.flush()
        return row
