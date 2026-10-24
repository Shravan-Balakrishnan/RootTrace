"""
Order and Inventory Services for Live Lab Application.
"""
from typing import Dict, List, Optional, Any
import math

# In-memory inventory catalogue
INVENTORY_STORE: Dict[str, int] = {
    "SKU-WIDGET-01": 50,
    "SKU-GADGET-02": 25,
    "SKU-SENSOR-03": 100,
    "SKU-MODULE-04": 0  # Out of stock
}

# Active promotional codes
DISCOUNT_CODES: Dict[str, float] = {
    "WELCOME10": 0.10,
    "SUMMER20": 0.20,
    "VIP30": 0.30
}


def check_inventory(sku: str, quantity: int) -> bool:
    """Verifies that requested quantity is available in stock."""
    if quantity <= 0:
        raise ValueError("Requested quantity must be greater than zero.")
    available = INVENTORY_STORE.get(sku, 0)
    return available >= quantity


def calculate_order_total(
    items: List[Dict[str, float]],
    discount_code: Optional[str] = None,
    tax_rate: float = 0.08
) -> Dict[str, float]:
    """
    Calculates subtotal, discount, tax, and final total for an order.
    Items format: [{"price": 25.0, "quantity": 2}, ...]
    """
    if not items:
        raise ValueError("Cannot process order with empty items list.")

    subtotal = 0.0
    for item in items:
        price = float(item.get("price", 0.0))
        qty = int(item.get("quantity", 1))
        if price < 0 or qty < 0:
            raise ValueError("Price and quantity must be non-negative.")
        subtotal += price * qty

    discount_amount = 0.0
    if discount_code:
        clean_code = discount_code.strip().upper()
        rate = DISCOUNT_CODES.get(clean_code)
        if rate is not None:
            discount_amount = subtotal * rate
    discounted_subtotal = max(0.0, subtotal - discount_amount)
    tax_amount = round(discounted_subtotal * tax_rate, 2)
    final_total = round(discounted_subtotal + tax_amount, 2)

    return {
        "subtotal": round(subtotal, 2),
        "discount_amount": round(discount_amount, 2),
        "tax_amount": tax_amount,
        "final_total": final_total
    }


def process_refund(order_id: str, amount: float) -> Dict[str, Any]:
    """Processes a refund request for a completed order."""
    if not order_id or not order_id.strip():
        raise ValueError("Invalid order ID provided.")
    if amount <= 0:
        raise ValueError("Refund amount must be strictly positive.")

    return {
        "order_id": order_id.strip(),
        "refund_amount": round(amount, 2),
        "status": "APPROVED",
        "reference": f"REF-{order_id.strip().upper()}-001"
    }
