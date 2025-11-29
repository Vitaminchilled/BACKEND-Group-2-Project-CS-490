import pytest
from unittest.mock import MagicMock, patch
from app import app
from flask import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def mock_mysql():
    cursor = MagicMock()
    cursor.lastrowid = 1
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    cursor.connection = MagicMock()
    cursor.connection.commit = MagicMock()
    mysql = MagicMock()
    mysql.connection.cursor.return_value = cursor
    return mysql, cursor

# /cart/ tests 
def test_view_empty_cart(client):
    with app.app_context():
        mock_mysql_obj, mock_cursor = mock_mysql()
        with patch('cart.current_app') as mock_app:
            mock_app.config = {'MYSQL': mock_mysql_obj}

            response = client.get('/cart/999/999')
            data = json.loads(response.data)
            assert response.status_code == 200
            assert data['cart'] == []
            assert data['message'] == 'Cart is empty'

def test_add_to_cart(client):
    with app.app_context():
        mysql_obj, cursor = mock_mysql()
        cursor.fetchone.side_effect = [None, None]

        with patch('cart.current_app') as mock_app:
            mock_app.config = {'MYSQL': mysql_obj}

            payload = {"customer_id": 1, "salon_id": 1, "product_id": 1, "quantity": 2}
            response = client.post('/cart/add', json=payload)
            data = json.loads(response.data)

            assert response.status_code == 201
            assert 'cart_id' in data
            assert data['message'] == 'Product added to cart'

def test_view_cart_with_items(client):
    with app.app_context():
        mysql_obj, cursor = mock_mysql()
        cursor.fetchone.side_effect = [(1,), None]
        cursor.fetchall.return_value = [(1, 1, 2, 'Shampoo', 10.0, 100)]

        with patch('cart.current_app') as mock_app:
            mock_app.config = {'MYSQL': mysql_obj}

            response = client.get('/cart/1/1')
            data = json.loads(response.data)
            assert response.status_code == 200
            assert len(data['cart']) == 1
            item = data['cart'][0]
            assert item['cart_item_id'] == 1
            assert item['product_id'] == 1
            assert item['quantity'] == 2
            assert item['subtotal'] == 20.0

def test_update_cart_quantity(client):
    with app.app_context():
        mysql_obj, cursor = mock_mysql()
        cursor.fetchall.return_value = [(1, 1, 2, 'Shampoo', 10.0, 100)]

        with patch('cart.current_app') as mock_app:
            mock_app.config = {'MYSQL': mysql_obj}

            payload = {"cart_item_id": 1, "quantity": 5}
            response = client.put('/cart/update', json=payload)
            data = json.loads(response.data)

            assert response.status_code == 200
            assert data['message'] == 'Cart quantity updated'

def test_remove_from_cart(client):
    with app.app_context():
        mysql_obj, cursor = mock_mysql()
        with patch('cart.current_app') as mock_app:
            mock_app.config = {'MYSQL': mysql_obj}

            payload = {"cart_item_id": 1}
            response = client.delete('/cart/remove', json=payload)
            data = json.loads(response.data)
            assert response.status_code == 200
            assert data['message'] == 'Item removed from cart'

def test_update_cart_quantity_to_zero_removes_item(client):
    with app.app_context():
        mysql_obj, cursor = mock_mysql()
        with patch('cart.current_app') as mock_app:
            mock_app.config = {'MYSQL': mysql_obj}

            payload = {"cart_item_id": 1, "quantity": 0}
            response = client.put('/cart/update', json=payload)
            data = json.loads(response.data)
            assert response.status_code == 200
            assert data['message'] == 'Cart item removed'
