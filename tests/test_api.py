import pytest
import os

# Force synthetic mode for tests
os.environ["DATA_MODE"] = "synthetic"
os.environ["GOOGLE_API_KEY"] = ""  # Ensure fallback mode

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db
from backend.services.vector_store import get_collection

# Initialize DB and ChromaDB before tests (lifespan may not run with TestClient)
init_db()
get_collection()

client = TestClient(app)


def test_health_endpoint():
    """Health check should return 200 with status info."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "data_mode" in data
    assert "timestamp" in data


def test_digest_endpoint_valid_city():
    """Digest for Bengaluru should return reports (using fallback)."""
    response = client.post("/api/digest", json={
        "city": "Bengaluru",
        "simple_mode": False,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "Bengaluru"
    assert "reports" in data
    assert "daily_tip" in data
    assert isinstance(data["reports"], list)


def test_digest_missing_city():
    """Missing required city field should return 422."""
    response = client.post("/api/digest", json={})
    assert response.status_code == 422


def test_chat_endpoint():
    """Chat should return a reply (fallback mode)."""
    response = client.post("/api/chat", json={
        "message": "Any UPI scams in Bengaluru?",
        "city": "Bengaluru",
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 0


def test_chat_empty_message():
    """Empty chat message should return 422."""
    response = client.post("/api/chat", json={
        "message": "",
        "city": "Bengaluru",
    })
    assert response.status_code == 422


def test_reports_endpoint():
    """Reports endpoint should return a list."""
    response = client.get("/api/reports")
    assert response.status_code == 200
    data = response.json()
    assert "reports" in data
    assert "count" in data


def test_reports_with_filter():
    """Reports endpoint with category filter should work."""
    response = client.get("/api/reports?category=SCAM")
    assert response.status_code == 200


def test_daily_tip_endpoint():
    """Daily tip should return a tip string."""
    response = client.get("/api/daily-tip?city=Bengaluru")
    assert response.status_code == 200
    data = response.json()
    assert "tip" in data
    assert "city" in data


def test_update_report_invalid_status():
    """Invalid status should return 400."""
    response = client.put("/api/reports/1/status", json={
        "status": "invalid_status",
    })
    assert response.status_code == 400
