from flask import Blueprint, request, jsonify, session
from flask import current_app
import json
from utils.logerror import log_error

services_bp = Blueprint('services', __name__)

@services_bp.route('/salon/<int:salon_id>/services', methods=['GET'])
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
            select s.service_id, 
                    s.name,
                    (
                        select COALESCE(
                            JSON_ARRAYAGG(
                                t.name
                            ), JSON_ARRAY()
                        )
                        from entity_tags e
                        left join tags t on t.tag_id = e.tag_id
                        where e.entity_id = s.service_id and e.entity_type = 'service'
                    ) as tag_names,
                    s.description, 
                    s.duration_minutes, 
                    s.price,
                    s.is_active
            from services s
            where s.salon_id=%s
        """
        cursor.execute(query, (salon_id,))
        services = cursor.fetchall()

        result = []
        for service in services:
            try:
                tags = json.loads(service[2]) if service[2] else []
            except Exception:
                tags = []

            result.append({
                "service_id": service[0], 
                "name": service[1], 
                "tags": tags, 
                "description": service[3], 
                "duration_minutes": service[4], 
                "price": service[5], 
                "is_active": service[6]
            })

        cursor.close()
        return jsonify({'services': result}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to fetch services', 'details': str(e)}), 500
    
@services_bp.route('/salon/<int:salon_id>/services/add', methods=['POST'])
def add_service(salon_id):
    data = request.get_json()

    #check if the form is filled out 
    required_fields = ['tags', 'name', 'description', 'duration_minutes', 'price']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    try: 
        tags = data['tags']
        name = data['name']
        description = data['description']
        duration_minutes = data['duration_minutes']
        price = data['price']

        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        #create new entry on the services table
        query = """
            insert into services(salon_id, name, description, duration_minutes, price)
            values(%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, name, description, duration_minutes, price))
        service_id = cursor.lastrowid

        for tag_name in tags:
            cursor.execute("select tag_id from tags where name = %s", (tag_name,))
            tag = cursor.fetchone()
            if not tag:
                return jsonify({"error": f"Tag '{tag_name}' does not exist"}), 400
            #insert into entity tags
            tag_id = tag[0]
            query = """
                insert into entity_tags (entity_type, entity_id, tag_id)
                values(%s, %s, %s)
            """
            cursor.execute(query, ('service', service_id, tag_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Service added successfully'}), 201
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to add service', 'details': str(e)}), 500

@services_bp.route('/salon/<int:salon_id>/services/<int:service_id>/edit', methods=['PUT'])
def edit_service(salon_id, service_id):
    data = request.get_json()
    #check if the form is filled out/there is autofilled data
    required_fields = ['tags', 'name', 'description', 'duration_minutes', 'price', 'is_active']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        tags = data['tags']
        name = data['name']
        description = data['description']
        duration_minutes = data['duration_minutes']
        price = data['price']
        is_active = data['is_active']
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

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
        for tag_name in tags:
            cursor.execute("SELECT tag_id FROM tags WHERE name=%s", (tag_name,))
            tag = cursor.fetchone()
            if not tag:
                return jsonify({"error": f"Tag '{tag_name}' does not exist"}), 400
            tag_id = tag[0]
            query = """
                insert into entity_tags (entity_type, entity_id, tag_id)
                values(%s, %s, %s)
            """
            cursor.execute(query, ('service', service_id, tag_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Service updated successfully'}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to update service', 'details': str(e)}), 500

@services_bp.route('/salon/<int:salon_id>/services/<int:service_id>', methods=['DELETE'])
def delete_service(salon_id, service_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        check_query = 'select count(*) from services where salon_id=%s'
        cursor.execute(check_query, (salon_id,))
        service_count = cursor.fetchone()[0]
        if service_count == 1:
            return jsonify({"error": "Salon must have at least one service. Cannot delete last instance."}), 409 #maybe 400???

        query = "delete from entity_tags where entity_type = 'service' and entity_id = %s"
        cursor.execute(query, (service_id,))
        query = "delete from services where service_id = %s and salon_id = %s"
        cursor.execute(query, (service_id, salon_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Service deleted successfully'}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to delete service', 'details': str(e)}), 500