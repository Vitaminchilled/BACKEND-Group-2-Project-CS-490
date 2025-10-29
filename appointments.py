from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from flask import current_app

appointments_bp = Blueprint('appointments_bp', __name__)

# here is my appointments booking, when calling this function (appointments/book), it'll need the customer, salon and service id
# as well as the appointment dates and notes, this can prolly be changed as we move forward thou.

@appointments_bp.route('/appointments/book', methods=['POST'])
def book_appointment():
    data = request.get_json()

    salon_id = data.get('salon_id')
    employee_id = data.get('employee_id')
    customer_id = data.get('customer_id')
    service_id = data.get('service_id')
    appointment_date = data.get('appointment_date')
    start_time = data.get('start_time')
    notes = data.get('notes', "")

    if not all([salon_id, employee_id, customer_id, service_id, appointment_date, start_time]):
        return jsonify({'error': 'Missing required fields'}), 400

    cursor = current_app.mysql.connection.cursor(dictionary=True)

    # getting the time of the service
    cursor.execute("SELECT duration_minutes FROM services WHERE service_id = %s", (service_id,))
    service = cursor.fetchone()
    if not service:
        cursor.close()
        return jsonify({'error': 'Invalid service ID'}), 400
    duration = timedelta(minutes=service['duration_minutes'])

    # Calc end time of appointment
    try:
        start_dt = datetime.strptime(start_time, "%H:%M:%S")
    except ValueError:
        cursor.close()
        return jsonify({'error': 'Invalid time format. Use HH:MM:SS'}), 400
    end_dt = (start_dt + duration).time()

    # Check if employee is actually working at that time
    cursor.execute("""
        SELECT * FROM time_slots
        WHERE employee_id = %s
          AND salon_id = %s
          AND date = %s
          AND start_time <= %s
          AND end_time >= %s
    """, (employee_id, salon_id, appointment_date, start_time, end_dt))
    if not cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'Employee not available during that time'}), 400

    # Make sure there arent overlapping appointments, HAVENT TESTED THIS YET
    cursor.execute("""
        SELECT * FROM appointments
        WHERE employee_id = %s
          AND salon_id = %s
          AND appointment_date = %s
          AND status IN ('booked', 'confirmed')
          AND (
                (start_time < %s AND end_time > %s) OR
                (start_time >= %s AND start_time < %s)
              )
    """, (employee_id, salon_id, appointment_date, end_dt, start_time, start_time, end_dt))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'Time slot overlaps with another appointment'}), 400

    # putting the appointment into the dataset
    now = datetime.now()
    try:
        cursor.execute("""
            INSERT INTO appointments (customer_id, salon_id, employee_id, service_id,
                                      appointment_date, start_time, end_time, notes,
                                      status, created_at, last_modified)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'booked',%s,%s)
        """, (customer_id, salon_id, employee_id, service_id, appointment_date,
              start_time, end_dt, notes, now, now))
        current_app.mysql.connection.commit()
        return jsonify({'message': 'Appointment booked successfully'}), 201
    except Exception as e:
        current_app.mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# this is the appointments view function, this is the function you'll use when you want to
# get data about appointments, maybe things like viewing appointment history and etc, expecting to make
# a buncha changes to this cuz i want it to work for other functions as well

@appointments_bp.route('/appointments/view', methods=['GET'])
def view_appointments():
    user_role = request.args.get('role') # between customer or salon
    user_id = request.args.get('id')

    if not all([user_role, user_id]):
        return jsonify({'error': 'Missing required parameters'}), 400

    cursor = current_app.mysql.connection.cursor(dictionary=True)

    try:
        if user_role == 'customer':
            cursor.execute("""
                SELECT a.appointment_id, a.appointment_date, a.status,
                       s.name AS salon_name, sv.service_name
                FROM appointments a
                JOIN salons s ON a.salon_id = s.salon_id
                JOIN services sv ON a.service_id = sv.service_id
                WHERE a.customer_id = %s
                ORDER BY a.appointment_date DESC
            """, (user_id,))
        elif user_role == 'salon':
            cursor.execute("""
                SELECT a.appointment_id, a.appointment_date, a.status,
                       u.first_name, u.last_name, sv.service_name
                FROM appointments a
                JOIN users u ON a.customer_id = u.id
                JOIN services sv ON a.service_id = sv.service_id
                WHERE a.salon_id = %s
                ORDER BY a.appointment_date DESC
            """, (user_id,))
        else:
            return jsonify({'error': 'Invalid role specified'}), 400

        appointments = cursor.fetchall()
        return jsonify({'appointments': appointments}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Rescheduling function! this function is going to need the new appointment date ofc.
# ADD ABILITY TO MODIFY THE NOTE of the appointment MAYBE?
# seems like it makes sense plus i think we wanted to be able to do that...

@appointments_bp.route('/appointments/update', methods=['PUT'])
def update_appointment():
    data = request.get_json()
    appointment_id = data.get('appointment_id')
    new_date = data.get('new_date')

    if not all([appointment_id, new_date]):
        return jsonify({'error': 'Missing required fields'}), 400

    cursor = current_app.mysql.connection.cursor()

    try:
        cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s", (appointment_id,))
        if not cursor.fetchone():
            cursor.close()
            return jsonify({'error': 'Appointment not found'}), 404

        query = """
            UPDATE appointments
            SET appointment_date = %s, last_modified = %s
            WHERE appointment_id = %s
        """
        cursor.execute(query, (new_date, datetime.now(), appointment_id))
        current_app.mysql.connection.commit()

        return jsonify({'message': 'Appointment rescheduled successfully'}), 200

    except Exception as e:
        current_app.mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# Just a simple cancelling of the appointments

@appointments_bp.route('/appointments/cancel', methods=['DELETE'])
def cancel_appointment():
    data = request.get_json()
    appointment_id = data.get('appointment_id')

    if not appointment_id:
        return jsonify({'error': 'Missing appointment ID'}), 400

    cursor = current_app.mysql.connection.cursor()

    try:
        cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s", (appointment_id,))
        if not cursor.fetchone():
            cursor.close()
            return jsonify({'error': 'Appointment not found'}), 404

        query = """
            UPDATE appointments
            SET status = %s, last_modified = %s
            WHERE appointment_id = %s
        """
        cursor.execute(query, ('cancelled', datetime.now(), appointment_id))
        current_app.mysql.connection.commit()

        return jsonify({'message': 'Appointment cancelled successfully'}), 200

    except Exception as e:
        current_app.mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# this is a function that yall will call if you need a specific appointment.
# make sure when your calling this that you include the role (customer, owner) and the customer id

@appointments_bp.route('/appointments/<string:role>/<int:entity_id>', methods=['GET'])
def get_appointments(role, entity_id):
    cursor = current_app.mysql.connection.cursor(dictionary=True)

    if role == 'customer' :
        cursor.execute("SELECT * FROM appointments WHERE customer_id = %s ORDER BY appointment_date, start_time", (entity_id))
    elif role == 'salon' :
        cursor.execute("SELECT * FROM appointments WHERE salon_id = %s ORDER BY appointment_date, start_time", (entity_id))
    else:
        cursor.close()
        return jsonify({'error': 'Invalid role entered'}), 400
    
    appointments = cursor.fetchall()
    cursor.close()
    return jsonify(appointments), 200