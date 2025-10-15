from flask import Flask, jsonify, request
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '5283'
app.config['MYSQL_DB'] = 'sakila'
mysql = MySQL(app)
#------------------------------------------------------#

#registering users (default page)
@app.route('/register/page', methods=['POST'])
def register_page():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    password_confirm = data.get('password_confirm')

    #check if form is filled out, passwords match
    if not all([username, password, password_confirm]):
        return jsonify({'error': 'Missing required fields'}), 400
    if password != password_confirm:
        return jsonify({'error': 'Passwords do not match'}), 400
    
    password = generate_password_hash(password)
    cursor = mysql.connection.cursor()

    #check is username exists 
    cursor.execute("""select * from users where username = %s """, (username,))
    if cursor.fetchone():
        return jsonify({'error': 'This user already exists'}), 400
    
    #send username and password to next page
    return jsonify({
    'message': 'Username is available',
    'username': username,
    'password': password
    }), 200

#registering customers (next page)
@app.route('/register/proceed', methods=['POST'])
def register_customer():
    data = request.json
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone_number = data.get('phone_number')
    gender = data.get('gender')
    birth_year = data.get('birth_year')
    username = data.get('username')
    password = data.get('password')

    #check if form is filled out
    if not all([first_name, last_name, email, phone_number, gender, birth_year, username, password]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    cursor = mysql.connection.cursor()

    #check if email exists
    cursor.execute("""select * from users where email = %s""", (email,))
    if cursor.fetchone():
        return jsonify({'error': 'This email is already in use'}), 400
    
    #check if phone number exists 
    cursor.execute("""select * from users where phone_number = %s""", (phone_number,))
    if cursor.fetchone():
        return jsonify({'error': 'This phone number is already in use'}), 400
    
    #insert new user into mysql 
    from datetime import datetime
    now = datetime.now()
    try:
        query = """
            insert into users(role, first_name, last_name, username, password, email, phone_number, gender, birth_year, last_login, created_at, last_modified)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(query, ('customer', first_name, last_name, username, password, email, phone_number, gender, birth_year, now(), now(), now()))

        mysql.connection.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

@app.route('/register/salon', methods=['POST'])
def register_salon():
    data = request.json
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    personal_email = data.get('personal_email')
    birth_year = data.get('birth_year')
    phone_number = data.get('phone_number')
    salon_name = data.get('salon_name')
    salon_email = data.get('salon_email')
    salon_phone_number = data.get('salon_phone_number')
    salon_address = data.get('salon_address')
    salon_city = data.get('salon_city')
    salon_state = data.get('salon_state')
    salon_postal_code = data.get('salon_postal_code')
    salon_country = data.get('salon_country')
    username = data.get('username')
    password = data.get('password')

