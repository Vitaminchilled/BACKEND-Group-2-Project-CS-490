import pytest
from unittest.mock import MagicMock, patch
from app import app 
from datetime import datetime

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# /salon/<int:salon_id>/promotion tests
def test_get_active_promotions_success(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()

            mock_cursor.fetchall.return_value = [
                (1, "Winter Sale", "50% off", datetime(2025, 1, 1), datetime(2025, 1, 31), "WINTER50", "50%")
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.get("/salon/1/promotions")
            data = res.get_json()

            assert res.status_code == 200
            assert data["active_promotions"][0]["name"] == "Winter Sale"

def test_get_active_promotions_not_found(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.get("/salon/1/promotions")
            data = res.get_json()

            assert res.status_code == 404
            assert "No active promotions" in data["message"]

def test_get_active_promotions_error(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.side_effect = Exception("DB error")
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.get("/salon/1/promotions")
            assert res.status_code == 500

def test_get_all_promotions_success(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                (1, "Black Friday", "Big sale", datetime(2025, 11, 1),
                 datetime(2025, 11, 30), "BLACK50", "$10")
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.get("/salon/1/promotions/all")
            assert res.status_code == 200
            assert res.get_json()["promotions"][0]["promo_code"] == "BLACK50"

def test_get_all_promotions_not_found(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [] 

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.get("/salon/1/promotions/all")
            assert res.status_code == 404

def test_get_all_promotions_error(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.side_effect = Exception("fail")
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.get("/salon/1/promotions/all")
            assert res.status_code == 500

def test_create_promotion_missing_fields(client):
    with app.app_context():
        res = client.post("/salon/1/promotions", json={
            "name": "Sale" 
        })
        assert res.status_code == 400
        assert "Missing required fields" in res.get_json()["error"]

def test_create_promotion_success(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = 10

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            payload = {
                "name": "Spring Sale",
                "description": "10% off",
                "start_date": "2025-03-01",
                "end_date": "2025-03-31",
                "promo_code": "SPR10",
                "discount_value": 10,
                "is_percentage": True
            }

            res = client.post("/salon/1/promotions", json=payload)
            data = res.get_json()

            assert res.status_code == 201
            assert data["promo_id"] == 10


def test_create_promotion_error(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.side_effect = Exception("insert error")
            mock_app.config = {"MYSQL": mock_mysql}

            payload = {
                "name": "Sale",
                "start_date": "2025-01-01",
                "end_date": "2025-01-10",
                "promo_code": "SALE",
                "discount_value": 5
            }

            res = client.post("/salon/1/promotions", json=payload)
            assert res.status_code == 500

def test_edit_promotion_missing_fields(client):
    with app.app_context():
        res = client.put("/promotions/1", json={"name": "Only name"})
        assert res.status_code == 400

def test_edit_promotion_not_found(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 0  

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            payload = {
                "name": "Updated",
                "description": "desc",
                "start_date": "2025-01-01",
                "end_date": "2025-01-10",
                "promo_code": "UPD",
                "discount_value": 20
            }

            res = client.put("/promotions/999", json=payload)
            assert res.status_code == 404

def test_edit_promotion_success(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            payload = {
                "name": "Updated Name",
                "description": "New desc",
                "start_date": "2025-01-01",
                "end_date": "2025-01-10",
                "promo_code": "NEWCODE",
                "discount_value": 15
            }

            res = client.put("/promotions/1", json=payload)
            assert res.status_code == 200

def test_edit_promotion_error(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.side_effect = Exception("update failed")
            mock_app.config = {"MYSQL": mock_mysql}

            payload = {
                "name": "Updated",
                "description": "desc",
                "start_date": "2025-01-01",
                "end_date": "2025-01-10",
                "promo_code": "SALE",
                "discount_value": 5
            }

            res = client.put("/promotions/1", json=payload)
            assert res.status_code == 500

def test_disable_promotion_success(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.put("/promotions/3/disable")
            assert res.status_code == 200

def test_disable_promotion_error(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.side_effect = Exception("disable error")
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.put("/promotions/3/disable")
            assert res.status_code == 500

def test_enable_promotion_not_found(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None 

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.put("/promotions/5/enable")
            assert res.status_code == 404

def test_enable_promotion_already_active(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,) 

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.put("/promotions/5/enable")
            assert res.status_code == 200
            assert "already active" in res.get_json()["message"]

def test_enable_promotion_success(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (0,) 

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.put("/promotions/9/enable")
            assert res.status_code == 200

def test_enable_promotion_error(client):
    with app.app_context():
        with patch("promotions.current_app") as mock_app:
            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.side_effect = Exception("failed enable")
            mock_app.config = {"MYSQL": mock_mysql}

            res = client.put("/promotions/9/enable")
            assert res.status_code == 500