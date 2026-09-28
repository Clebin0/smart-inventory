import os
os.environ["APP_TOKEN"]="test-token"
from fastapi.testclient import TestClient
from app import app

client=TestClient(app)

def test_health():
    r=client.get("/health")
    assert r.status_code==200
    assert r.json()["status"]=="ok"

def test_requires_token():
    r=client.get("/assets")
    assert r.status_code==401
