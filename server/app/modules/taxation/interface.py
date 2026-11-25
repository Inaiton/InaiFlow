"""Public API of the taxation module: pure GST / TDS engines used by accounts (compute-tax, voucher GST metadata)."""

from app.modules.taxation.gst_calc import (
    GstContext,
    GstLine,
    GstResult,
    compute_gst,
    hsn_for_return,
    is_valid_gstin,
    place_of_supply,
)
from app.modules.taxation.tds_calc import challan_due_date, compute_tds

__all__ = [
    "GstContext",
    "GstLine",
    "GstResult",
    "challan_due_date",
    "compute_gst",
    "compute_tds",
    "hsn_for_return",
    "is_valid_gstin",
    "place_of_supply",
]
