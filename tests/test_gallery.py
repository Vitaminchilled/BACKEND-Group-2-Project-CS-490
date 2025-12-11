'''import io
import pytest
from unittest.mock import MagicMock, patch
from app import app
from io import BytesIO


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_gallery_success(client):
    with app.app_context():
        with patch("salon_gallery.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchall.return_value = [
                (1, 10, "/images/img1.jpg", "Desc", None, None)
            ]
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/10/gallery")
            assert response.status_code == 200
            assert b"/images/img1.jpg" in response.data

def test_get_gallery_not_found(client):
    with app.app_context():
        with patch("salon_gallery.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/10/gallery")
            assert response.status_code == 404
            assert b"No images found" in response.data

def test_get_salon_image_success(client):
    with app.app_context():
        with patch("salon_gallery.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchone.return_value = (1, 10, "/images/salon.jpg", None, None)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/10/image")
            assert response.status_code == 200
            assert b"/images/salon.jpg" in response.data

def test_get_employee_image_success(client):
    with app.app_context():
        with patch("salon_gallery.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchone.return_value = (1, 10, 5, "/images/employee.jpg", None, None)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/10/employees/5/image")
            assert response.status_code == 200
            assert b"/images/employee.jpg" in response.data

def test_get_product_image_success(client):
    with app.app_context():
        with patch("salon_gallery.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchone.return_value = (1, 10, 7, "/images/product.jpg", None, None)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/10/products/7/image")
            assert response.status_code == 200
            assert b"/images/product.jpg" in response.data

def test_upload_general_salon_image(client, monkeypatch):
    data = {
        'image': (io.BytesIO(b'my image data'), 'test.jpg'),
        'description': 'General salon image'
    }

    class DummyCursor:
        lastrowid = 1
        def execute(self, query, params=None):
            return
        def fetchone(self):
            return (1,)
        def close(self):
            pass
    class DummyMySQL:
        connection = type('obj', (), {'cursor': lambda self: DummyCursor(), 'commit': lambda self: None})()
    
    monkeypatch.setitem(client.application.config, 'MYSQL', DummyMySQL())

    response = client.post('/salon/1/gallery/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 201
    assert 'Image uploaded successfully' in response.json['message']

def test_upload_employee_image(client, monkeypatch):
    data = {
        'image': (io.BytesIO(b'employee image'), 'employee.jpg'),
        'description': 'Employee photo',
        'employee_id': '1'
    }

    class DummyCursor:
        lastrowid = 2
        def execute(self, query, params=None):
            # Simulate employee belongs to salon
            if 'select employee_id' in query:
                self._result = [(1,)]
            return
        def fetchone(self):
            return (1,)
        def close(self):
            pass
    class DummyMySQL:
        connection = type('obj', (), {'cursor': lambda self: DummyCursor(), 'commit': lambda self: None})()

    monkeypatch.setitem(client.application.config, 'MYSQL', DummyMySQL())
    response = client.post('/salon/1/gallery/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 201
    assert 'Image uploaded successfully' in response.json['message']

def test_upload_product_image(client, monkeypatch):
    data = {
        'image': (io.BytesIO(b'product image'), 'product.jpg'),
        'description': 'Product thumbnail',
        'product_id': '1'
    }
    class DummyCursor:
        lastrowid = 3
        def execute(self, query, params=None):
            # Simulate product belongs to salon
            if 'select product_id' in query:
                self._result = [(1,)]
            return
        def fetchone(self):
            return (1,)
        def close(self):
            pass
    class DummyMySQL:
        connection = type('obj', (), {'cursor': lambda self: DummyCursor(), 'commit': lambda self: None})()

    monkeypatch.setitem(client.application.config, 'MYSQL', DummyMySQL())
    response = client.post('/salon/1/gallery/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 201
    assert 'Image uploaded successfully' in response.json['message']

def test_upload_primary_salon_image(client, monkeypatch):
    data = {
        'image': (io.BytesIO(b'primary image'), 'primary.jpg'),
        'description': 'Primary salon image',
        'is_primary': 'true'
    }

    class DummyCursor:
        lastrowid = 4
        def execute(self, query, params=None):
            return
        def fetchone(self):
            return None
        def close(self):
            pass
    class DummyMySQL:
        connection = type('obj', (), {'cursor': lambda self: DummyCursor(), 'commit': lambda self: None})()

    monkeypatch.setitem(client.application.config, 'MYSQL', DummyMySQL())
    response = client.post('/salon/1/gallery/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 201
    assert 'Image uploaded successfully' in response.json['message']

def test_upload_no_file(client):
    data = {
        'description': 'Missing file'
    }
    response = client.post('/salon/1/gallery/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert 'Image file is required' in response.json['error']

def test_upload_invalid_employee(client, monkeypatch):
    data = {
        'image': (io.BytesIO(b'image'), 'img.jpg'),
        'employee_id': '999'
    }
    class DummyCursor:
        lastrowid = 5
        def execute(self, query, params=None):
            # Simulate employee does NOT belong to salon
            if 'select employee_id' in query:
                self._result = None
            return
        def fetchone(self):
            return None
        def close(self):
            pass

    class DummyMySQL:
        connection = type('obj', (), {'cursor': lambda self: DummyCursor(), 'commit': lambda self: None})()

    monkeypatch.setitem(client.application.config, 'MYSQL', DummyMySQL())
    response = client.post('/salon/1/gallery/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert 'does not belong to salon' in response.json['error']

def test_upload_invalid_product(client, monkeypatch):
    data = {
        'image': (io.BytesIO(b'image'), 'img.jpg'),
        'product_id': '999'
    }
    class DummyCursor:
        lastrowid = 6
        def execute(self, query, params=None):
            if 'select product_id' in query:
                self._result = None
            return
        def fetchone(self):
            return None
        def close(self):
            pass

    class DummyMySQL:
        connection = type('obj', (), {'cursor': lambda self: DummyCursor(), 'commit': lambda self: None})()
    monkeypatch.setitem(client.application.config, 'MYSQL', DummyMySQL())
    response = client.post('/salon/1/gallery/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert 'does not belong to salon' in response.json['error']

def test_update_image_success(client):
    with app.app_context():
        with patch("salon_gallery.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchone.return_value = ("/gallery/old.jpg",)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            data = {
                "description": "New description"
            }

            response = client.put("/salon/gallery/1/update", data=data, content_type='multipart/form-data')
            assert response.status_code == 200
            assert b"Image updated successfully" in response.data

def test_delete_image_success(client):
    with app.app_context():
        with patch("salon_gallery.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchone.return_value = (1, False)
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.delete("/salon/gallery/1/delete")
            assert response.status_code == 200
            assert b"Image deleted successfully" in response.data
'''
