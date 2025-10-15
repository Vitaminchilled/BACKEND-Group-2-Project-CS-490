from flask import Flask, jsonify, session, request
from flask_mysqldb import MySQL
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'G76D-U89V-576V-7BT6'
CORS(app)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '5283' #put your own mysql password here
app.config['MYSQL_DB'] = 'sakila' #put your own database name here
mysql = MySQL(app)
#------------------------------------------------------#

#registering users (default page)
@app.route('/register/page', methods=['POST'])
def register_page():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    password_confirm = data.get('password_confirm')

    #check if form is filled out, passwords match
    if not all([username, password, password_confirm]):
        return jsonify({'error': 'Missing required fields'}), 400
    if password != password_confirm:
        return jsonify({'error': 'Passwords do not match'}), 400
    
    cursor = mysql.connection.cursor()

    #check is username exists 
    cursor.execute("""select * from users where username = %s """, (username,))
    if cursor.fetchone():
        cursor.close()  
        return jsonify({'error': 'This user already exists'}), 400
    
    hashed_password = generate_password_hash(password)
    #send username and password to next page
    session['register_username'] = username
    session['register_password'] = hashed_password
    
    return jsonify({'message': 'Proceed to next page'}), 200

#registering customers (next page)
@app.route('/register/proceed', methods=['POST'])
def register_customer():
    data = request.get_json()
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone_number = data.get('phone_number')
    gender = data.get('gender')
    birth_year = data.get('birth_year')
    username = session.get('register_username')
    password = session.get('register_password') #already hashed 

    #check if form is filled out
    if not all([first_name, last_name, email, phone_number, gender, birth_year, username, password]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    cursor = mysql.connection.cursor()

    #check if email exists
    cursor.execute("""select * from users where email = %s""", (email,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'This email is already in use'}), 400
    
    #check if phone number exists 
    cursor.execute("""select * from users where phone_number = %s""", (phone_number,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'This phone number is already in use'}), 400
    
    #insert new user into mysql 
    now = datetime.now()
    try:
        query = """
            insert into users(role, first_name, last_name, username, password, email, phone_number, gender, birth_year, last_login, created_at, last_modified)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(query, ('customer', first_name, last_name, username, password, email, phone_number, gender, birth_year, now, now, now))
        mysql.connection.commit()
        session.pop('register_username', None)
        session.pop('register_password', None)
        return jsonify({'message': 'User registered successfully'}), 201
    
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#register salons (alternative next page)
@app.route('/register/salon', methods=['POST'])
def register_salon():
    data = request.get_json()
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    personal_email = data.get('personal_email')
    personal_email_confirm = data.get('personal_email_confirm')
    birth_year = data.get('birth_year')
    phone_number = data.get('phone_number')
    gender = data.get('gender') #Male | Female 

    salon_category = data.get('salon_category') #1, 2, 3, 4, 5, 6, 7
    salon_name = data.get('salon_name')
    salon_email = data.get('salon_email')
    salon_email_confirm = data.get('salon_email_confirm')
    salon_phone_number = data.get('salon_phone_number')
    salon_address = data.get('salon_address')
    salon_city = data.get('salon_city')
    salon_state = data.get('salon_state')
    salon_postal_code = data.get('salon_postal_code')
    salon_country = data.get('salon_country')
    username = session.get('register_username')
    password = session.get('register_password') #already hashed

    #check if form is filled out, emails match 
    required_fields = [first_name, last_name, personal_email, personal_email_confirm, birth_year,
                       phone_number, gender, salon_category, salon_name, salon_email, salon_email_confirm,
                       salon_phone_number, salon_address, salon_city, salon_state, salon_postal_code,
                       salon_country, username, password]
    if not all(required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    if personal_email != personal_email_confirm:
        return jsonify({'error': 'Emails do not match'}), 400
    if salon_email != salon_email_confirm:
        return jsonify({'error': 'Emails do not match'}), 400
    
    cursor = mysql.connection.cursor()

    #check if business name, personal email, salon email, personal phone number or salon phone number exists
    cursor.execute("""select * from salons where name = %s """, (salon_name,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'This name already exists'}), 400
    cursor.execute("""select * from users where email = %s""", (personal_email,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'This personal email is already in use'}), 400
    cursor.execute("""select * from salons where email = %s""", (salon_email,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'This salon email is already in use'}), 400
    cursor.execute("""select * from users where phone_number = %s""", (phone_number,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'This personal phone number is already in use'}), 400
    cursor.execute("""select * from salons where phone_number = %s""", (salon_phone_number,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'This salon phone number is already in use'}), 400
    
    try:
        mysql.connection.begin()
        now = datetime.now()

        #insert new salon owner into users table
        query = """
            insert into users(role, first_name, last_name, username, password, email, phone_number, gender, birth_year, last_login, created_at, last_modified)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(query, ('owner', first_name, last_name, username, password, personal_email, phone_number, gender, birth_year, now, now, now))
        owner_id = cursor.lastrowid 

        #insert new salon into salons table
        query = """
            insert into salons(owner_id, master_tag_id, name, description, email, phone_number, operating_hours, created_at, last_modified)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(query, (owner_id, salon_category, salon_name, None, salon_email, salon_phone_number, None, now, now))
        salon_id = cursor.lastrowid 

        #insert new salon address into addresses table
        query = """
            insert into addresses(entity_type, salon_id, customer_id, address, city, state, postal_code, country, created_at, last_modified)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(query, ('salon', salon_id, None, salon_address, salon_city, salon_state, salon_postal_code, salon_country, now, now))
        mysql.connection.commit()
        session.pop('register_username', None)
        session.pop('register_password', None)
        return jsonify({'message': 'Salon registered successfully'}), 201
    
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

if __name__ == '__main__':
    app.run(debug=True)
