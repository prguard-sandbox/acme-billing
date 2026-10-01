import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.db import get_db
from app.models import Invoice, InvoiceLine, User
from app.routers.customers import get_owned_customer
from app.schemas import InvoiceCreate, InvoiceRead, InvoiceSummary, StatusTotals
from app.services.tax import compute_tax_cents

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"sent", "void"},
    "sent": {"paid", "void"},
    "paid": set(),
    "void": set(),
}


def get_owned_invoice(db: Session, invoice_id: int, user: User) -> Invoice:
    """Loads an invoice, answering 404 for missing ones and for other users' ones."""
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id).options(selectinload(Invoice.lines))
    )
    if invoice is None or invoice.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


def new_invoice_number() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m")
    return f"INV-{stamp}-{uuid.uuid4().hex[:8].upper()}"


def transition(invoice: Invoice, new_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(invoice.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Cannot move an invoice from {invoice.status} to {new_status}",
        )
    invoice.status = new_status
    if new_status == "paid":
        invoice.paid_at = datetime.now(timezone.utc)


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.owner_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    stmt = stmt.options(selectinload(Invoice.lines)).order_by(Invoice.id.desc())
    return list(db.scalars(stmt.limit(limit).offset(offset)))


# Declared before "/{invoice_id}" so "summary" is never read as an invoice id.
@router.get("/summary", response_model=InvoiceSummary)
def invoice_summary(
    currency: str = Query(default="USD", pattern=r"^[A-Z]{3}$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceSummary:
    """How many of the current user's invoices are in each status, and what they add up to,
    in one currency (totals in different currencies cannot be added)."""
    rows = db.execute(
        select(Invoice.status, func.count(Invoice.id), func.coalesce(func.sum(Invoice.total_cents), 0))
        .where(Invoice.owner_id == current_user.id, Invoice.currency == currency)
        .group_by(Invoice.status)
    ).all()
    by_status = {name: StatusTotals(count=0, total_cents=0) for name in ALLOWED_TRANSITIONS}
    for name, count, total_cents in rows:
        by_status[name] = StatusTotals(count=count, total_cents=total_cents)
    return InvoiceSummary(
        currency=currency,
        by_status=by_status,
        outstanding_cents=by_status["sent"].total_cents,
    )


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Invoice:
    customer = get_owned_customer(db, payload.customer_id, current_user)

    if payload.due_date < date.today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="due_date cannot be in the past",
        )

    subtotal_cents = sum(line.quantity * line.unit_price_cents for line in payload.lines)
    tax_cents = compute_tax_cents(subtotal_cents, customer.tax_region)

    invoice = Invoice(
        owner_id=current_user.id,
        customer_id=customer.id,
        number=new_invoice_number(),
        currency=payload.currency,
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=subtotal_cents + tax_cents,
        due_date=payload.due_date,
        lines=[
            InvoiceLine(
                description=line.description,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
            )
            for line in payload.lines
        ],
    )
    db.add(invoice)
    db.commit()

    logger.info(
        "invoice created id=%s number=%s total_cents=%s",
        invoice.id,
        invoice.number,
        invoice.total_cents,
    )
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Invoice:
    return get_owned_invoice(db, invoice_id, current_user)


@router.post("/{invoice_id}/send", response_model=InvoiceRead)
def send_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Invoice:
    invoice = get_owned_invoice(db, invoice_id, current_user)
    transition(invoice, "sent")
    db.commit()
    logger.info("invoice sent id=%s", invoice.id)
    return invoice


@router.post("/{invoice_id}/pay", response_model=InvoiceRead)
def pay_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Invoice:
    invoice = get_owned_invoice(db, invoice_id, current_user)
    transition(invoice, "paid")
    db.commit()
    logger.info("invoice paid id=%s total_cents=%s", invoice.id, invoice.total_cents)
    return invoice


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
def void_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Invoice:
    invoice = get_owned_invoice(db, invoice_id, current_user)
    transition(invoice, "void")
    db.commit()
    logger.info("invoice voided id=%s", invoice.id)
    return invoice
