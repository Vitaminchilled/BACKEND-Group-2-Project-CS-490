from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash
from flask import current_app
from flasgger import swag_from
from utils.logerror import log_error

login_bp = Blueprint('login', __name__)

@login_bp.route('/login', methods=['POST'])
def login():
    """
    User Login
    ---
    tags:
      - Authentication
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
            password:
              type: string
    responses:
      200:
        description: Login successful
      400:
        description: Missing required fields
      401:
        description: Invalid username or password
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    #check if form is filled out
    if not username or not password:
        log_error("Login attempt with missing fields", None)
        return jsonify({'error': 'Missing required fields'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()
    cursor.execute("""select user_id, password from users where username = %s""", (username,))
    user = cursor.fetchone()
    
    #check if user exists
    if not user:
        cursor.close()
        log_error("Invalid login attempt for username: {}".format(username), None)
        return jsonify({'error': 'Invalid username or password'}), 401
    
    #check if password is correct
    user_id, hashed_password = user
    if not check_password_hash(hashed_password, password):
        cursor.close()
        log_error("Invalid login attempt for username: {}".format(username), None)
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # Get first_name
    first_name = None
    try:
        cursor.execute("select first_name from users where user_id = %s limit 1", (user_id,))
        r = cursor.fetchone()
        if r and r[0]:
            first_name = r[0]
    except Exception:
        first_name = None

    # Get role
    role = None
    try:
        cursor.execute("select role from users where user_id = %s limit 1", (user_id,))
        r = cursor.fetchone()
        if r and r[0]:
            role = str(r[0]).lower()
    except Exception:
        role = None

    # Get salon_id and is_verified for salon owners
    salon_id = None
    is_verified = None
    
    if role == 'owner':
        try:
            cursor.execute("select salon_id, is_verified from salons where owner_id = %s limit 1", (user_id,))
            r = cursor.fetchone()
            if r:
                salon_id = r[0]
                is_verified = bool(r[1]) if r[1] is not None else False
        except Exception as e:
            log_error(f"Error fetching salon: {e}", user_id)
            salon_id = None
            is_verified = None

    cursor.close()

    if not role:
        role = 'customer'
    if not first_name or str(first_name).strip() == "":
        first_name = username

    session['user_id'] = user_id
    session['username'] = username
    session['first_name'] = first_name
    session['role'] = role
    session['salon_id'] = salon_id
    session['is_verified'] = is_verified
    
    return jsonify({
        'message': 'Login successful',
        'user_id': user_id,
        'first_name': first_name,
        'role': role,
        'salon_id': salon_id,
        'is_verified': is_verified
    }), 200

@login_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """
    Authentication Status
    ---
    tags:
      - Authentication
    responses:
      200:
        description: Returns whether the user is authenticated
    """
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'username': session.get('username'),
            'first_name': session.get('first_name'),
            'user_id': session.get('user_id'),
            'role': session.get('role'),
            'salon_id': session.get('salon_id'),
            'is_verified': session.get('is_verified')
        }), 200
    else:
        return jsonify({'authenticated': False}), 200
    
@login_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout
    ---
    tags:
      - Authentication
    responses:
      200:
        description: Logout successful
    """
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200
