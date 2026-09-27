"""Integration tests for Tests endpoints."""

import uuid
import pytest


class TestListTests:
    def test_list_tests(self, client, sample_test):
        response = client.get("/api/v1/tests")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_tests_pagination(self, client, sample_test):
        response = client.get("/api/v1/tests?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_tests_filter_by_centre(self, client, sample_centre, sample_centre_test):
        response = client.get(f"/api/v1/tests?centre_id={sample_centre.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1


class TestGetTest:
    def test_get_test_success(self, client, sample_test, sample_centre_test):
        response = client.get(f"/api/v1/tests/{sample_test.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_test.name
        assert "centres" in data

    def test_get_test_not_found(self, client):
        response = client.get(f"/api/v1/tests/{uuid.uuid4()}")
        assert response.status_code == 404
