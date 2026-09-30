from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    tax_region: str = Field(default="US-CA", max_length=16)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    tax_region: str
    created_at: datetime


class InvoiceLineCreate(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: int = Field(ge=1, le=10_000)
    unit_price_cents: int = Field(ge=0, le=100_000_000)


class InvoiceCreate(BaseModel):
    customer_id: int
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    due_date: date
    lines: list[InvoiceLineCreate] = Field(min_length=1, max_length=100)


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    quantity: int
    unit_price_cents: int


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    customer_id: int
    status: str
    currency: str
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    due_date: date
    created_at: datetime
    paid_at: datetime | None
    lines: list[InvoiceLineRead]
