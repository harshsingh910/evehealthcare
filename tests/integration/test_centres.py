"""Integration tests for Centres endpoints."""

import uuid
import pytest


class TestListCentres:
    def test_list_centres(self, client, sample_centre):
        response = client.get("/api/v1/centres")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_list_centres_pagination(self, client, sample_centre):
        response = client.get("/api/v1/centres?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_list_centres_invalid_page_size(self, client):
        response = client.get("/api/v1/centres?page_size=200")
        assert response.status_code == 422

    def test_list_centres_cache_hit(self, client):
        from unittest.mock import patch
        cached_payload = '{"items": [{"id": "00000000-0000-0000-0000-000000000001", "name": "Cached Centre", "location": "Cached City", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}], "page": 1, "page_size": 20, "total": 1, "total_pages": 1}'
        with patch("app.routers.centres.get_cached") as mock_get_cached:
            mock_get_cached.return_value = cached_payload
            response = client.get("/api/v1/centres")
            assert response.status_code == 200
            data = response.json()
            assert data["items"][0]["name"] == "Cached Centre"



class TestGetCentre:
    def test_get_centre_success(self, client, sample_centre, sample_centre_test):
        response = client.get(f"/api/v1/centres/{sample_centre.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_centre.name
        assert "tests" in data
        assert len(data["tests"]) >= 1

    def test_get_centre_not_found(self, client):
        response = client.get(f"/api/v1/centres/{uuid.uuid4()}")
        assert response.status_code == 404


class TestGetCentreTests:
    def test_get_centre_tests(self, client, sample_centre, sample_centre_test):
        response = client.get(f"/api/v1/centres/{sample_centre.id}/tests")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "price" in data[0]

    def test_get_centre_tests_not_found(self, client):
        response = client.get(f"/api/v1/centres/{uuid.uuid4()}/tests")
        assert response.status_code == 404
