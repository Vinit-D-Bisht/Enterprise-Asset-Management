import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.models import Asset

CENT = Decimal("0.01")


def depreciation_for_inputs(
    cost_value,
    residual_value,
    useful_life_months: int,
    purchase_date: date,
    as_of: date,
) -> tuple[Decimal, Decimal]:
    cost = Decimal(cost_value)
    residual = Decimal(residual_value)
    if cost < 0 or residual < 0 or residual > cost or useful_life_months <= 0:
        raise ValueError("Invalid asset cost, residual value, or useful life")
    depreciable_basis = max(Decimal("0"), cost - residual)
    elapsed_days = max(0, (as_of - purchase_date).days)
    end_month_index = purchase_date.month - 1 + useful_life_months
    end_year = purchase_date.year + end_month_index // 12
    end_month = end_month_index % 12 + 1
    end_day = min(purchase_date.day, calendar.monthrange(end_year, end_month)[1])
    useful_life_end = date(end_year, end_month, end_day)
    total_life_days = Decimal((useful_life_end - purchase_date).days)
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
