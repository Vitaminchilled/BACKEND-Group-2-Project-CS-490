import pytest
from unittest.mock import MagicMock, patch
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# /loyalty/<int:salon_id> tests
def test_get_active_loyalty(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {"name": "New Customer Discount", "points_required": 50, "tags": "haircut, fade"}
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/loyalty/1")
            data = response.get_json()

            assert response.status_code == 200
            assert data[0]["name"] == "New Customer Discount"

def test_get_all_loyalty(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {"name": "Birthday Deal", "points_required": 100, "tags": "birthday", "discount_display": "10%"}
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/loyalty/viewall/2")
            data = response.get_json()

            assert response.status_code == 200
            assert data[0]["name"] == "Birthday Deal"

def test_add_loyalty(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [5]  # mock tag_id
            mock_cursor.lastrowid = 10

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor

            mock_app.config = {"MYSQL": mock_mysql}

            payload = {
                "name": "Holiday Savings",
                "tag_names": ["winter"],
                "points_required": 120,
                "discount_value": 20,
                "is_percentage": True,
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }

            response = client.post("/loyalty/1", json=payload)
            data = response.get_json()

            assert response.status_code == 201
            assert data["message"] == "Loyalty program added successfully"

            mock_mysql.connection.commit.assert_called_once()

def test_add_loyalty_missing_fields(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:
            mock_app.config = {"MYSQL": MagicMock()}

            payload = {"name": "Deal"}  # missing fields
            response = client.post("/loyalty/1", json=payload)

            assert response.status_code == 400
            assert "Missing required fields" in response.get_json()["error"]

def test_edit_loyalty(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [3]   # tag_id for updated tags

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor

            mock_app.config = {"MYSQL": mock_mysql}

            payload = {
                "name": "Updated Deal",
                "tag_names": ["fade"],
                "points_required": 80,
                "discount_value": 15,
                "is_percentage": False,
                "start_date": "2025-01-01",
                "end_date": "2025-06-01"
            }

            response = client.put("/loyalty/10", json=payload)
            data = response.get_json()

            assert response.status_code == 200
            assert data["message"] == "Loyalty program updated successfully"
            mock_mysql.connection.commit.assert_called_once()

def test_disable_loyalty(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_mysql = MagicMock()
            mock_cursor = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor

            mock_app.config = {"MYSQL": mock_mysql}

            response = client.patch("/loyalty/10/disable")
            data = response.get_json()

            assert response.status_code == 200
            assert data["message"] == "Loyalty program disabled"
            mock_mysql.connection.commit.assert_called_once()

def test_enable_loyalty(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_mysql = MagicMock()
            mock_cursor = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor

            mock_app.config = {"MYSQL": mock_mysql}

            response = client.patch("/loyalty/viewall/10/enable")
            data = response.get_json()

            assert response.status_code == 200
            assert data["message"] == "Loyalty program enabled"
            mock_mysql.connection.commit.assert_called_once()

# /loyalty/<int:salon_id>/points/<int:customer_id> tests
def test_get_customer_points(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [150, 40, 110]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor

            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/loyalty/1/points/5")
            data = response.get_json()

            assert response.status_code == 200
            assert data["available_points"] == 110

def test_claim_voucher(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_cursor = MagicMock()

            # Customer has 200 points
            mock_cursor.fetchone.side_effect = [
                [200],   # available points
                [150]    # points_required
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor

            mock_app.config = {"MYSQL": mock_mysql}

            payload = {"customer_id": 1, "loyalty_program_id": 10}

            response = client.post("/loyalty/1/claim", json=payload)
            data = response.get_json()

            assert response.status_code == 201
            assert data["message"] == "Voucher claimed successfully"
            mock_mysql.connection.commit.assert_called_once()

def test_get_vouchers(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {"name": "Salon A", "discount_display": "$10"}
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor

            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/loyalty/5/vouchers")
            data = response.get_json()

            assert response.status_code == 200
            assert data[0]["discount_display"] == "$10"

def test_claim_voucher_not_enough_points(client):
    with app.app_context():
        with patch("loyalty.current_app") as mock_app:

            mock_cursor = MagicMock()

            mock_cursor.fetchone.side_effect = [
                [20],  # customer has only 20 points
                [100]  # loyalty requires 100
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = mock_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            payload = {"customer_id": 1, "loyalty_program_id": 5}

            response = client.post("/loyalty/1/claim", json=payload)
            assert response.status_code == 400
