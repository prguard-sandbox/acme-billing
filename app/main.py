import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers import customers, invoices, refunds

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    logger.info("acme-billing started")
    yield


app = FastAPI(title="acme-billing", version="0.3.0", lifespan=lifespan)

app.include_router(customers.router)
app.include_router(invoices.router)
app.include_router(refunds.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
