from flask import Blueprint, request, jsonify, session
from flask import current_app

services_bp = Blueprint('services', __name__)

@services_bp.route('/salon/services/<int:salon_id>', methods=['GET'])
def get_services(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        salon_query = """
            select salon_id
            from salons
            where salon_id=%s
        """
        cursor.execute(salon_query, (salon_id,))
        salon = cursor.fetchone()
        if not salon:
            return jsonify({"error": "Salon not found"}), 404

        query = """
            select service_id, services.master_tag_id, services.name, master_tags.name as tag_name, description, duration_minutes, price, is_active
            from services
            join master_tags 
            on master_tags.master_tag_id = services.master_tag_id
            where salon_id=%s
        """
        cursor.execute(query, (salon_id,))
        services = cursor.fetchall()
        cursor.close()
        return jsonify({
            'services': [{
                "service_id": service[0], 
                "master_tag_id": service[1], 
                "service_name": service[2], 
                "master_tag_name": service[3], 
                "description": service[4], 
                "duration_minutes": service[5], 
                "price": service[6], 
                "is_active": service[7]
            } for service in services]
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch services', 'details': str(e)}), 500
    
@services_bp.route('/salon/<int:salon_id>/services/add', methods=['POST'])
def add_service(salon_id):
    data = request.get_json()
    #check if the form is filled out 
    required_fields = ['tag_name', 'name', 'description', 'duration_minutes', 'price']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    #find master_tag_id and tag_id by tag name
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()
    query = """
        select tags.tag_id, master_tags.master_tag_id
        from tags
        join master_tags on master_tags.master_tag_id = tags.master_tag_id
        where tags.name = %s
    """
    cursor.execute(query, (data['tag_name'],))
    tag_info = cursor.fetchone()
    tag_id, master_tag_id = tag_info

    try:
        name = data['name']
        description = data['description']
        duration_minutes = data['duration_minutes']
        price = data['price']

        #create new entry on the services table
        query = """
            insert into services(salon_id, master_tag_id, name, description, duration_minutes, price)
            values(%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, master_tag_id, name, description, duration_minutes, price))
        mysql.connection.commit()
        cursor.close()

        return jsonify({'message': 'Service added successfully'}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to add service', 'details': str(e)}), 500

@services_bp.route('/salon/services/edit/<int:service_id>', methods=['PUT'])
def edit_service(service_id):
    data = request.get_json()
    #check if the form is filled out/there is autofilled data
    required_fields = ['tag_name', 'name', 'description', 'duration_minutes', 'price', 'is_active']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    #convert tag name to master_tag_id
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()
    query = """
    select master_tags.master_tag_id
    from tags
    join master_tags on master_tags.master_tag_id = tags.master_tag_id
    where tags.name = %s
    """
    cursor.execute(query, (data['tag_name'],))
    result = cursor.fetchone()
    master_tag_id = result[0] if result else None

    try:
        name = data['name']
        description = data['description']
        duration_minutes = data['duration_minutes']
        price = data['price']
        is_active = data['is_active']

        #update the service entry
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

@services_bp.route('/salon/services/delete/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = "delete from services where service_id=%s"
        cursor.execute(query, (service_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Service deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to delete service', 'details': str(e)}), 500
