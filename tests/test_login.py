import pytest
from unittest.mock import MagicMock, patch
from app import app 
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# /login tests
def test_login_missing_fields(client):
    response = client.post('/login', json={"username": ""})
    data = response.get_json()
    assert response.status_code == 400
    assert 'Missing required fields' in data['error']


def test_login_invalid_username(client):
    with app.app_context():
        with patch('login.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None 
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.post('/login', json={"username": "wrong", "password": "123"})
            data = response.get_json()
            assert response.status_code == 401
            assert 'Invalid username or password' in data['error']


def test_login_invalid_password(client):
    hashed_pw = generate_password_hash("correctpw")
    with app.app_context():
        with patch('login.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1, hashed_pw)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.post('/login', json={"username": "user1", "password": "wrongpw"})
            data = response.get_json()
            assert response.status_code == 401
            assert 'Invalid username or password' in data['error']

'''
def test_login_success(client):
    hashed_pw = generate_password_hash("mypassword")
    with app.app_context():
        with patch('login.current_app') as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (42, hashed_pw)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {'MYSQL': mock_mysql}

            response = client.post('/login', json={"username": "user1", "password": "mypassword"})
            data = response.get_json()
            assert response.status_code == 200
            assert 'Login successful' in data['message']

            with client.session_transaction() as sess:
                assert sess['user_id'] == 42
                assert sess['username'] == "user1"
'''
# /auth/status tests
def test_auth_status_authenticated(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 42
        sess['username'] = "user1"

    response = client.get('/auth/status')
    data = response.get_json()
    assert response.status_code == 200
    assert data['authenticated'] is True
    assert data['username'] == "user1"

def test_auth_status_unauthenticated(client):
    response = client.get('/auth/status')
    data = response.get_json()
    assert response.status_code == 200
    assert data['authenticated'] is False

# /logout tests
def test_logout(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 42
        sess['username'] = "user1"

    response = client.post('/logout')
    data = response.get_json()
    assert response.status_code == 200
    assert 'Logout successful' in data['message']

    with client.session_transaction() as sess:
        assert 'user_id' not in sess
        assert 'username' not in sess
