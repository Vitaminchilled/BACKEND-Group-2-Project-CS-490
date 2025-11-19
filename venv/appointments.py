from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta, time as dt_time
from MySQLdb.cursors import DictCursor

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
@appointments_bp.route('/appointments/book', methods=['POST'])
def book_appointment():
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

        # inserting into time slot, idk if this is neccesary, 
        # might end up removing time_slot table from database down the line...
        cursor.execute("""
            INSERT INTO time_slots (
                salon_id, employee_id, date, start_time, end_time, is_available
            ) VALUES (%s, %s, %s, %s, %s, FALSE)
        """, (salon_id, employee_id, appointment_date, start_time, end_time_str))
        time_slot_id = cursor.lastrowid

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
    user_type = request.args.get('role')  # 'customer' or 'salon'
    user_id = request.args.get('id')

    if not all([user_type, user_id]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({'error': 'ID must be an integer'}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()
    
    try:
        if user_type == 'customer':
            cursor.execute("""
                SELECT a.appointment_id, a.appointment_date, a.status,
                       s.name AS salon_name, sv.name AS service_name
                FROM appointments a
                JOIN salons s ON a.salon_id = s.salon_id
                JOIN services sv ON a.service_id = sv.service_id
                WHERE a.customer_id = %s
                ORDER BY a.appointment_date DESC
            """, (user_id,))
        elif user_type == 'salon':
            cursor.execute("""
                SELECT a.appointment_id, a.appointment_date, a.status,
                       u.first_name, u.last_name, sv.name AS service_name
                FROM appointments a
                JOIN users u ON a.customer_id = u.user_id
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

# to view how many appointments are on a specific day (calendar view)
@appointments_bp.route('/salon/<int:salon_id>/appointments/calendar', methods=['GET'])
def total_appointments(salon_id):
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
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# Rescheduling function! this function is going to need the new appointment date.
@appointments_bp.route('/appointments/update', methods=['PUT'])
def update_appointment():
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
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()


# cancelling of appointment, appointment_id is only needed, doesn't delete 
# it from the database it just changes status to cancelled
@appointments_bp.route('/appointments/cancel', methods=['PUT'])
def cancel_appointment():
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
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Get specific appointments history from salon or customer
@appointments_bp.route('/appointments/<string:role>/<int:entity_id>', methods=['GET'])
def get_appointments(role, entity_id):

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

        return jsonify(appointments), 200

    finally:
        cursor.close()


# getter for populating appointment schedule/time tab
@appointments_bp.route('/employees/<int:employee_id>/weekly-availability', methods=['GET'])
def employee_weekly_availability(employee_id):
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
                if latest_start <= earliest_end:
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
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
