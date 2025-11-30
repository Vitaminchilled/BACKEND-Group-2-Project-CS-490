import pytest
from unittest.mock import MagicMock, patch
from app import app
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# /salon/<int:salon_id>/services tests 
def test_get_services(client):
    with app.app_context():
        with patch('services.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                (1, 'Haircut', '["Tag1","Tag2"]', 'Basic haircut', 30, 25.0, True)
            ]
            mock_cursor.fetchone.side_effect = [(1,), None] 
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.get("/salon/1/services")
            data = response.get_json()

            assert response.status_code == 200
            assert "services" in data
            service = data['services'][0]
            assert service['name'] == 'Haircut'
            assert service['tags'] == ["Tag1", "Tag2"]
            assert service['price'] == 25.0


def test_get_services_salon_not_found(client):
    with app.app_context():
        with patch('services.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None 
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.get("/salon/999/services")
            data = response.get_json()

            assert response.status_code == 404
            assert "Salon not found" in data['error']

def test_add_service(client):
    with app.app_context():
        with patch('services.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            payload = {
                "tags": ["Tag1"],
                "name": "Hair Coloring",
                "description": "Full color",
                "duration_minutes": 60,
                "price": 50.0
            }

            response = client.post("/salon/1/services/add", json=payload)
            data = response.get_json()

            mock_cursor.execute.assert_called()
            mock_mysql.connection.commit.assert_called_once()
            assert response.status_code == 201
            assert data['message'] == "Service added successfully"


def test_add_service_missing_fields(client):
    payload = {"name": "Haircut"} 
    response = client.post("/salon/1/services/add", json=payload)
    data = response.get_json()
    assert response.status_code == 400
    assert "Missing required fields" in data['error']

def test_edit_service(client):
    with app.app_context():
        with patch('services.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            payload = {
                "tags": ["Tag1"],
                "name": "Haircut Updated",
                "description": "Updated desc",
                "duration_minutes": 45,
                "price": 30.0,
                "is_active": True
            }

            response = client.put("/salon/1/services/1/edit", json=payload)
            data = response.get_json()

            mock_cursor.execute.assert_called()
            mock_mysql.connection.commit.assert_called_once()
            assert response.status_code == 200
            assert data['message'] == "Service updated successfully"


def test_edit_service_missing_fields(client):
    payload = {"name": "Haircut"}  # missing required fields
    response = client.put("/salon/1/services/1/edit", json=payload)
    data = response.get_json()
    assert response.status_code == 400
    assert "Missing required fields" in data['error']

def test_delete_service(client):
    with app.app_context():
        with patch('services.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (2,)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.delete("/salon/1/services/1")
            data = response.get_json()

            assert mock_cursor.execute.call_count >= 2
            mock_mysql.connection.commit.assert_called_once()
            assert response.status_code == 200
            assert data['message'] == "Service deleted successfully"


def test_delete_service_last_instance(client):
    with app.app_context():
        with patch('services.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,) 
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.delete("/salon/1/services/1")
            data = response.get_json()

            assert response.status_code == 409
            assert "Cannot delete last instance" in data['error']
