import pytest
from unittest.mock import MagicMock, patch
from app import app  # import your Flask app
from flask import session

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['register_username'] = 'testuser'
            sess['register_password'] = 'hashedpassword'
        yield client

# /register/page tests
def test_register_page_missing_fields(client):
    payload = {"username": "user1", "password": ""}
    response = client.post('/register/page', json=payload)
    data = response.get_json()
    assert response.status_code == 400
    assert 'Missing required fields' in data['error']

def test_register_page_password_mismatch(client):
    payload = {"username": "user1", "password": "123", "password_confirm": "321"}
    response = client.post('/register/page', json=payload)
    data = response.get_json()
    assert response.status_code == 400
    assert 'Passwords do not match' in data['error']

def test_register_page_success(client):
    payload = {"username": "newuser", "password": "12345", "password_confirm": "12345"}
    with app.app_context():
        with patch('register.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.post('/register/page', json=payload)
            data = response.get_json()
            assert response.status_code == 200
            assert data['message'] == 'Proceed to next page'

# /register/customer tests
def test_register_customer_missing_session(client):
    with client.session_transaction() as sess:
        sess.pop('register_username', None)
        sess.pop('register_password', None)

    response = client.post('/register/customer', json={})
    data = response.get_json()
    assert response.status_code == 400
    assert 'Session expired' in data['error']

def test_register_customer_missing_fields(client):
    payload = {"first_name": "John"}  
    response = client.post('/register/customer', json=payload)
    data = response.get_json()
    assert response.status_code == 400
    assert 'Missing required fields' in data['error']

def test_register_customer_duplicate_email(client):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "existing@example.com",
        "phone_number": "1234567890",
        "gender": "Male",
        "birth_year": 1990
    }
    with app.app_context():
        with patch('register.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.side_effect = [True, None]
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.post('/register/customer', json=payload)
            data = response.get_json()
            assert response.status_code == 400
            assert 'email is already in use' in data['error']

def test_register_customer_success(client):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone_number": "1234567890",
        "gender": "Male",
        "birth_year": 1990
    }
    with app.app_context():
        with patch('register.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None  # no duplicates
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.post('/register/customer', json=payload)
            data = response.get_json()
            assert response.status_code == 201
            assert 'User registered successfully' in data['message']

# /register/salon tests
def test_register_salon_missing_fields(client):
    payload = {"first_name": "Alice"}
    response = client.post('/register/salon', json=payload)
    data = response.get_json()
    assert response.status_code == 400
    assert 'Missing required fields' in data['error']

def test_register_salon_email_mismatch(client):
    payload = {
        "first_name": "Alice",
        "last_name": "Owner",
        "personal_email": "owner@example.com",
        "personal_email_confirm": "other@example.com",
        "birth_year": 1990,
        "phone_number": "1111111111",
        "gender": "Female",
        "salon_name": "Test Salon",
        "salon_email": "salon@example.com",
        "salon_email_confirm": "salon@example.com",
        "salon_phone_number": "2222222222",
        "salon_address": "123 Main St",
        "salon_city": "City",
        "salon_state": "State",
        "salon_postal_code": "12345",
        "salon_country": "USA",
        "master_tag_ids": [1, 2]
    }
    response = client.post('/register/salon', json=payload)
    data = response.get_json()
    assert response.status_code == 400
    assert 'Emails do not match' in data['error']
'''
def test_register_salon_success(client):
    payload = {
        "first_name": "Alice",
        "last_name": "Owner",
        "personal_email": "owner@example.com",
        "personal_email_confirm": "owner@example.com",
        "birth_year": 1990,
        "phone_number": "1111111111",
        "gender": "Female",
        "salon_name": "Test Salon",
        "salon_email": "salon@example.com",
        "salon_email_confirm": "salon@example.com",
        "salon_phone_number": "2222222222",
        "salon_address": "123 Main St",
        "salon_city": "City",
        "salon_state": "State",
        "salon_postal_code": "12345",
        "salon_country": "USA",
        "master_tag_ids": [1, 2]
    }
    with app.app_context():
        with patch('register.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.post('/register/salon', json=payload)
            data = response.get_json()
            assert response.status_code == 201
            assert 'Salon registered successfully' in data['message']
'''
