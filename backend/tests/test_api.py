from fastapi.testclient import TestClient
import os
import sys
from pathlib import Path

path = os.getcwd()
parent_path = Path().resolve().parent

if str(parent_path) not in sys.path:
    sys.path.append(str(parent_path))
if path not in sys.path:
    sys.path.append(path)
print(sys.path)
import app

client = TestClient(app.app)


def test_bad_city():
    body = {"city": "asdascasc", "start_date": "2024-01-02", "end_date": "2024-01-03"}
    response = client.post("/agents/invoke", json=body)
    assert response.status_code == 404
    assert response.json() == {"detail": "City is not found"}


def test_bad_order_date():
    body = {"city": "Toronto", "start_date": "2024-01-02", "end_date": "2024-01-01"}
    response = client.post("/agents/invoke", json=body)
    assert response.status_code == 400
    assert response.json() == {"detail": "Start date must be before end date"}
