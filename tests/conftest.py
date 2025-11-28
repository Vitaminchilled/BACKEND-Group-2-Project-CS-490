import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        # Pre-populate session for next-page routes
        with client.session_transaction() as sess:
            sess['register_username'] = 'testuser'
            sess['register_password'] = 'hashedpassword'
        yield client
