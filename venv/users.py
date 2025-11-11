from flask import Blueprint, request, jsonify, session
from flask import current_app

users_bp = Blueprint('users', __name__)


#User details page
@users_bp.route('/userDetails', methods=['POST'])
def userDetails():
    try:
        data = request.get_json()
        user_id = data["user_id"]

        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = mysql.connection.cursor()
        cursor.execute("""
            select *
            from users
            where user_id = %s
        """, (user_id,))

        result = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        user_data = dict(zip(columns, result))
        cursor.close() 
        return jsonify(user_data), 200
    
    except Exception as e:
        return jsonify({'error': 'Failed to fetch user details', 'details': str(e)}), 500