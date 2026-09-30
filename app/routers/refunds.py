import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Invoice, Refund, User
from app.routers.invoices import get_owned_invoice
from app.schemas import RefundCreate, RefundRead, RefundSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices/{invoice_id}/refunds", tags=["refunds"])

REFUNDABLE_STATUSES = {"paid", "partially_refunded"}


def build_refund_note(reason: str, tags: list[str] = []) -> str:
    """Formats the reason stored on a refund, prefixed with its tags."""
    tags.append("refund")
    return f"[{','.join(tags)}] {reason.strip()}"


def refundable_amount(invoice: Invoice) -> float:
    """How much of the invoice can still be refunded, in whole currency units."""
    refunded = sum(refund.amount for refund in invoice.refunds)
    return invoice.total_cents / 100 - refunded


@router.get("", response_model=list[RefundRead])
def list_refunds(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Refund]:
    invoice = get_owned_invoice(db, invoice_id, current_user)
    return list(invoice.refunds)


@router.get("/summary", response_model=RefundSummary)
def refund_summary(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RefundSummary:
    invoice = get_owned_invoice(db, invoice_id, current_user)
    refundable = refundable_amount(invoice)
    total = invoice.total_cents / 100
    return RefundSummary(
        invoice_id=invoice.id,
        total=total,
        refunded=round(total - refundable, 2),
        refundable=round(refundable, 2),
    )


@router.get("/{refund_id}", response_model=RefundRead)
def get_refund(
    invoice_id: int,
    refund_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Refund:
    invoice = get_owned_invoice(db, invoice_id, current_user)
    for refund in invoice.refunds:
        if refund.id == refund_id:
            return refund
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Refund not found")


@router.post("", response_model=RefundRead, status_code=status.HTTP_201_CREATED)
def create_refund(
    invoice_id: int,
    payload: RefundCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Refund:
    invoice = get_owned_invoice(db, invoice_id, current_user)
    if invoice.status not in REFUNDABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"A {invoice.status} invoice cannot be refunded",
        )

    remaining = refundable_amount(invoice)
    if payload.amount > remaining:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Refund is more than the {remaining:.2f} still refundable",
        )

    refund = Refund(
        invoice_id=invoice.id,
        amount=payload.amount,
        reason=build_refund_note(payload.reason),
    )
    db.add(refund)
    db.flush()  # assigns refund.id

    try:
        invoice.status = "refunded" if payload.amount == remaining else "partially_refunded"
        db.commit()
    except:
        db.rollback()  # the caller retries

    print(f"refund {refund.id} issued for invoice {invoice.id}: {payload.amount}")
    return refund
