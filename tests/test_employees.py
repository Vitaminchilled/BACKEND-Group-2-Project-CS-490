import pytest
from unittest.mock import MagicMock
from app import app 
from datetime import timedelta

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context(): 
            yield client

# /salon/<int:salon_id>/employees tests
def test_get_employees(client):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        (1, 'John', 'Doe', 'Stylist', '["Hair", "Makeup"]', 10, 25.0, '2025-01-01')
    ]
    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    res = client.get('/salon/1/employees')
    data = res.get_json()

    assert res.status_code == 200
    assert data['employees'][0]['first_name'] == 'John'
    assert data['employees'][0]['tags'] == ["Hair", "Makeup"]

def test_add_employee(client):
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 1
    mock_cursor.fetchone.side_effect = [(1,), (2,)]

    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    payload = {
        "first_name": "Jane",
        "last_name": "Smith",
        "description": "Stylist",
        "tags": ["Hair", "Makeup"]
    }

    res = client.post('/salon/1/employees', json=payload)
    data = res.get_json()

    assert res.status_code == 201
    assert data['employee_id'] == 1

def test_edit_employee(client):
    mock_cursor = MagicMock()
    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "description": "Senior Stylist",
        "tags": ["Hair", "Makeup", "Nails"]
    }

    res = client.put('/salon/1/employees/1', json=payload)
    data = res.get_json()

    assert res.status_code == 200
    assert data['message'] == 'Employee updated successfully'

def test_delete_employee(client):
    mock_cursor = MagicMock()
    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    res = client.delete('/salon/1/employees/1')
    data = res.get_json()

    assert res.status_code == 200
    assert data['message'] == 'Employee deleted successfully'

def test_add_employee_missing_fields(client):
    payload = {
        "first_name": "Jane"
    }

    res = client.post('/salon/1/employees', json=payload)
    data = res.get_json()

    assert res.status_code == 400
    assert 'Missing required fields' in data['error']

def test_get_employees_no_employees(client):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    res = client.get('/salon/1/employees')
    data = res.get_json()

    assert res.status_code == 200
    assert data['employees'] == []

# /salon/<int:salon_id>/employees/<int:employee_id>/timeslots tests
def test_get_employee_timeslots(client):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        (1, 'Monday', '09:00:00', '10:00:00'),
        (2, 'Wednesday', '13:00:00', '14:00:00')
    ]

    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor
    client.application.config['MYSQL'] = mock_mysql

    res = client.get('/salon/1/employees/1/timeslots')
    data = res.get_json()

    assert res.status_code == 200
    assert data == [{}, {}]

def test_add_employee_timeslot(client):
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 1

    mock_cursor.fetchone.side_effect = [
        (timedelta(hours=9), timedelta(hours=18)),
        None
    ]

    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    payload = {
        "day": "Tuesday",
        "start_time": "10:00:00",
        "end_time": "11:00:00"
    }

    res = client.post('/salon/1/employees/1/timeslots', json=payload)
    data = res.get_json()

    assert res.status_code == 201
    assert data['message'] == "Time slot added successfully"

def test_delete_employee_timeslot(client):
    mock_cursor = MagicMock()
    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    res = client.delete('/salon/1/employees/1/timeslots/1')
    data = res.get_json()

    assert res.status_code == 200
    assert data['message'] == 'Time slot deleted successfully'

# /salon/<int:salon_id>/employees/<int:employee_id>/salaries tests
def get_employee_salary(client):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (25.0,)
    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    res = client.get('/employees/1/salary')
    data = res.get_json()

    assert res.status_code == 200
    assert data['salary'] == 25.0

def set_employee_salary(client):
    mock_cursor = MagicMock()
    mock_mysql = MagicMock()
    mock_mysql.connection.cursor.return_value = mock_cursor

    client.application.config['MYSQL'] = mock_mysql

    payload = {
        "salary": 30.0
    }

    res = client.put('/employees/1/salary', json=payload)
    data = res.get_json()

    assert res.status_code == 200
    assert data['message'] == 'Salary updated successfully'

