import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Customer, Invoice, User
from app.schemas import CustomerCreate, CustomerRead
from app.services.tax import is_known_region

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


def get_owned_customer(db: Session, customer_id: int, user: User) -> Customer:
    """Loads a customer, answering 404 for missing ones and for other users' ones."""
    customer = db.get(Customer, customer_id)
    if customer is None or customer.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.get("", response_model=list[CustomerRead])
def list_customers(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Customer]:
    stmt = (
        select(Customer)
        .where(Customer.owner_id == current_user.id)
        .order_by(Customer.id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Customer:
    if not is_known_region(payload.tax_region):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown tax region {payload.tax_region}",
        )

    customer = Customer(
        owner_id=current_user.id,
        name=payload.name,
        email=payload.email.lower(),
        tax_region=payload.tax_region,
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="You already have a customer with that email",
        ) from None

    logger.info("customer created id=%s owner=%s", customer.id, current_user.id)
    return customer


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Customer:
    return get_owned_customer(db, customer_id, current_user)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    customer = get_owned_customer(db, customer_id, current_user)

    invoice_count = db.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.customer_id == customer.id)
    )
    if invoice_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Customer has invoices and cannot be deleted",
        )

    db.delete(customer)
    db.commit()
    logger.info("customer deleted id=%s owner=%s", customer_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
