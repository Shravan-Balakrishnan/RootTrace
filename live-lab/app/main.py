"""
Live Lab Sample Application — Main FastAPI Entry Point.
Runs as a separate managed service on port 8001.
"""
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import os

from .services import calculate_order_total, check_inventory, process_refund, INVENTORY_STORE

app = FastAPI(
    title="LiveLab Checkout Service",
    description="Sample e-commerce microservice monitored and debugged by RootTrace Live.",
    version="1.0.0"
)


class OrderItem(BaseModel):
    sku: str
    price: float = Field(ge=0.0)
    quantity: int = Field(gt=0)


class OrderCalculationRequest(BaseModel):
    items: List[OrderItem]
    discount_code: Optional[str] = None
    tax_rate: float = 0.08


class RefundRequest(BaseModel):
    order_id: str
    amount: float = Field(gt=0.0)


@app.get("/")
def index():
    return {
        "service": "live-lab-checkout",
        "status": "ok",
        "health_check": "/health",
        "api_docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Liveness and readiness probe for RootTrace process monitoring."""
    return {
        "status": "ok",
        "service": "live-lab-checkout",
        "pid": os.getpid(),
        "version": "1.0.0"
    }


@app.get("/inventory/{sku}")
def get_inventory(sku: str):
    sku_upper = sku.strip().upper()
    if sku_upper not in INVENTORY_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SKU '{sku}' not found in inventory."
        )
    return {
        "sku": sku_upper,
        "available_units": INVENTORY_STORE[sku_upper],
        "in_stock": INVENTORY_STORE[sku_upper] > 0
    }


@app.post("/orders/calculate")
def calculate_order(req: OrderCalculationRequest):
    try:
        raw_items = [{"price": it.price, "quantity": it.quantity} for it in req.items]
        summary = calculate_order_total(raw_items, discount_code=req.discount_code, tax_rate=req.tax_rate)
        return {
            "status": "SUCCESS",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/refunds")
def create_refund(req: RefundRequest):
    try:
        res = process_refund(order_id=req.order_id, amount=req.amount)
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
