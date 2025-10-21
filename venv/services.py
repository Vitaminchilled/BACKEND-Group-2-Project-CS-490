from flask import Blueprint, request, jsonify, session
from flask import current_app

services_bp = Blueprint('services', __name__)

@services_bp.route('salon/services/add', methods=['POST'])
def add_service():
    data = request.get_json()
    #check if the form is filled out 
    required_fields = ['salon_id', 'master_tag_id', 'name', 'description', 'duration_minutes', 'price']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        salon_id = data['salon_id']
        master_tag_id = data['master_tag_id']
        name = data['name']
        description = data['description']
        duration_minutes = data['duration_minutes']
        price = data['price']

        #create new entry on the services table
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            insert into services(salon_id, master_tag_id, name, description, duration_minutes, price)
        """
        cursor.execute(query, (salon_id, master_tag_id, name, description, duration_minutes, price))
        mysql.connection.commit()

        service_id = cursor.lastrowid
        cursor.close()
        return jsonify({'message': 'Service added successfully'}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to add service', 'details': str(e)}), 500

@services_bp.route('salon/services/edit/<int:service_id>', methods=['PUT'])
def edit_service(service_id):
    data = request.get_json()
    #check if the form is filled out
    required_fields = ['master_tag_id', 'name', 'description', 'duration_minutes', 'price', 'is_active']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        master_tag_id = data['master_tag_id']
        name = data['name']
        description = data['description']
        duration_minutes = data['duration_minutes']
        price = data['price']
        is_active = data['is_active']

        #update the service entry
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            update services
            set master_tag_id=%s, name=%s, description=%s, duration_minutes=%s, price=%s, is_active=%s
            where service_id=%s
        """
        cursor.execute(query, (master_tag_id, name, description, duration_minutes, price, is_active, service_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Service updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to update service', 'details': str(e)}), 500

@services_bp.route('salon/services/delete/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    pass

@services_bp.route('salon/services/loyalty', methods=['POST'])
def service_loyalty():
    pass