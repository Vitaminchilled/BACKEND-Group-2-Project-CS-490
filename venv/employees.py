from flask import Blueprint, request, jsonify, session
from flask import current_app

employees_bp = Blueprint('employees', __name__)

#implement salon gallery later

@employees_bp.route('/salon/<int:salon_id>/employees', methods=['GET'])
def get_employees(salon_id):
    try: 
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select employees.employee_id, employees.first_name, employees.last_name, employees.description, master_tags.name, salon_gallery.image_url
            from employees
            left join master_tags on master_tags.master_tag_id = employees.master_tag_id
            left join salon_gallery on salon_gallery.employee_id = employees.employee_id
            where employees.salon_id = %s
            order by employees.last_name
        """
        cursor.execute(query, (salon_id,))
        employees = cursor.fetchall()
        cursor.close()
        return jsonify(employees)
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching employees."}), 500

@employees_bp.route('/salon/<int:salon_id>/employees', methods=['POST'])
def add_employee(salon_id):
    first_name = request.json.get('first_name')
    last_name = request.json.get('last_name')
    description = request.json.get('description')
    master_tag_id = request.json.get('master_tag_id')
    #photo = request.json.get('photo')

    if not all([first_name, last_name, master_tag_id]):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            insert into employees (salon_id, master_tag_id, first_name, last_name, description)
            values (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, master_tag_id, first_name, last_name, description))
        mysql.connection.commit()
        employee_id = cursor.lastrowid

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
def update_employee(salon_id, employee_id):
    first_name = request.json.get('first_name')
    last_name = request.json.get('last_name')
    description = request.json.get('description')
    master_tag_id = request.json.get('master_tag_id')
    photo = request.json.get('photo')  # Assuming photo is a URL

    if not all([first_name, last_name, master_tag_id]):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            update employees
            set first_name = %s, last_name = %s, description = %s, master_tag_id = %s
            where employee_id = %s and salon_id = %s
        """
        cursor.execute(query, (first_name, last_name, description, master_tag_id, employee_id, salon_id))
        mysql.connection.commit()

        if photo:
            query = """
                insert into salon_gallery (salon_id, employee_id, image_url)
                values (%s, %s, %s)
                on duplicate key update image_url = %s
            """
            cursor.execute(query, (salon_id, employee_id, photo, photo))
            mysql.connection.commit()
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
    
@employees_bp.route('/employees/<int:employee_id>/timeslots', methods=['POST'])
def add_timeslot(employee_id):
    pass





