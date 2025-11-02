from flask import Blueprint, request, jsonify, session
from flask import current_app

services_bp = Blueprint('services', __name__)

@services_bp.route('/salon/<int:salon_id>/services', methods=['GET'])
def get_services(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select services.service_id, services.name, services.description, services.duration_minutes, services.price, services.is_active, tags.name
            from services
            left join entity_tags on entity_tags.entity_id = services.service_id and entity_tags.entity_type = 'service'
            left join tags on tags.tag_id = entity_tags.tag_id
            where services.salon_id = %s;
        """
        cursor.execute(query, (salon_id,))
        services = cursor.fetchall()
        cursor.close()
        return jsonify({'services': services}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch services', 'details': str(e)}), 500
    
@services_bp.route('/salon/<int:salon_id>/services/add', methods=['POST'])
def add_service(salon_id):
    data = request.get_json()

    #check if the form is filled out 
    required_fields = ['tag_name', 'name', 'description', 'duration_minutes', 'price']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    tag_name = data.get('tag_name')

    try: 
        name = data['name']
        description = data['description']
        duration_minutes = data['duration_minutes']
        price = data['price']

        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        #get tag id
        query = """
            select tag_id
            from tags
            where name = %s
        """
        cursor.execute(query, (tag_name,))
        tag = cursor.fetchone()
        if not tag:
            return jsonify({"error": f"Tag '{tag_name}' does not exist"}), 400
        tag_id = tag[0]

        #create new entry on the services table
        query = """
            insert into services(salon_id, name, description, duration_minutes, price)
            values(%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, name, description, duration_minutes, price))
        service_id = cursor.lastrowid

        #insert into entity tags
        query = """
            insert into entity_tags (entity_type, entity_id, tag_id)
            values(%s, %s, %s)
        """
        cursor.execute(query, ('service', service_id, tag_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Service added successfully'}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to add service', 'details': str(e)}), 500

@services_bp.route('/salon/<int:salon_id>/services/edit/<int:service_id>', methods=['PUT'])
def edit_service(salon_id, service_id):
    data = request.get_json()
    #check if the form is filled out/there is autofilled data
    required_fields = ['tag_name', 'name', 'description', 'duration_minutes', 'price', 'is_active']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    tag_name = data.get('tag_name')

    try:
        name = data['name']
        description = data['description']
        duration_minutes = data['duration_minutes']
        price = data['price']
        is_active = data['is_active']
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        #get tag id
        query = """
            select tag_id
            from tags
            where name = %s
        """
        cursor.execute(query, (tag_name,))
        tag = cursor.fetchone()
        if not tag:
            return jsonify({"error": f"Tag '{tag_name}' does not exist"}), 400
        tag_id = tag[0]

        #update the service entry
        query = """
            update services
            set name=%s, description=%s, duration_minutes=%s, price=%s, is_active=%s
            where service_id=%s and salon_id = %s
        """
        cursor.execute(query, (name, description, duration_minutes, price, is_active, service_id, salon_id))

        #delete old tag
        query = """
            delete from entity_tags
            where entity_type = 'service' and entity_id = %s
        """
        cursor.execute(query, (service_id,))
        #insert new tag
        query = """
            insert into entity_tags (entity_type, entity_id, tag_id)
            values(%s, %s, %s)
        """
        cursor.execute(query, ('service', service_id, tag_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Service updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to update service', 'details': str(e)}), 500

@services_bp.route('/salon/<int:salon_id>/services/delete/<int:service_id>', methods=['DELETE'])
def delete_service(salon_id, service_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = "delete from entity_tags where entity_type = 'service' and entity_id = %s"
        cursor.execute(query, (service_id,))
        query = "delete from services where service_id = %s and salon_id = %s"
        cursor.execute(query, (service_id, salon_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Service deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to delete service', 'details': str(e)}), 500
