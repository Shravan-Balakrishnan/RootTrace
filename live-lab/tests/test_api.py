import os
import sys
import pytest
from starlette.testclient import TestClient

# Ensure live-lab root is on sys.path
_LIVE_LAB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIVE_LAB_DIR not in sys.path:
    sys.path.insert(0, _LIVE_LAB_DIR)

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "live-lab-checkout"
    assert "pid" in data


def test_inventory_lookup(client):
    r = client.get("/inventory/SKU-WIDGET-01")
    assert r.status_code == 200
    data = r.json()
    assert data["sku"] == "SKU-WIDGET-01"
    assert data["available_units"] > 0
    assert data["in_stock"] is True

    r_404 = client.get("/inventory/NON_EXISTENT_ITEM")
    assert r_404.status_code == 404


def test_order_calculation_without_discount(client):
    payload = {
        "items": [
            {"sku": "SKU-WIDGET-01", "price": 50.0, "quantity": 2},
            {"sku": "SKU-GADGET-02", "price": 20.0, "quantity": 1}
        ],
        "tax_rate": 0.10
    }
    r = client.post("/orders/calculate", json=payload)
    assert r.status_code == 200
    summary = r.json()["summary"]
    # subtotal = (50*2) + 20 = 120.0
    assert summary["subtotal"] == 120.0
    assert summary["discount_amount"] == 0.0
    # tax = 120 * 0.10 = 12.0
    assert summary["tax_amount"] == 12.0
    assert summary["final_total"] == 132.0


def test_order_calculation_with_discount(client):
    payload = {
        "items": [
            {"sku": "SKU-WIDGET-01", "price": 100.0, "quantity": 1}
        ],
        "discount_code": "SUMMER20",
        "tax_rate": 0.08
    }
    r = client.post("/orders/calculate", json=payload)
    assert r.status_code == 200
    summary = r.json()["summary"]
    # subtotal = 100.0, 20% discount = 20.0, discounted = 80.0, tax = 80 * 0.08 = 6.40, final = 86.40
    assert summary["subtotal"] == 100.0
    assert summary["discount_amount"] == 20.0
    assert summary["tax_amount"] == 6.40
    assert summary["final_total"] == 86.40


def test_order_calculation_invalid_items(client):
    r = client.post("/orders/calculate", json={"items": []})
    assert r.status_code in [400, 422]


def test_refund_processing(client):
    payload = {"order_id": "ORD-12345", "amount": 45.50}
    r = client.post("/refunds", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["order_id"] == "ORD-12345"
    assert data["refund_amount"] == 45.50
    assert data["status"] == "APPROVED"


def test_refund_invalid_amount(client):
    r = client.post("/refunds", json={"order_id": "ORD-12345", "amount": -10.0})
    assert r.status_code in [400, 422]
