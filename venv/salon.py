from flask import Blueprint, request, jsonify, session
from flask import current_app

salon_bp = Blueprint('salon', __name__)

#Can be used on Landing to salon names and their rating
@salon_bp.route('/salonData', methods=['GET'])
def salonData():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select s.name, sa.average_rating
            from salons s
            join salon_analytics sa on sa.salon_id = s.salon_id
            limit 6
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        data = [dict(zip(columns, row)) for row in rows]
        return jsonify({'salons': data}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500

@salon_bp.route('/salonsToVerify', methods=['GET'])
def salonsToVerify():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select 	s.name,
                    s.email,
                    s.phone_number,
                    s.created_at,
                    a.address,
                    a.city,
                    a.state,
                    a.postal_code,
                    a.country,
                    u.first_name as owner_first_name,
                    u.last_name as owner_last_name,
                    u.email as owner_email,
                    u.phone_number as owner_phone_number,
                    u.birth_year as owner_birth_year
            from salons s 
            join users u on u.user_id = s.owner_id
            join addresses a on a.salon_id = s.salon_id;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        cursor.close()
        data = [dict(zip(cols, row)) for row in rows]

        return jsonify({'salons': data}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500