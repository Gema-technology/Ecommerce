from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.sri.models import FiscalDocument, SriConfig


class SriConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> SriConfig | None:
        return self.db.get(SriConfig, 1)

    def get_or_create(self) -> SriConfig:
        row = self.get()
        if row is not None:
            return row
        row = SriConfig(id=1)
        self.db.add(row)
        self.db.flush()
        return row

    def get_for_update(self) -> SriConfig:
        row = self.db.scalar(select(SriConfig).where(SriConfig.id == 1).with_for_update())
        if row is None:
            row = SriConfig(id=1)
            self.db.add(row)
            self.db.flush()
            row = self.db.scalar(select(SriConfig).where(SriConfig.id == 1).with_for_update())
            assert row is not None
        return row


class FiscalDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, doc: FiscalDocument) -> FiscalDocument:
        self.db.add(doc)
        self.db.flush()
        return doc

    def get(self, doc_id: UUID) -> FiscalDocument | None:
        return self.db.get(FiscalDocument, doc_id)

    def list_for_order(self, order_id: UUID) -> list[FiscalDocument]:
        return list(
            self.db.scalars(
                select(FiscalDocument)
                .where(FiscalDocument.order_id == order_id)
                .order_by(FiscalDocument.created_at.desc())
            ).all()
        )

    def active_for_order(self, order_id: UUID) -> FiscalDocument | None:
        return self.db.scalar(
            select(FiscalDocument)
            .where(
                FiscalDocument.order_id == order_id,
                FiscalDocument.status.notin_(["CANCELLED", "REJECTED"]),
            )
            .order_by(FiscalDocument.created_at.desc())
            .limit(1)
        )

    def list_all(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[FiscalDocument], int]:
        total = self.db.scalar(select(func.count()).select_from(FiscalDocument)) or 0
        offset = max(page - 1, 0) * page_size
        items = list(
            self.db.scalars(
                select(FiscalDocument)
                .order_by(FiscalDocument.created_at.desc())
                .offset(offset)
                .limit(page_size)
            ).all()
        )
        return items, int(total)

    @staticmethod
    def total_pages(total: int, page_size: int) -> int:
        return ceil(total / page_size) if page_size else 0
