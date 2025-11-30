import pytest
from unittest.mock import MagicMock, patch
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# /products//<int:product_id> tests
def test_view_products(client):
    with app.app_context():
        with patch('products.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {"product_id": 1, "name": "Gel", "price": 9.99}
            ]
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.get("/products/view?salon_id=1")
            data = response.get_json()

            assert response.status_code == 200
            assert "products" in data
            assert data['products'][0]['name'] == "Gel"

def test_add_product(client):
    with app.app_context():
        with patch('products.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            payload = {
                "salon_id": 1,
                "name": "Shampoo",
                "price": 12.5
            }

            response = client.post("/products", json=payload)
            data = response.get_json()

            mock_cursor.execute.assert_called_once()
            mock_mysql.connection.commit.assert_called_once()
            assert response.status_code == 201
            assert data['message'] == "Product added successfully"

def test_update_product(client):
    with app.app_context():
        with patch('products.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"salon_id": 1}
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            payload = {
                "salon_id": 1,
                "name": "Updated Shampoo",
                "price": 15.0
            }

            response = client.put("/products/10", json=payload)
            data = response.get_json()
            assert mock_cursor.execute.call_count >= 2
            mock_mysql.connection.commit.assert_called_once()
            assert response.status_code == 200
            assert data['message'] == "Product updated successfully"

def test_delete_product(client):
    with app.app_context():
        with patch('products.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"salon_id": 1}
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.delete("/products/delete/10?salon_id=1")
            data = response.get_json()
            
            assert mock_cursor.execute.call_count >= 2
            mock_mysql.connection.commit.assert_called_once()
            assert response.status_code == 200
            assert data['message'] == "Product deleted successfully"

def test_add_product_missing_fields(client):
    payload = {"salon_id": 1, "name": ""}
    response = client.post("/products", json=payload)
    data = response.get_json()
    assert response.status_code == 400
    assert 'Missing required fields' in data['error']

def test_update_product_unauthorized(client):
    with app.app_context():
        with patch('products.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"salon_id": 2}  # Different salon
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            payload = {"salon_id": 1, "name": "Hack"}
            response = client.put("/products/10", json=payload)
            data = response.get_json()

            assert response.status_code == 403
            assert "Unauthorized" in data['error']

def test_update_product_no_fields(client):
    with app.app_context():
        with patch('products.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"salon_id": 1}
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            payload = {"salon_id": 1}  # No fields to update
            response = client.put("/products/10", json=payload)
            data = response.get_json()

            assert response.status_code == 401
            assert "No update fields provided" in data['error']

def test_delete_product_unauthorized(client):
    with app.app_context():
        with patch('products.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"salon_id": 2}  # Different salon
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.delete("/products/delete/10?salon_id=1")
            data = response.get_json()

            assert response.status_code == 403
            assert "Unauthorized" in data['error']

def test_delete_product_missing_salon_id(client):
    response = client.delete("/products/delete/10")
    data = response.get_json()
    assert response.status_code == 400
    assert "Missing salon_id" in data['error']