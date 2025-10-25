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
        cursor.close()
        #Sending data in this format makes it way easier to iterate through
        data = [{"name": row[0], "average_rating": row[1]} for row in rows]
        return jsonify({'salons': data}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500
