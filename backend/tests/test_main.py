import os
os.environ["IS_DOCKER"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./test_ci.db"  # BD en archivo (repo root/backend)

# ahora sí importamos la app ya con la BD lista
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_seed_properties_exists():
    # Debe existir al menos la propiedad con id=1 de tu seed
    resp = client.get("/api/reserved-dates/1")
    assert resp.status_code == 200
    assert "reserved_dates" in resp.json()

def test_register_and_login_flow():
    # registro
    payload = {"name": "Test", "email": "test@example.com", "password": "1234"}
    r = client.post("/api/register", json=payload)
    assert r.status_code in (200, 201)
    user_id = r.json().get("user_id")
    assert user_id is not None

    # login
    r2 = client.post("/api/login", json={"email": "test@example.com", "password": "1234"})
    assert r2.status_code == 200
    assert r2.json()["message"].lower().startswith("inicio de sesión exitoso")

def test_reserve_and_cancel():
    # crear usuario
    payload = {"name": "A", "email": "a@a.com", "password": "x"}
    user_id = client.post("/api/register", json=payload).json()["user_id"]

    # reservar (rango futuro)
    r = client.post("/api/reserve", json={
        "property_id": 1,
        "user_id": user_id,
        "in_time": "2099-01-10",
        "out_time": "2099-01-12"
    })
    assert r.status_code == 201

    # ver activas
    r2 = client.get(f"/api/active-reservations/{user_id}")
    assert r2.status_code == 200
    data = r2.json()["reservations"]
    assert len(data) == 1
    booking_id = data[0]["id"]

    # cancelar (antes del check-in)
    r3 = client.post("/api/cancel-reservation", json={
        "booking_id": booking_id, "user_id": user_id
    })
    assert r3.status_code == 200
    assert "cancelada" in r3.json()["message"].lower()

def test_feedback_crud_minimal():
    # crear feedback
    r = client.post("/api/feedback", json={"id_property": 1, "comment": "Bien", "rating": 5})
    assert r.status_code == 201

    # listar
    r2 = client.get("/api/feedback/1")
    assert r2.status_code == 200
    assert len(r2.json()["feedback"]) >= 1
