from flask import Blueprint, request, jsonify, session, current_app, url_for
from werkzeug.security import check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flasgger import swag_from
from utils.logerror import log_error
from utils.emails import send_email
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
    cursor.close()
    #check if user exists
    if not user:
        log_error("Invalid login attempt for username: {}".format(username), None)
        return jsonify({'error': 'Invalid username or password'}), 401
    
    #check if password is correct
    user_id, hashed_password = user
    if not check_password_hash(hashed_password, password):
        log_error("Invalid login attempt for username: {}".format(username), None)
        return jsonify({'error': 'Invalid username or password'}), 401
    
    session['user_id'] = user_id
    session['username'] = username
    return jsonify({'message': 'Login successful'}), 200

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
        return jsonify({'authenticated': True, 'username': session.get('username')}), 200
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


@login_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400
    try:  
      mysql = current_app.config['MYSQL']
      cursor = mysql.connection.cursor()
      cursor.execute("select user_id from users where email = %s", (email,))
      user = cursor.fetchone()
      cursor.close()

      if not user:
        return jsonify({"message": "If the email exists, a reset link will be sent"}), 200

      user_id = user[0]

      #generate token and link
      serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
      token = serializer.dumps({"user_id": user_id}, salt="password-reset-salt")
      reset_url = url_for("login.reset_password", token=token, _external=True)

      #send email
      subject = "Password Reset Request"
      body = f"""
      We received a request to reset your password.
      Click the link below to reset it:

      {reset_url}

      This link expires in 30 minutes.
      """

      send_email(to=email, subject=subject, body=body)

      return jsonify({"message": "If the email exists, a reset link will be sent"}), 200
    except Exception as e:
      log_error(str(e), session.get("user_id"))
      return jsonify({"error": "This email does not exist"}), 500
    
