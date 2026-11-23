from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.models import Asset

CENT = Decimal("0.01")
DAYS_PER_YEAR = Decimal("365.2425")


def depreciation_for_inputs(
    cost_value,
    residual_value,
    useful_life_months: int,
    purchase_date: date,
    as_of: date,
) -> tuple[Decimal, Decimal]:
    cost = Decimal(cost_value)
    residual = Decimal(residual_value)
    depreciable_basis = max(Decimal("0"), cost - residual)
    elapsed_days = max(0, (as_of - purchase_date).days)
    useful_life_years = Decimal(useful_life_months) / Decimal(12)
    total_life_days = useful_life_years * DAYS_PER_YEAR
    fraction = min(Decimal(elapsed_days) / total_life_days, Decimal("1"))
    accumulated = (depreciable_basis * fraction).quantize(CENT, rounding=ROUND_HALF_UP)
    book_value = max(residual, cost - accumulated).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    return accumulated, book_value


def depreciation_values(asset: Asset, as_of: date) -> tuple[Decimal, Decimal]:
    return depreciation_for_inputs(
        asset.purchase_cost,
        asset.residual_value,
        asset.useful_life_months,
        asset.purchase_date,
        as_of,
    )
