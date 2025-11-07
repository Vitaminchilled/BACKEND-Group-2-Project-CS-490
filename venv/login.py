from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash
from flask import current_app

login_bp = Blueprint('login', __name__)

@login_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    #check if form is filled out
    if not username or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()
    cursor.execute("""select user_id, password from users where username = %s""", (username,))
    user = cursor.fetchone()
    cursor.close()
    #check if user exists
    if not user:
        return jsonify({'error': 'Invalid username or password'}), 401
    
    #check if password is correct
    user_id, hashed_password = user
    if not check_password_hash(hashed_password, password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    session['user_id'] = user_id
    session['username'] = username
    return jsonify({'message': 'Login successful'}), 200

@login_bp.route('/auth/status', methods=['GET'])
def auth_status():
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'username': session.get('username')}), 200
    else:
        return jsonify({'authenticated': False}), 200
    
@login_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200