from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta, time as dt_time, date
from MySQLdb.cursors import DictCursor

user_dashboard_bp = Blueprint('user_dashboard_bp', __name__)

def convert_mysql_objects(obj):
    if isinstance(obj, timedelta):
        total_seconds = int(obj.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    elif isinstance(obj, (datetime, date, dt_time)):
        return obj.isoformat()

    elif isinstance(obj, list):
        return [convert_mysql_objects(x) for x in obj]

    elif isinstance(obj, dict):
        return {k: convert_mysql_objects(v) for k, v in obj.items()}

    return obj

@user_dashboard_bp.route('/user_dashboard', methods=['GET'])
def customer_dashboard():
    customer_id = request.args.get('customer_id')

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Get user profile
        cursor.execute("""
            SELECT user_id, first_name, last_name, email, phone_number, gender, birth_year, created_at
            FROM users
            WHERE user_id = %s AND role = 'customer'
        """, (customer_id,))
        profile = cursor.fetchone()
        if profile:
            profile = dict(profile)


        if not profile:
            return jsonify({'error': 'Customer not found'}), 404

        # Upcoming appointments
        cursor.execute("""
            SELECT a.appointment_id, a.appointment_date, a.start_time, a.end_time, a.status,
                   s.name AS salon_name, sv.name AS service_name
            FROM appointments a
            JOIN salons s ON a.salon_id = s.salon_id
            JOIN services sv ON a.service_id = sv.service_id
            WHERE a.customer_id = %s AND a.status = 'booked' AND a.appointment_date >= CURDATE()
            ORDER BY a.appointment_date ASC
        """, (customer_id,))
        upcoming_appointments = [dict(row) for row in cursor.fetchall()]

        # Past appointments
        cursor.execute("""
            SELECT a.appointment_id, a.appointment_date, a.start_time, a.end_time, a.status,
                   s.name AS salon_name, sv.name AS service_name
            FROM appointments a
            JOIN salons s ON a.salon_id = s.salon_id
            JOIN services sv ON a.service_id = sv.service_id
            WHERE a.customer_id = %s AND a.appointment_date < CURDATE()
            ORDER BY a.appointment_date DESC
        """, (customer_id,))
        past_appointments = [dict(row) for row in cursor.fetchall()]

        # Payment history
        cursor.execute("""
            SELECT i.invoice_id, i.issued_date, i.total_amount, i.status,
                   s.name AS salon_name
            FROM invoices i
            LEFT JOIN appointments a ON i.appointment_id = a.appointment_id
            LEFT JOIN salons s ON a.salon_id = s.salon_id
            WHERE i.customer_id = %s
            ORDER BY i.issued_date DESC
        """, (customer_id,))
        payment_history = [dict(row) for row in cursor.fetchall()]

        # Verified salons and employees
        cursor.execute("""
            SELECT s.salon_id, s.name AS salon_name, s.email, s.phone_number,
                   e.employee_id, e.first_name AS employee_first_name, e.last_name AS employee_last_name
            FROM salons s
            LEFT JOIN employees e ON s.salon_id = e.salon_id
            WHERE s.is_verified = TRUE
            ORDER BY s.name ASC
        """)
        verified_salons = [dict(row) for row in cursor.fetchall()]

        response_data = {
            'profile': profile,
            'upcoming_appointments': upcoming_appointments,
            'past_appointments': past_appointments,
            'payment_history': payment_history,
            'verified_salons': verified_salons
        }

        return jsonify(convert_mysql_objects(response_data)), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()
