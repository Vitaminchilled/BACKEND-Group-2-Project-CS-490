import pytest
from unittest.mock import MagicMock, patch
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# /salon/<int:salon_id>/reviews tests 
def test_get_reviews_success(client):
    with app.app_context():
        with patch("reviews.current_app") as mock_app:

            # Salon exists
            salon_cursor = MagicMock()
            salon_cursor.fetchone.side_effect = [
                (1, 10),
                (3,), 
            ]

            review_row = (
                1, 1, 20, 5, "Great!", None, "2023-01-01",
                '[{"reply_id":1,"user_id":10,"first_name":"Sam","last_name":"Owner","message":"Thanks!","created_at":"2023"}]',
                "John", "Doe", 20
            )
            salon_cursor.fetchall.return_value = [review_row]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = salon_cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/1/reviews")
            data = response.get_json()

            assert response.status_code == 200
            assert data["review_count"] == 3
            assert data["reviews"][0]["comment"] == "Great!"
            assert data["reviews"][0]["replies"][0]["user"] == "Owner"

def test_get_reviews_not_found(client):
    with app.app_context():
        with patch("reviews.current_app") as mock_app:

            cursor = MagicMock()
            cursor.fetchone.return_value = None

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/999/reviews")
            assert response.status_code == 404

def test_recent_three(client):
    with app.app_context():
        with patch("reviews.current_app") as mock_app:

            cursor = MagicMock()
            cursor.fetchall.return_value = [
                ("John", "D.", 5, "Excellent"),
                ("Jane", "R.", 4, "Good"),
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/1/dashboard/reviews")
            data = response.get_json()

            assert response.status_code == 201
            assert len(data["reviews"]) == 2

def test_recent_three_none(client):
    with app.app_context():
        with patch("reviews.current_app") as mock_app:

            cursor = MagicMock()
            cursor.fetchall.return_value = []

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.get("/salon/1/dashboard/reviews")
            data = response.get_json()

            assert response.status_code == 201
            assert data["reviews"] == []

def test_post_review_appointment_not_found(client):
    with app.app_context():
        with patch("reviews.current_app"), \
             client.session_transaction() as sess:

            sess["user_id"] = 5

        with patch("reviews.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchone.return_value = None 

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.post("/appointments/1/review", json={
                "rating": 5, "comment": "Nice"
            })

            assert response.status_code == 500

def test_post_review_already_exists(client):
    with app.app_context():
        with client.session_transaction() as sess:
            sess["user_id"] = 20

        with patch("reviews.current_app") as mock_app:

            cursor = MagicMock()
            cursor.fetchone.side_effect = [
                (1, 20, "completed"),
                (1,),                  
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.post("/appointments/1/review", json={
                "rating": 5, "comment": "Good"
            })

            assert response.status_code == 400
            assert b"Review already exists" in response.data

def test_post_review_success(client):
    with app.app_context():
        with client.session_transaction() as sess:
            sess["user_id"] = 20

        with patch("reviews.current_app") as mock_app:
            cursor = MagicMock()
            cursor.fetchone.side_effect = [
                (1, 20, "completed"), 
                None,                 
            ]

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_mysql.connection.commit.return_value = None
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.post("/appointments/1/review", json={
                "rating": 5, "comment": "Perfect!"
            })

            assert response.status_code == 201
            assert b"Review posted successfully" in response.data

# /reviews/<int:review_id>/reply tests
def test_post_reply_success(client):
    with app.app_context():
        with client.session_transaction() as sess:
            sess["user_id"] = 50

        with patch("reviews.current_app") as mock_app:

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = MagicMock()
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.post("/reviews/1/reply", json={
                "reply": "Thank you!"
            })

            assert response.status_code == 201
            assert b"Reply posted successfully" in response.data

def test_delete_review_success(client):
    with app.app_context():
        with client.session_transaction() as sess:
            sess["user_id"] = 20
            sess["role"] = "admin"

        with patch("reviews.current_app") as mock_app:

            cursor = MagicMock()
            cursor.fetchone.return_value = (20,)

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.delete("/reviews/1")

            assert response.status_code == 200
            assert b"Review deleted successfully" in response.data

def test_delete_reply_success(client):
    with app.app_context():
        with client.session_transaction() as sess:
            sess["user_id"] = 20
            sess["role"] = "admin"

        with patch("reviews.current_app") as mock_app:

            cursor = MagicMock()
            cursor.fetchone.return_value = (20,)  # reply owner

            mock_mysql = MagicMock()
            mock_mysql.connection.cursor.return_value = cursor
            mock_app.config = {"MYSQL": mock_mysql}

            response = client.delete("/reviews/reply/1")

            assert response.status_code == 200
            assert b"Reply deleted successfully" in response.data
