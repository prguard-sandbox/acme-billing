# acme-billing

Invoicing service for Acme. Users manage their customers, draft and send
invoices, and mark them paid. Tax is calculated per customer region when an
invoice is created.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m app.auth you@example.com      # creates a user and prints its API key once
uvicorn app.main:app --reload           # http://localhost:8000/docs
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./acme-billing.db` | SQLAlchemy database URL |
| `LOG_LEVEL` | `INFO` | Python logging level |

Every route except `GET /healthz` needs an `X-API-Key` header. Keys are stored
as SHA-256 hashes; the raw key is only shown when the user is created.

## API

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/healthz` | liveness probe |
| `GET` | `/customers` | your customers (`limit`, `offset`) |
| `POST` | `/customers` | create a customer |
| `GET` | `/customers/{id}` | one customer |
| `DELETE` | `/customers/{id}` | delete a customer that has no invoices |
| `GET` | `/invoices` | your invoices (`status`, `limit`, `offset`) |
| `POST` | `/invoices` | create a draft invoice, tax included |
| `GET` | `/invoices/{id}` | one invoice with its lines |
| `POST` | `/invoices/{id}/send` | draft -> sent |
| `POST` | `/invoices/{id}/pay` | sent -> paid |
| `POST` | `/invoices/{id}/void` | draft or sent -> void |

## Project layout

```
app/
  main.py           FastAPI app and router wiring
  db.py             engine, session and Base
  models.py         SQLAlchemy models
  schemas.py        Pydantic request/response models
  auth.py           API-key authentication
  routers/          HTTP handlers
  services/         business rules (tax)
```

## Conventions

- Money is `Decimal` or integer cents, never `float`. Stored amounts are
  integer cents (`total_cents`); tax rates are `Decimal`.
- Every route that touches a customer or an invoice checks that
  `current_user` owns it. Look resources up through `get_owned_customer` /
  `get_owned_invoice`, which answer 404 for someone else's data.
- Use `logging` (`logging.getLogger(__name__)`), not `print`.
- Validate request bodies with Pydantic schemas in `app/schemas.py`, not by
  hand inside the handler.
