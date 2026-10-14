from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import RequireAdmin
from app.modules.sri.schemas import (
    CertVerifyResponse,
    EmitFiscalDocumentRequest,
    FiscalDocumentListResponse,
    FiscalDocumentRead,
    SriConfigRead,
    SriConfigUpdate,
)
from app.modules.sri.service import SriService

router = APIRouter(tags=["sri"])


@router.get("/admin/sri/config", response_model=SriConfigRead)
def get_sri_config(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SriConfigRead:
    return SriService(db).get_config()


@router.put("/admin/sri/config", response_model=SriConfigRead)
def update_sri_config(
    payload: SriConfigUpdate,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> SriConfigRead:
    return SriService(db).update_config(payload)


@router.post("/admin/sri/cert", response_model=SriConfigRead)
async def upload_sri_cert(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> SriConfigRead:
    return await SriService(db).upload_certificate(file)


@router.post("/admin/sri/cert/verify", response_model=CertVerifyResponse)
def verify_sri_cert(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> CertVerifyResponse:
    return SriService(db).verify_certificate()


@router.get("/admin/fiscal-documents", response_model=FiscalDocumentListResponse)
def list_fiscal_documents(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> FiscalDocumentListResponse:
    return SriService(db).list_documents(page=page, page_size=page_size)


@router.get("/admin/fiscal-documents/{doc_id}", response_model=FiscalDocumentRead)
def get_fiscal_document(
    doc_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> FiscalDocumentRead:
    return SriService(db).get_document(doc_id)


@router.get(
    "/admin/orders/{order_id}/fiscal-documents",
    response_model=list[FiscalDocumentRead],
)
def list_order_fiscal_documents(
    order_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> list[FiscalDocumentRead]:
    return SriService(db).list_for_order(order_id)


@router.post(
    "/admin/orders/{order_id}/fiscal-documents",
    response_model=FiscalDocumentRead,
    status_code=201,
)
def emit_fiscal_document(
    order_id: UUID,
    payload: EmitFiscalDocumentRequest,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> FiscalDocumentRead:
    return SriService(db).emit_for_order(order_id, payload)


@router.post(
    "/admin/fiscal-documents/{doc_id}/retry-authorization",
    response_model=FiscalDocumentRead,
)
def retry_authorization(
    doc_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> FiscalDocumentRead:
    return SriService(db).retry_authorization(doc_id)


@router.get("/admin/fiscal-documents/{doc_id}/pdf")
def download_fiscal_pdf(
    doc_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    data, filename = SriService(db).get_pdf_bytes(doc_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/fiscal-documents/{doc_id}/xml")
def download_fiscal_xml(
    doc_id: UUID,
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    text, filename = SriService(db).get_xml_text(doc_id)
    return Response(
        content=text.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
