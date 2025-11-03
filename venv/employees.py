from flask import Blueprint, request, jsonify, session
from flask import current_app
from datetime import datetime

employees_bp = Blueprint('employees', __name__)

#implement salon gallery later

@employees_bp.route('/salon/<int:salon_id>/employees', methods=['GET'])
def get_employees(salon_id):
    try: 
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select e.employee_id, e.first_name, e.last_name, e.description
            from employees e
            where e.salon_id = %s
            order by e.last_name
        """
        cursor.execute(query, (salon_id,))
        employees = cursor.fetchall()
        cursor.close()
        return jsonify({
            'employees' : [{
                "employee_id": employee[0],
                "employee_first_name": employee[1],
                "employee_last_name": employee[2],
                "description": employee[3]
            } for employee in employees]
        })
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching employees."}), 500

@employees_bp.route('/salon/<int:salon_id>/employees', methods=['POST'])
def add_employee(salon_id):
    first_name = request.json.get('first_name')
    last_name = request.json.get('last_name')
    description = request.json.get('description')
    tag_name = request.json.get('tag_name')
    #photo = request.json.get('photo')

    if not all([first_name, last_name, tag_name]):
        return jsonify({"error": "Missing required fields"}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()
    query = """
        select master_tag_id
        from master_tags
        where name = %s
    """
    cursor.execute(query, (tag_name,))
    tag_info = cursor.fetchone()
    master_tag_id = tag_info[0]

    try:
        query = """
            insert into employees (salon_id, first_name, last_name, description)
            values (%s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, first_name, last_name, description))
        employee_id = cursor.lastrowid
        
        query = """
            insert into entity_master_tags (entity_type, entity_id, master_tag_id)
            values (%s, %s, %s)
        """
        cursor.execute(query, ('employees', employee_id, master_tag_id))
        mysql.connection.commit()

        #if photo:
            #query = """
                #insert into salon_gallery (salon_id, employee_id, image_url)
                #values (%s, %s, %s)
            #"""
           # cursor.execute(query, (salon_id, employee_id, photo))
           # mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Employee added successfully", "employee_id": employee_id}), 201
    except Exception as e:
        return jsonify({"error": "An error occurred while adding the employee."}), 500
    
