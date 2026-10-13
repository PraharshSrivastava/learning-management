from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import document_drafts
from app.core.exceptions import install_exception_handlers
from app.core.settings import settings


def client(monkeypatch, enabled):
    monkeypatch.setattr(settings, "document_builder_workflow_enabled", enabled)
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(document_drafts.router)
    return TestClient(app)


def test_workflow_disabled_by_default_without_touching_database(monkeypatch):
    api = client(monkeypatch, False)
    assert api.get("/api/document-builder/drafts").status_code == 404


def test_unknown_fields_are_rejected_before_persistence(monkeypatch):
    api = client(monkeypatch, True)
    response = api.post(
        "/api/document-builder/drafts",
        json={
            "entryMode": "blank",
            "trainer_id": "attacker",
            "revision": 42,
        },
    )
    assert response.status_code == 422


def test_feature_enabled_still_requires_trainer_identity(monkeypatch):
    api = client(monkeypatch, True)
    response = api.get("/api/document-builder/drafts")
    assert response.status_code == 401


def test_client_cannot_claim_image_assets_or_generation_status(monkeypatch):
    api = client(monkeypatch, True)
    monkeypatch.setattr(document_drafts, "_owner", lambda *args: "owner")
    for module in (
        {"id": "module_1", "title": "Topic", "status": "generating"},
        {
            "id": "module_1",
            "title": "Topic",
            "blocks": [{"id": "image_1", "type": "image", "assetId": "someone_elses_asset"}],
        },
    ):
        response = api.post(
            "/api/document-builder/drafts", json={"entryMode": "blank", "modules": [module]}
        )
        assert response.status_code == 422
