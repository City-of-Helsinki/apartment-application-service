from decimal import Decimal
from typing import TypedDict


class SalesReportProjectTotalsDict(TypedDict):
    sold_haso_apartments_count: int
    sold_hitas_apartments_count: int
    unsold_apartments_count: int
    haso_right_of_occupancy_payment_sum: Decimal
    hitas_sales_price_sum: Decimal
    hitas_debt_free_sales_price_sum: Decimal
