from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import app


def test_liveness_does_not_claim_feature_readiness():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["stage"] == "sandip-sprint-1"
        paths = client.get("/api/openapi.json").json()["paths"]
        assert '/api/v1/auth/login' in paths
        assert '/api/v1/patients/{patient_id}/circle' in paths
        assert not any('/doses' in path for path in paths)


def test_missing_routes_have_shared_error_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v1/not-implemented")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_validation_error_omits_sensitive_raw_input():
    test_app = FastAPI()
    test_app.exception_handlers.update(app.exception_handlers)

    class Payload(BaseModel):
        number: int

    @test_app.post("/validate")
    def validate(payload: Payload):
        return payload

    with TestClient(test_app) as client:
        response = client.post("/validate", json={"number": "private-health-data"})
        assert response.status_code == 422
        assert "private-health-data" not in response.text
        assert response.json()["error"]["details"][0]["field"] == "body.number"
