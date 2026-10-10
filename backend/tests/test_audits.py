"""
Audit API Endpoint Tests
"""
import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from unittest.mock import AsyncMock

from app.main import create_app
from app.schemas.audit import AuditCreateResponse, AuditListResponse
from app.api.routes.audits import get_audit_service


@pytest.fixture
def app():
    """Create test app."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAuditCreate:
    """Tests for POST /api/audits"""

    @pytest.mark.asyncio
    async def test_create_audit_valid(self, app, client: AsyncClient):
        """Test creating an audit with valid answer and source_text."""
        # Override the dependency
        mock_audit_service = AsyncMock()
        mock_audit_service.create_audit_with_files.return_value = AuditCreateResponse(
            audit_id=uuid4(),
            status="PROCESSING",
            created_at="2026-10-10T12:00:00Z",
        )
        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            response = await client.post(
                "/api/audits",
                data={
                    "answer": "The survey included 500 students.",
                    "source_text": "The survey included 200 students.",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert "audit_id" in data
            assert data["status"] == "PROCESSING"
            assert "created_at" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_audit_empty_answer(self, app, client: AsyncClient):
        """Test creating an audit with empty answer returns 400."""
        mock_audit_service = AsyncMock()
        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            response = await client.post(
                "/api/audits",
                data={
                    "answer": "   ",
                    "source_text": "The survey included 200 students.",
                },
            )

            # FastAPI Form validation returns 422 for empty required fields
            # but our validation catches whitespace-only
            assert response.status_code in (400, 422)
            data = response.json()
            assert "error" in data or "detail" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_audit_missing_source(self, app, client: AsyncClient):
        """Test creating an audit without any source returns 400."""
        mock_audit_service = AsyncMock()
        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            response = await client.post(
                "/api/audits",
                data={
                    "answer": "The survey included 500 students.",
                },
            )

            assert response.status_code == 400
            data = response.json()
            assert "error" in data or "detail" in data
        finally:
            app.dependency_overrides.clear()


class TestAuditList:
    """Tests for GET /api/audits"""

    @pytest.mark.asyncio
    async def test_list_audits_empty(self, app, client: AsyncClient):
        """Test listing audits when none exist."""
        mock_audit_service = AsyncMock()
        mock_audit_service.list_audits.return_value = []
        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            response = await client.get("/api/audits")

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert data["items"] == []
        finally:
            app.dependency_overrides.clear()


class TestAuditGet:
    """Tests for GET /api/audits/{audit_id}"""

    @pytest.mark.asyncio
    async def test_get_audit_not_found(self, app, client: AsyncClient):
        """Test getting a non-existent audit returns 404."""
        mock_audit_service = AsyncMock()
        mock_audit_service.get_audit.return_value = None
        app.dependency_overrides[get_audit_service] = lambda: mock_audit_service

        try:
            fake_id = uuid4()
            response = await client.get(f"/api/audits/{fake_id}")

            assert response.status_code == 404
            data = response.json()
            assert "error" in data or "detail" in data
        finally:
            app.dependency_overrides.clear()