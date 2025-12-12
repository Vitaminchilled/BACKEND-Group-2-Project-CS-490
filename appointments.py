from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta, time as dt_time, date
from MySQLdb.cursors import DictCursor
from utils.logerror import log_error
from flask import session

appointments_bp = Blueprint('appointments_bp', __name__)

# THIS FUNCTION IS SUPER IMPROTANT: some of the time values in the data for some reason returns
# timedelta, so this function below converts that to something that can be manipulated and etc.
def timedelta_to_time(td):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return dt_time(hour=hours, minute=minutes, second=seconds)

# here is my appointments booking, when calling this function (appointments/book), it'll need the customer, salon and service id
# as well as the appointment dates and notes, this can prolly be changed as we move forward thou.
# add extra function to add image to appointment
@appointments_bp.route('/appointments/book', methods=['POST'])
def book_appointment():
    """
    Book a new appointment
    ---
    tags:
      - Appointments
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
          salon_id:
            type: integer
          employee_id:
            type: integer
          customer_id:
            type: integer
          service_id:
            type: integer
          appointment_date:
            type: string
          start_time:
            type: string
          notes:
            type: string
    responses:
      201:
        description: Appointment booked
      400:
        description: Missing or invalid fields
      500:
        description: Internal server error
    """
    data = request.get_json()

    salon_id = data.get('salon_id')
    employee_id = data.get('employee_id')
    customer_id = data.get('customer_id')
    service_id = data.get('service_id')
    appointment_date = data.get('appointment_date')     # has to be in this format: YYYY-MM-DD
    start_time = data.get('start_time')                 # time has to be in this format: HH:MM:SS
    notes = data.get('notes', "")

    if not all([salon_id, employee_id, customer_id, service_id, appointment_date, start_time]):
        return jsonify({'error': 'Missing required fields'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # gets service duration
        cursor.execute("SELECT duration_minutes FROM services WHERE service_id = %s", (service_id,))
        service = cursor.fetchone()
        if not service:
            return jsonify({'error': 'Invalid service ID'}), 400

        duration = timedelta(minutes=service['duration_minutes'])

        # Get start date
        try:
            start_dt = datetime.strptime(f"{appointment_date} {start_time}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return jsonify({'error': 'Invalid date or time format'}), 400

        # Calc end date
        end_dt = start_dt + duration
        end_time_str = end_dt.strftime("%H:%M:%S")

        # get the day name (ex. monday, tuesday, wednesday, etc)
        day_name = start_dt.strftime("%A")

        # checks employee schedule, prevent overlap/employee not avaliable
        cursor.execute("""
            SELECT start_time, end_time 
            FROM time_slots
            WHERE employee_id = %s AND salon_id = %s
              AND day = %s AND is_available = TRUE
        """, (employee_id, salon_id, day_name))
        schedule = cursor.fetchone()

        if not schedule:
            return jsonify({'error': f'Employee is not scheduled to work on {day_name}'}), 400

        # IMPORTANT: Convert schedule times to datetime.time 
        schedule_start_time = schedule['start_time']
        schedule_end_time = schedule['end_time']

        if isinstance(schedule_start_time, timedelta):
            schedule_start_time = timedelta_to_time(schedule_start_time)
        if isinstance(schedule_end_time, timedelta):
            schedule_end_time = timedelta_to_time(schedule_end_time)

        schedule_start_dt = datetime.combine(start_dt.date(), schedule_start_time)
        schedule_end_dt = datetime.combine(start_dt.date(), schedule_end_time)

        if not (schedule_start_dt <= start_dt < schedule_end_dt):
            return jsonify({'error': 'Requested time is outside working hours'}), 400

        if not (start_dt < end_dt <= schedule_end_dt):
            return jsonify({'error': 'Service duration extends beyond working hours'}), 400

        # Make sure no overlapping
        cursor.execute("""
            SELECT 1 FROM appointments
            WHERE employee_id = %s
              AND salon_id = %s
              AND appointment_date = %s
              AND status IN ('booked', 'confirmed')
              AND (
                    (start_time < %s AND end_time > %s) OR
                    (start_time >= %s AND start_time < %s)
                  )
            LIMIT 1
        """, (employee_id, salon_id, appointment_date, end_time_str, start_time, start_time, end_time_str))
        overlap = cursor.fetchone()

        if overlap:
            return jsonify({'error': 'Time slot overlaps with another appointment'}), 400

        cursor.execute("""
            SELECT slot_id
            FROM time_slots
            WHERE salon_id = %s AND employee_id = %s AND day = %s AND start_time <= %s AND end_time >= %s AND is_available = TRUE
            LIMIT 1
        """, (employee_id, salon_id, day_name, start_time, end_time_str))

        time_slot_id = cursor.fetchone()

        if not time_slot_id:
            return jsonify({'error': 'No matching time slot found'}), 400

        time_slot_id = time_slot_id['slot_id']

        # Insert into appoint
        now = datetime.now()
        cursor.execute("""
            INSERT INTO appointments (
                customer_id, salon_id, employee_id, service_id, time_slot_id,
                appointment_date, start_time, end_time, notes,
                status, created_at, last_modified
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'booked',%s,%s)
        """, (customer_id, salon_id, employee_id, service_id, time_slot_id,
              appointment_date, start_time, end_time_str, notes, now, now))

        mysql.connection.commit()

        return jsonify({
            'message': 'Appointment booked successfully',
            'appointment_date': appointment_date,
            'start_time': start_time,
            'end_time': end_time_str,
            'employee_id': employee_id
        }), 201

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()

# just a debugger for me/ testing
@appointments_bp.route('/debug-test', methods=['GET'])
def debug_test():
    return jsonify({
        'args_received': dict(request.args),
        'url': request.url,
        'method': request.method,
        'headers': dict(request.headers)
    })

# This is the appointments view function, this is the function you'll use when you want to
# get data about appointments, maybe things like viewing appointment history and etc
@appointments_bp.route('/appointments/view', methods=['GET'])
def view_appointments():
    """
    View appointments for a customer or salon
    ---
    tags:
      - Appointments
    parameters:
      - name: role
        in: query
        required: true
        type: string
        description: customer or salon
      - name: id
        in: query
        required: true
        type: integer
        description: user or salon ID
    responses:
      200:
        description: Appointments returned
      400:
        description: Missing required parameters
    """
    user_type = request.args.get('role')  # 'customer' or 'salon'
    user_id = request.args.get('id')

    if user_id is None:
        user_id = session.get('user_id') #fail safe?

    if not all([user_type, user_id]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({'error': 'ID must be an integer'}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)
    
    try:
        if user_type == 'customer':
            cursor.execute("""
                SELECT 
                    a.appointment_id, 
                    a.customer_id,
                    a.appointment_date, 
                    a.start_time,
                    a.end_time,
                    a.status,
                    a.notes AS customer_notes,
                    s.salon_id,
                    s.name AS salon_name,
                    sv.service_id,
                    sv.name AS service_name,
                    sv.description AS service_description,
                    sv.price AS price,
                    sv.duration_minutes AS service_duration,
                    e.employee_id,
                    CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                    e.description AS employee_description,
                    a.image_url,
                    a.image_after_url
                FROM appointments a
                JOIN salons s ON a.salon_id = s.salon_id
                JOIN services sv ON a.service_id = sv.service_id
                JOIN employees e ON a.employee_id = e.employee_id
                WHERE a.customer_id = %s
                ORDER BY a.appointment_date DESC, a.start_time DESC
            """, (user_id,))
            
        elif user_type == 'salon':
            cursor.execute("""
                SELECT 
                    a.appointment_id, 
                    a.appointment_date, 
                    a.start_time,
                    a.end_time,
                    a.status,
                    a.notes,
                    u.user_id AS customer_id,
                    CONCAT(u.first_name, ' ', u.last_name) AS customer_name,
                    u.email AS customer_email,
                    u.phone_number AS customer_phone,
                    sv.service_id,
                    sv.name AS service_name,
                    sv.description AS service_description,
                    sv.price AS service_price,
                    sv.duration_minutes AS service_duration,
                    e.employee_id,
                    CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                    e.description AS employee_description
                    a.image_url,
                    a.image_after_url
                FROM appointments a
                JOIN users u ON a.customer_id = u.user_id
                JOIN services sv ON a.service_id = sv.service_id
                JOIN employees e ON a.employee_id = e.employee_id
                WHERE a.salon_id = %s
                ORDER BY a.appointment_date DESC, a.start_time DESC
            """, (user_id,))
        else:
            return jsonify({'error': 'Invalid role specified'}), 400
        
        appointments = cursor.fetchall()

        for appointment in appointments:
            for key in ['appointment_date', 'start_time', 'end_time']:
                if key in appointment and appointment[key] is not None:
                    appointment[key] = str(appointment[key])
            
            # time slot
            if appointment.get('start_time') and appointment.get('end_time'):
                appointment['time_slot'] = f"{appointment['start_time']} - {appointment['end_time']}"
        
        return jsonify({
            'appointments': appointments,
            'count': len(appointments)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@appointments_bp.route('/appointments/reviewless/<int:salon_id>', methods=['GET'])
def reviewless_appointments(salon_id):
    """
    Get customer appointments that don't have reviews yet
    ---
    tags:
      - Appointments
    parameters:
      - name: customer_id
        in: query
        required: true
        type: integer
        description: Customer ID
    responses:
      200:
        description: Appointments without reviews returned
      400:
        description: Missing customer ID
    """
    #customer_id = request.args.get('customer_id')
    # user context user_id wasnt always set so this was reliable
    customer_id = session.get('user_id')

    if not customer_id:
        return jsonify({'error': 'Missing customer_id parameter'}), 400

    try:
        customer_id = int(customer_id)
    except ValueError:
        return jsonify({'error': 'customer_id must be an integer'}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)
    
    try:
        # Simple query: Only appointments without reviews
        cursor.execute("""
            SELECT 
                a.appointment_id, 
                a.appointment_date, 
                a.start_time,
                a.end_time,
                a.status,
                a.notes as customer_notes,
                s.salon_id,
                s.name AS salon_name,
                sv.service_id,
                sv.name AS service_name,
                sv.price AS price,
                sv.duration_minutes AS service_duration,
                e.employee_id,
                CONCAT(e.first_name, ' ', e.last_name) AS employee_name
            FROM appointments a
            JOIN salons s ON a.salon_id = s.salon_id
            JOIN services sv ON a.service_id = sv.service_id
            JOIN employees e ON a.employee_id = e.employee_id
            LEFT JOIN reviews r ON a.appointment_id = r.appointment_id
            WHERE a.customer_id = %s
              AND r.review_id IS NULL
              AND a.status = 'completed'
              AND s.salon_id = %s
            ORDER BY a.appointment_date DESC, a.start_time DESC
        """, (customer_id,salon_id,))
        
        appointments = cursor.fetchall()

        # Simple formatting
        for appointment in appointments:
            for key in ['appointment_date', 'start_time', 'end_time']:
                if key in appointment and appointment[key] is not None:
                    appointment[key] = str(appointment[key])
            
            appointment['time_slot'] = f"{appointment['start_time']} - {appointment['end_time']}"
        
        return jsonify({
            'customer_id': customer_id,
            'appointments': appointments,
            'count': len(appointments)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# to view how many appointments are on a specific day (calendar view)
@appointments_bp.route('/salon/<int:salon_id>/appointments/calendar', methods=['GET'])
def total_appointments(salon_id):
    """
    Get total appointments per day for a salon
    ---
    tags:
      - Appointments
    parameters:
      - name: salon_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: List of dates and counts
    """
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    try:
        query = """
            select appointment_date, count(*) as total_appointments
            from appointments
            where salon_id = %s and status in('booked', 'paid')
            group by appointment_date
            order by appointment_date asc
        """
        cursor.execute(query, (salon_id,))
        result = cursor.fetchall()
        return jsonify(result), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# Rescheduling function! this function is going to need the new appointment date.
@appointments_bp.route('/appointments/update', methods=['PUT'])
def update_appointment():
    """
    Update an appointment date/time
    ---
    tags:
      - Appointments
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            appointment_id:
              type: integer
            new_date:
              type: string
            new_start_time:
              type: string
            new_note:
              type: string
    responses:
      200:
        description: Appointment updated
      404:
        description: Appointment not found
    """
    data = request.get_json()
    appointment_id = data.get('appointment_id')
    new_date = data.get('new_date')        # needs this format: YYYY-MM-DD
    new_start_time = data.get('new_start_time')  # needs this format: HH:MM:SS
    new_note = data.get('new_note')        # optional

    if not appointment_id:
        return jsonify({'error': 'Missing appointment ID'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # get existing format
        cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s", (appointment_id,))
        appointment = cursor.fetchone()
        if not appointment:
            return jsonify({'error': 'Appointment not found'}), 404

        # Will use existing appointment data if not provided by customer originally
        appointment_date = new_date or appointment['appointment_date']
        start_time = new_start_time or appointment['start_time']
        notes = new_note if new_note is not None else appointment['notes']

        # getting duration of service
        cursor.execute("SELECT duration_minutes FROM services WHERE service_id = %s", (appointment['service_id'],))
        service = cursor.fetchone()
        if not service:
            return jsonify({'error': 'Invalid service associated with this appointment'}), 400
        duration = timedelta(minutes=service['duration_minutes'])

        # calc new start and end time
        try:
            start_dt = datetime.strptime(f"{appointment_date} {start_time}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return jsonify({'error': 'Invalid date or time format'}), 400
        end_dt = start_dt + duration
        end_time_str = end_dt.strftime("%H:%M:%S")

        day_name = start_dt.strftime("%A")

        cursor.execute("""
            SELECT start_time, end_time
            FROM time_slots
            WHERE employee_id = %s AND salon_id = %s
              AND day = %s AND is_available = TRUE
        """, (appointment['employee_id'], appointment['salon_id'], day_name))
        schedule = cursor.fetchone()
        if not schedule:
            return jsonify({'error': f'Employee is not scheduled to work on {day_name}'}), 400

        schedule_start_time = schedule['start_time']
        schedule_end_time = schedule['end_time']

        if isinstance(schedule_start_time, timedelta):
            schedule_start_time = timedelta_to_time(schedule_start_time)
        if isinstance(schedule_end_time, timedelta):
            schedule_end_time = timedelta_to_time(schedule_end_time)

        schedule_start_dt = datetime.combine(start_dt.date(), schedule_start_time)
        schedule_end_dt = datetime.combine(start_dt.date(), schedule_end_time)

        # checker for working hours
        if not (schedule_start_dt <= start_dt < schedule_end_dt):
            return jsonify({'error': 'Requested time is outside working hours'}), 400
        if not (start_dt < end_dt <= schedule_end_dt):
            return jsonify({'error': 'Service duration extends beyond working hours'}), 400

        cursor.execute("""
            SELECT 1 FROM appointments
            WHERE employee_id = %s
              AND salon_id = %s
              AND appointment_date = %s
              AND status IN ('booked', 'confirmed')
              AND appointment_id != %s
              AND (
                    (start_time < %s AND end_time > %s) OR
                    (start_time >= %s AND start_time < %s)
                  )
            LIMIT 1
        """, (
            appointment['employee_id'],
            appointment['salon_id'],
            appointment_date,
            appointment_id,
            end_time_str, start_time,
            start_time, end_time_str
        ))
        overlap = cursor.fetchone()
        if overlap:
            return jsonify({'error': 'Time slot overlaps with another appointment'}), 400

        # insert updated appoint into data
        cursor.execute("""
            UPDATE appointments
            SET appointment_date = %s,
                start_time = %s,
                end_time = %s,
                notes = %s,
                last_modified = %s
            WHERE appointment_id = %s
        """, (appointment_date, start_time, end_time_str, notes, datetime.now(), appointment_id))

        mysql.connection.commit()
        return jsonify({
            'message': 'Appointment updated successfully',
            'appointment_date': appointment_date,
            'start_time': start_time,
            'end_time': end_time_str,
            'notes': notes
        }), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()


# cancelling of appointment, appointment_id is only needed, doesn't delete 
# it from the database it just changes status to cancelled
@appointments_bp.route('/appointments/cancel', methods=['PUT'])
def cancel_appointment():
    """
    Cancel an appointment (does not delete it)
    ---
    tags:
      - Appointments
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            appointment_id:
              type: integer
              description: ID of the appointment to cancel
    responses:
      200:
        description: Appointment cancelled successfully
      400:
        description: Missing appointment ID
      404:
        description: Appointment not found
      500:
        description: Internal server error
    """
    data = request.get_json()
    appointment_id = data.get('appointment_id')

    if not appointment_id:
        return jsonify({'error': 'Missing appointment ID'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    try:
        cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s", (appointment_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Appointment not found'}), 404

        cursor.execute("""
            UPDATE appointments
            SET status = %s, last_modified = %s
            WHERE appointment_id = %s
        """, ('cancelled', datetime.now(), appointment_id))

        mysql.connection.commit()
        return jsonify({'message': 'Appointment cancelled successfully'}), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Get specific appointments history from salon or customer
@appointments_bp.route('/appointments/<string:role>/<int:entity_id>', methods=['GET'])
def get_appointments(role, entity_id):
    """
    Get appointment history for a salon or customer
    ---
    tags:
      - Appointments
    parameters:
      - name: role
        in: path
        type: string
        required: true
        description: customer or salon
      - name: entity_id
        in: path
        type: integer
        required: true
        description: Customer ID or Salon ID
    responses:
      200:
        description: Appointment history returned
      400:
        description: Invalid role entered
      500:
        description: Internal server error
    """
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        if role == 'customer':
            cursor.execute(
                "SELECT * FROM appointments WHERE customer_id = %s ORDER BY appointment_date, start_time",
                (entity_id,)
            )
        elif role == 'salon':
            cursor.execute(
                "SELECT * FROM appointments WHERE salon_id = %s ORDER BY appointment_date, start_time",
                (entity_id,)
            )
        else:
            return jsonify({'error': 'Invalid role entered'}), 400



        appointments = cursor.fetchall()

        for appt in appointments:
            for field in ['start_time', 'end_time']:
                val = appt.get(field)
                if isinstance(val, timedelta):
                    t = timedelta_to_time(val)
                    appt[field] = t.strftime("%H:%M:%S")

        return jsonify({'appointments': appointments}), 200

    finally:
        cursor.close()


# getter for populating appointment schedule/time tab
@appointments_bp.route('/employees/<int:employee_id>/weekly-availability', methods=['GET'])
def employee_weekly_availability(employee_id):
    """
    Get weekly availability for an employee
    ---
    tags:
      - Appointments
    parameters:
      - name: employee_id
        in: path
        required: true
        type: integer
        description: Employee ID
      - name: date
        in: query
        required: false
        type: string
        description: Optional date (YYYY-MM-DD) to highlight booked slots
    responses:
      200:
        description: Weekly availability, working hours, and time slot statuses
      400:
        description: Invalid date format
      404:
        description: Employee not found
      500:
        description: Internal server error
    """
    req_date = request.args.get('date')
    increment_minutes = 15

    # Validate date param
    target_date = None
    if req_date:
        try:
            target_date = datetime.strptime(req_date, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Get employee and salon
        cursor.execute("SELECT salon_id FROM employees WHERE employee_id = %s", (employee_id,))
        emp = cursor.fetchone()
        if not emp:
            return jsonify({'error': 'Employee not found'}), 404
        salon_id = emp['salon_id']

        def normalize_time(t):
            if isinstance(t, timedelta):
                hours, remainder = divmod(t.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                return dt_time(int(hours), int(minutes), int(seconds))
            if isinstance(t, str):
                return datetime.strptime(t, "%H:%M:%S").time()
            return t

        days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

        cursor.execute("""
            SELECT day, open_time, close_time, is_closed
            FROM operating_hours
            WHERE salon_id = %s
        """, (salon_id,))
        op_map = {r['day']: r for r in cursor.fetchall()}

        cursor.execute("""
            SELECT day, start_time, end_time, is_available
            FROM time_slots
            WHERE employee_id = %s AND salon_id = %s
        """, (employee_id, salon_id))
        time_slots_rows = cursor.fetchall()
        
        sched_map = {}
        ts_by_day = {}
        for r in time_slots_rows:
            day = r['day']
            ts_by_day.setdefault(day, []).append(r)
            if r['is_available']:
                sched_map[day] = r

        # Get appointments for target date if provided
        appointments_on_date = []
        if target_date:
            cursor.execute("""
                SELECT start_time, end_time
                FROM appointments
                WHERE employee_id = %s AND salon_id = %s 
                  AND appointment_date = %s
                  AND status IN ('booked','confirmed')
            """, (employee_id, salon_id, target_date))
            appointments_on_date = cursor.fetchall()

        # interval checking
        def is_time_in_intervals(check_time, check_end_time, intervals):
            """Check if a time period overlaps with any interval"""
            for interval_start, interval_end in intervals:
                # Check for overlap
                latest_start = max(check_time, interval_start)
                earliest_end = min(check_end_time, interval_end)
                if latest_start < earliest_end:
                    return True
            return False

        # Build results for each day
        week_result = []

        for day in days:
            day_entry = {
                'day': day,
                'salon_closed': False,
                'operating_hours': None,
                'employee_schedule': None,
                'timeline': []
            }

            op = op_map.get(day)
            if not op or op['is_closed']:
                # Handle salon closed or no operating hours
                day_entry['salon_closed'] = True
                if op:
                    day_entry['operating_hours'] = {
                        'open_time': normalize_time(op['open_time']).strftime("%H:%M:%S"),
                        'close_time': normalize_time(op['close_time']).strftime("%H:%M:%S")
                    }
                week_result.append(day_entry)
                continue

            # get operating hours
            open_time = normalize_time(op['open_time'])
            close_time = normalize_time(op['close_time'])
            day_entry['operating_hours'] = {
                'open_time': open_time.strftime("%H:%M:%S"),
                'close_time': close_time.strftime("%H:%M:%S")
            }

            # Check employee schedule
            sched = sched_map.get(day)
            if sched:
                sched_start = normalize_time(sched['start_time'])
                sched_end = normalize_time(sched['end_time'])
                day_entry['employee_schedule'] = {
                    'start_time': sched_start.strftime("%H:%M:%S"),
                    'end_time': sched_end.strftime("%H:%M:%S")
                }

            # Prepare intervals for checking
            unavailable_intervals = []
            for ts in ts_by_day.get(day, []):
                if not ts['is_available']:
                    start = normalize_time(ts['start_time'])
                    end = normalize_time(ts['end_time'])
                    unavailable_intervals.append((start, end))

            appt_intervals = []
            if target_date and target_date.strftime("%A") == day:
                for appt in appointments_on_date:
                    start = normalize_time(appt['start_time'])
                    end = normalize_time(appt['end_time'])
                    appt_intervals.append((start, end))

            # Build timeline
            current = datetime.combine(datetime.today(), open_time)
            end_dt = datetime.combine(datetime.today(), close_time)
            
            while current <= end_dt:
                slot_time = current.time()
                slot_end = (current + timedelta(minutes=increment_minutes)).time()
                
                # Determine status with clear priority
                if not sched or not (sched_start <= slot_time < sched_end):
                    status = 'not_working'
                elif is_time_in_intervals(slot_time, slot_end, unavailable_intervals):
                    status = 'unavailable'
                elif is_time_in_intervals(slot_time, slot_end, appt_intervals):
                    status = 'booked'
                else:
                    status = 'available'

                day_entry['timeline'].append({
                    'time': slot_time.strftime("%H:%M:%S"),
                    'status': status
                })

                current += timedelta(minutes=increment_minutes)

            week_result.append(day_entry)

        return jsonify({
            'employee_id': employee_id,
            'salon_id': salon_id,
            'increment_minutes': increment_minutes,
            'week': week_result
        }), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# getter for book appointment where week starts with sunday
# gets the week based on the date you put in
@appointments_bp.route('/employees/<int:employee_id>/weekly-availability/sunday-based', methods=['GET'])
def sunday_based_availability(employee_id):
    req_date = request.args.get('date')
    increment_minutes = 15

    target_date = None
    if req_date:
        try:
            target_date = datetime.strptime(req_date, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400
        
    weekday_index = (target_date.weekday() + 1) % 7
    week_start = target_date - timedelta(days=weekday_index)
    week_end = week_start + timedelta(days=6)
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("SELECT salon_id FROM employees WHERE employee_id = %s", (employee_id,))
        emp = cursor.fetchone()
        if not emp:
            return jsonify({'error': 'Employee not found'}), 404
        salon_id = emp['salon_id']

        def normalize_time(t):
            if isinstance(t, timedelta):
                hours, remainder = divmod(t.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                return dt_time(int(hours), int(minutes), int(seconds))
            if isinstance(t, str):
                return datetime.strptime(t, "%H:%M:%S").time()
            return t
        
        days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']

        cursor.execute("""
            SELECT day, open_time, close_time, is_closed
            FROM operating_hours
            WHERE salon_id = %s
        """, (salon_id,))
        op_map = {r['day']: r for r in cursor.fetchall()}

        cursor.execute("""
            SELECT day, start_time, end_time, is_available
            FROM time_slots
            WHERE employee_id = %s AND salon_id = %s
        """, (employee_id, salon_id))
        time_slots_rows = cursor.fetchall()

        sched_map = {}
        ts_by_day = {}
        for r in time_slots_rows:
            day = r['day']
            ts_by_day.setdefault(day, []).append(r)
            if r['is_available']:
                sched_map[day] = r

        cursor.execute("""
            SELECT appointment_date, start_time, end_time
            FROM appointments
            WHERE 
                employee_id=%s AND 
                salon_id=%s AND 
                DATE(appointment_date) BETWEEN %s AND %s AND 
                status IN ('booked', 'confirmed')
        """, (employee_id, salon_id, week_start, week_end))

        appts_by_date = {}

        for row in cursor.fetchall():
            ad = row['appointment_date']
            if isinstance(ad, datetime):
                ad = ad.date()
            appts_by_date.setdefault(ad, []).append(row)

        # interval checking
        def is_time_in_intervals(check_time, check_end_time, intervals):
            """Check if a time period overlaps with any interval"""
            for interval_start, interval_end in intervals:
                # Check for overlap
                latest_start = max(check_time, interval_start)
                earliest_end = min(check_end_time, interval_end)
                if latest_start < earliest_end:
                    return True
            return False

        week_result = []

        for i, day in enumerate(days):
            day_date = week_start + timedelta(days=i)
            op = op_map.get(day)

            day_entry = {
                "day": day,
                "date": day_date.isoformat(),
                "salon_closed": False,
                "operating_hours": None,
                "employee_schedule": None,
                "timeline" : []
            }

            if not op or op['is_closed']:
                day_entry['salon_closed'] = True
                week_result.append(day_entry)
                continue

            # get operating hours
            open_time = normalize_time(op['open_time'])
            close_time = normalize_time(op['close_time'])
            day_entry['operating_hours'] = {
                'open_time': open_time.strftime("%H:%M:%S"),
                'close_time': close_time.strftime("%H:%M:%S")
            }

             # Check employee schedule
            sched = sched_map.get(day)
            if sched:
                sched_start = normalize_time(sched['start_time'])
                sched_end = normalize_time(sched['end_time'])
                day_entry['employee_schedule'] = {
                    'start_time': sched_start.strftime("%H:%M:%S"),
                    'end_time': sched_end.strftime("%H:%M:%S")
                }

            # Prepare intervals for checking
            unavailable_intervals = []
            for ts in ts_by_day.get(day, []):
                if not ts['is_available']:
                    start = normalize_time(ts['start_time'])
                    end = normalize_time(ts['end_time'])
                    unavailable_intervals.append((start, end))

            # Appointments for this day
            appt_intervals = []
            for appt in appts_by_date.get(day_date, []):
                start = normalize_time(appt['start_time'])
                end = normalize_time(appt['end_time'])
                appt_intervals.append((start, end))

            # Build timeline
            current = datetime.combine(datetime.today(), open_time)
            end_dt = datetime.combine(datetime.today(), close_time)

            while current <= end_dt:
                slot_time = current.time()
                slot_end = (current + timedelta(minutes=increment_minutes)).time()
                
                # Determine status with clear priority
                if not sched or not (sched_start <= slot_time < sched_end):
                    status = 'not_working'
                elif is_time_in_intervals(slot_time, slot_end, unavailable_intervals):
                    status = 'unavailable'
                elif is_time_in_intervals(slot_time, slot_end, appt_intervals):
                    status = 'booked'
                else:
                    status = 'available'

                day_entry['timeline'].append({
                    'time': slot_time.strftime("%H:%M:%S"),
                    'status': status
                })

                current += timedelta(minutes=increment_minutes)

            week_result.append(day_entry)

        return jsonify({
            'employee_id': employee_id,
            'salon_id': salon_id,
            'increment_minutes': increment_minutes,
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'week': week_result
        }), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

@appointments_bp.route('/employees/<int:employee_id>/breaks', methods=['GET'])
def get_employee_breaks(employee_id):
    """
    Get all breaks/blocked times for an employee
    Returns time_slots where is_available = FALSE
    """
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Verify employee exists
        cursor.execute("SELECT salon_id FROM employees WHERE employee_id = %s", (employee_id,))
        employee = cursor.fetchone()
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404

        # Get all unavailable time slots (breaks)
        cursor.execute("""
            SELECT slot_id, day, start_time, end_time
            FROM time_slots
            WHERE employee_id = %s 
              AND is_available = FALSE
            ORDER BY 
              FIELD(day, 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'),
              start_time
        """, (employee_id,))

        breaks = cursor.fetchall()

        # Convert timedelta to string if needed
        for break_item in breaks:
            if isinstance(break_item['start_time'], timedelta):
                break_item['start_time'] = str(timedelta_to_time(break_item['start_time']))
            if isinstance(break_item['end_time'], timedelta):
                break_item['end_time'] = str(timedelta_to_time(break_item['end_time']))

        return jsonify({
            'employee_id': employee_id,
            'salon_id': employee['salon_id'],
            'breaks': breaks
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@appointments_bp.route('/employees/<int:employee_id>/breaks', methods=['POST'])
def add_employee_break(employee_id):
    """
    Add a break/blocked time for an employee
    Creates a time_slot with is_available = FALSE
    No database changes required - uses existing columns only
    """
    data = request.get_json()

    salon_id = data.get('salon_id')
    day = data.get('day')
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    if not all([salon_id, day, start_time, end_time]):
        return jsonify({'error': 'Missing required fields: salon_id, day, start_time, end_time'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Verify employee exists and belongs to salon
        cursor.execute("""
            SELECT employee_id FROM employees 
            WHERE employee_id = %s AND salon_id = %s
        """, (employee_id, salon_id))
        
        if not cursor.fetchone():
            return jsonify({'error': 'Employee not found or does not belong to this salon'}), 404

        # Validate times
        try:
            start_dt = datetime.strptime(start_time, "%H:%M:%S").time()
            end_dt = datetime.strptime(end_time, "%H:%M:%S").time()
        except ValueError:
            return jsonify({'error': 'Invalid time format. Use HH:MM:SS'}), 400

        if start_dt >= end_dt:
            return jsonify({'error': 'Start time must be before end time'}), 400

        # Check for overlapping breaks on the same day
        cursor.execute("""
            SELECT slot_id FROM time_slots
            WHERE employee_id = %s 
              AND day = %s
              AND is_available = FALSE
              AND (
                (start_time < %s AND end_time > %s) OR
                (start_time >= %s AND start_time < %s)
              )
        """, (employee_id, day, end_time, start_time, start_time, end_time))

        if cursor.fetchone():
            return jsonify({'error': 'This break overlaps with an existing break'}), 400

        # Insert the break (is_available = FALSE marks it as a break/blocked time)
        cursor.execute("""
            INSERT INTO time_slots (
                salon_id, employee_id, day, start_time, end_time, is_available
            ) VALUES (%s, %s, %s, %s, %s, FALSE)
        """, (salon_id, employee_id, day, start_time, end_time))

        mysql.connection.commit()
        slot_id = cursor.lastrowid

        return jsonify({
            'message': 'Break added successfully',
            'slot_id': slot_id,
            'day': day,
            'start_time': start_time,
            'end_time': end_time
        }), 201

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@appointments_bp.route('/employees/<int:employee_id>/breaks/<int:slot_id>', methods=['DELETE'])
def delete_employee_break(employee_id, slot_id):
    """
    Delete a specific break/blocked time
    """
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Verify the slot exists and belongs to this employee
        cursor.execute("""
            SELECT slot_id FROM time_slots
            WHERE slot_id = %s 
              AND employee_id = %s 
              AND is_available = FALSE
        """, (slot_id, employee_id))

        if not cursor.fetchone():
            return jsonify({'error': 'Break not found'}), 404

        # Delete the break
        cursor.execute("""
            DELETE FROM time_slots
            WHERE slot_id = %s AND employee_id = %s
        """, (slot_id, employee_id))

        mysql.connection.commit()

        return jsonify({
            'message': 'Break removed successfully',
            'slot_id': slot_id
        }), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()