@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>', methods=['PUT'])
def edit_employee(salon_id, employee_id):
    first_name = request.json.get('first_name')
    last_name = request.json.get('last_name')
    description = request.json.get('description')
    tag_name = request.json.get('tag_name')
    #photo = request.json.get('photo')  

    if not all([first_name, last_name, tag_name]):
        return jsonify({"error": "Missing required fields"}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()
    query = """
        select master_tag_id
        from master_tags
        where name = %s
    """
    cursor.execute(query, (tag_name,))
    tag_info = cursor.fetchone()
    master_tag_id = tag_info[0]

    try:
        query = """
            update employees
            set first_name = %s, last_name = %s, description = %s
            where employee_id = %s and salon_id = %s
        """
        cursor.execute(query, (first_name, last_name, description, employee_id, salon_id))
        query = """
            update entity_master_tags
            set master_tag_id = %s
            where entity_id = %s and entity_type = 'employees'
        """
        cursor.execute(query, (master_tag_id, employee_id))
        mysql.connection.commit()

        #if photo:
            #query = """
               # insert into salon_gallery (salon_id, employee_id, image_url)
               # values (%s, %s, %s)
               # on duplicate key update image_url = %s
            #"""
            #cursor.execute(query, (salon_id, employee_id, photo, photo))
            #mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Employee updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while updating the employee."}), 500

@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>', methods=['DELETE'])
def delete_employee(salon_id, employee_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        #delete employee's photos first
        query = """
            delete from salon_gallery
            where employee_id = %s
        """
        cursor.execute(query, (employee_id,))
        #delete employee's time slots later
        query = """
            delete from time_slots
            where employee_id = %s
        """
        cursor.execute(query, (employee_id,))
        #delete employee's tag
        query = """
            delete from entity_master_tags
            where entity_id = %s
        """
        cursor.execute(query, (employee_id,))
        #delete employee last 
        query = """
            delete from employees
            where employee_id = %s
        """
        cursor.execute(query, (employee_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Employee deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while deleting the employee."}), 500
    
@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>/timeslots', methods=['POST'])
def add_timeslot(salon_id, employee_id):
    data = request.get_json()
    day = data.get('day')
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    if not all([day, start_time, end_time]):
        return jsonify({"error": "Missing required fields"}), 400

    start_time = datetime.strptime(start_time, "%H:%M:%S").time()
    end_time = datetime.strptime(end_time, "%H:%M:%S").time()

    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        #check salon's hours
        query = """
            select open_time, close_time
            from operating_hours
            where salon_id = %s and day = %s
        """
        cursor.execute(query, (salon_id, day))
        hours = cursor.fetchone()

        if not hours:
            cursor.close()
            return jsonify({"error": f"No operating hours set for {day}."}), 400
        
        open_time, close_time = hours
        open_time = (datetime.min + open_time).time()
        close_time = (datetime.min + close_time).time()

        #check if within operating hours
        if not (open_time <= start_time < end_time <= close_time):
            cursor.close()
            return jsonify({
                "error": f"Time slot must be between {open_time} and {close_time} for {day}."}), 400
        
        #check for overlapping times
        query = """
            select slot_id from time_slots
            where employee_id = %s and salon_id = %s and day = %s
            and (%s < end_time and %s > start_time)
        """
        cursor.execute(query, (employee_id, salon_id, day, start_time, end_time))
        overlap = cursor.fetchone()

        if overlap:
            cursor.close()
            return jsonify({"error": "Please choose a different time slot."}), 400 
        
        query = """
            insert into time_slots (salon_id, employee_id, day, start_time, end_time)
            values (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, employee_id, day, start_time, end_time))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Time slot added successfully"}), 201
    except Exception as e:
        return jsonify({"error": "An error occurred while adding the time slot."}), 500
    

@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>/timeslots', methods=['GET'])
def get_timeslots(salon_id, employee_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select slot_id, day, start_time, end_time
            from time_slots
            where salon_id = %s and employee_id = %s
            order by field(day, 'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'), start_time
        """
        cursor.execute(query, (salon_id, employee_id))

        #convert datetime to strings
        columns = [desc[0] for desc in cursor.description]
        timeslots = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()

        for timeslot in timeslots:
            for key in ['day', 'start_time', 'end_time', 'created_at', 'last_modified']:
                if key in timeslot and timeslot[key] is not None:
                    timeslot[key] = str(timeslot[key])
        return jsonify(timeslots), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching time slots."}), 500

@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>/timeslots/<int:slot_id>', methods=['PUT'])
def edit_timeslot(salon_id, employee_id, slot_id):
    data = request.get_json()
    day = data.get('day')
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    if not all([day, start_time, end_time]):
        return jsonify({"error": "Missing required fields"}), 400

    start_time = datetime.strptime(start_time, "%H:%M:%S").time()
    end_time = datetime.strptime(end_time, "%H:%M:%S").time()
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        #check salon's hours
        query = """
            select open_time, close_time
            from operating_hours
            where salon_id = %s and day = %s
        """
        cursor.execute(query, (salon_id, day))
        hours = cursor.fetchone()

        if not hours:
            cursor.close()
            return jsonify({"error": f"No operating hours set for {day}."}), 400
        
        open_time, close_time = hours
        open_time = (datetime.min + open_time).time()
        close_time = (datetime.min + close_time).time()

        #check if within operating hours
        if not (open_time <= start_time < end_time <= close_time):
            cursor.close()
            return jsonify({
                "error": f"Time slot must be between {open_time} and {close_time} for {day}."}), 400
        
        #check for overlapping times
        query = """
            select slot_id from time_slots
            where employee_id = %s and salon_id = %s and day = %s
            and slot_id != %s
            and (%s < end_time and %s > start_time)
        """
        cursor.execute(query, (employee_id, salon_id, day, slot_id, start_time, end_time))
        overlap = cursor.fetchone()

        if overlap:
            cursor.close()
            return jsonify({"error": "Please choose a different time slot."}), 400
        
        query = """
            update time_slots
            set day = %s, start_time = %s, end_time = %s
            where slot_id = %s and employee_id = %s and salon_id = %s
        """
        cursor.execute(query, (day, start_time, end_time, slot_id, employee_id, salon_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Time slot updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while updating the time slot."}), 500
    
@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>/timeslots/<int:slot_id>', methods=['DELETE'])
def delete_timeslot(salon_id, employee_id, slot_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            delete from time_slots
            where slot_id = %s and employee_id = %s and salon_id = %s
        """
        cursor.execute(query, (slot_id, employee_id, salon_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Time slot deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while deleting the time slot."}), 500

@employees_bp.route('/salon/<int:salon_id>/employees/salaries', methods=['GET'])
def get_salaries(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select employees.first_name, employees.last_name,
                (select employee_salaries.salary_value
                from employee_salaries
                where employee_salaries.employee_id = employees.employee_id
                order by employee_salaries.effective_date desc
                limit 1) AS hourly,
                (select employee_salaries.effective_date
                from employee_salaries
                where employee_salaries.employee_id = employees.employee_id
                order by employee_salaries.effective_date desc
                limit 1) AS effective_date
            from employees
            where employees.salon_id = %s
            order by employees.last_name;
        """
        cursor.execute(query, (salon_id,))
        columns = [desc[0] for desc in cursor.description]
        salaries = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()

        #turn dates into strings
        for salary in salaries:
            if 'effective_date' in salary and salary['effective_date'] is not None:
                salary['effective_date'] = str(salary['effective_date'])

        return jsonify(salaries)
    except Exception as e:
        return jsonify({"error": "An error occurred while displaying the salaries."}), 500

@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>/salaries', methods=['POST'])
def add_salary(salon_id, employee_id):
    data = request.get_json()
    salary_value = data.get('salary_value')
    effective_date = data.get('effective_date')

    if not all([salary_value, effective_date]):
        return jsonify({"error": "Missing required fields"}), 400 
    
    datetime.strptime(effective_date, "%Y-%m-%d")

    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            insert into employee_salaries(salon_id, employee_id, salary_value, effective_date)
            values(%s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, employee_id, salary_value, effective_date))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Salary added successfully"}), 201
    except Exception as e:
        return jsonify({"error": "An error occurred while adding the salary."}), 500

#displays the salary histories of a specific employee 
@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>/salaries', methods=['GET'])
def get_salary(salon_id, employee_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select employees.first_name, employees.last_name, employee_salaries.salary_value as hourly, employee_salaries.effective_date
            from employees 
            join employee_salaries on employees.employee_id = employee_salaries.employee_id
            where employees.salon_id = %s and employees.employee_id = %s
            order by employee_salaries.effective_date;
        """
        cursor.execute(query, (salon_id, employee_id,))
        columns = [desc[0] for desc in cursor.description]
        salaries = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()

        for salary in salaries:
            if 'effective_date' in salary and salary['effective_date'] is not None:
                salary['effective_date'] = str(salary['effective_date'])

        return jsonify(salaries), 200
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching the employee's salary history."}), 500