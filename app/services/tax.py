"""Sales tax and VAT. Amounts are integer cents and rates are Decimals, so no
floating point ever touches money."""

from decimal import ROUND_HALF_UP, Decimal

TAX_RATES: dict[str, Decimal] = {
    "US-CA": Decimal("0.0725"),
    "US-NY": Decimal("0.08875"),
    "US-TX": Decimal("0.0625"),
    "US-OR": Decimal("0"),
    "GB": Decimal("0.20"),
    "DE": Decimal("0.19"),
    "FR": Decimal("0.20"),
}


class UnknownRegionError(ValueError):
    def __init__(self, region: str) -> None:
        super().__init__(f"Unknown tax region: {region}")
        self.region = region


def is_known_region(region: str) -> bool:
    return region in TAX_RATES


def rate_for(region: str) -> Decimal:
    try:
        return TAX_RATES[region]
    except KeyError:
        raise UnknownRegionError(region) from None


def compute_tax_cents(subtotal_cents: int, region: str) -> int:
    """Tax owed on `subtotal_cents`, rounded half up to a whole cent."""
    tax = Decimal(subtotal_cents) * rate_for(region)
    return int(tax.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
