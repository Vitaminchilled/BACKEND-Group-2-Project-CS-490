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
            order by sa.average_rating desc
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