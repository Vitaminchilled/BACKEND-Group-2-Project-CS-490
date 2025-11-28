from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from datetime import datetime
from flask import current_app

register_bp = Blueprint('register', __name__)

#registering users (default page)
@register_bp.route('/register/page', methods=['POST'])
def register_page():
    """
Initial registration page - validate username and password
---
tags:
  - Registration
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
        password_confirm:
          type: string
      required:
        - username
        - password
        - password_confirm
responses:
  200:
    description: Username and password validated, proceed to next step
  400:
    description: Missing fields, passwords don't match, or username exists
"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    password_confirm = data.get('password_confirm')

    #check if form is filled out, passwords match
    if not all([username, password, password_confirm]):
        return jsonify({'error': 'Missing required fields'}), 400
    if password != password_confirm:
        return jsonify({'error': 'Passwords do not match'}), 400
    
    mysql = current_app.config['MYSQL']
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
@register_bp.route('/register/customer', methods=['POST'])
def register_customer():
    """
Complete customer registration
---
tags:
  - Registration
consumes:
  - application/json
parameters:
  - in: body
    name: body
    required: true
    schema:
      type: object
      properties:
        first_name:
          type: string
        last_name:
          type: string
        email:
          type: string
          format: email
        phone_number:
          type: string
        gender:
          type: string
        birth_year:
          type: integer
      required:
        - first_name
        - last_name
        - email
        - phone_number
        - gender
        - birth_year
responses:
  201:
    description: Customer registered successfully
  400:
    description: Missing fields, session expired, or email/phone already exists
  500:
    description: Registration failed
"""
    username = session.get('register_username')
    password = session.get('register_password') #already hashed 
    if not username or not password:
        return jsonify({'error': 'Session expired. Please start registration again.'}), 400
    
    data = request.get_json()
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone_number = data.get('phone_number')
    gender = data.get('gender')
    birth_year = data.get('birth_year')

    #check if form is filled out
    if not all([first_name, last_name, email, phone_number, gender, birth_year, username, password]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    mysql = current_app.config['MYSQL']
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
@register_bp.route('/register/salon', methods=['POST'])
def register_salon():
    """
Complete salon owner registration
---
tags:
  - Registration
consumes:
  - application/json
parameters:
  - in: body
    name: body
    required: true
    schema:
      type: object
      properties:
        first_name:
          type: string
        last_name:
          type: string
        personal_email:
          type: string
          format: email
        personal_email_confirm:
          type: string
          format: email
        birth_year:
          type: integer
        phone_number:
          type: string
        gender:
          type: string
        salon_name:
          type: string
        description:
          type: string
        salon_email:
          type: string
          format: email
        salon_email_confirm:
          type: string
          format: email
        salon_phone_number:
          type: string
        salon_address:
          type: string
        salon_city:
          type: string
        salon_state:
          type: string
        salon_postal_code:
          type: string
        salon_country:
          type: string
        master_tag_ids:
          type: array
          items:
            type: integer
      required:
        - first_name
        - last_name
        - personal_email
        - personal_email_confirm
        - birth_year
        - phone_number
        - gender
        - salon_name
        - salon_email
        - salon_email_confirm
        - salon_phone_number
        - salon_address
        - salon_city
        - salon_state
        - salon_postal_code
        - salon_country
        - master_tag_ids
responses:
  201:
    description: Salon and owner registered successfully
  400:
    description: Missing fields, emails don't match, or business details already exist
  500:
    description: Registration failed
    """
    username = session.get('register_username')
    password = session.get('register_password') #already hashed
    if not username or not password:
        return jsonify({'error': 'Session expired. Please start registration again.'}), 400
    
    data = request.get_json()
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    personal_email = data.get('personal_email')
    personal_email_confirm = data.get('personal_email_confirm')
    birth_year = data.get('birth_year')
    phone_number = data.get('phone_number')
    gender = data.get('gender') #Male | Female 

    salon_name = data.get('salon_name')
    description = data.get('description')
    salon_email = data.get('salon_email')
    salon_email_confirm = data.get('salon_email_confirm')
    salon_phone_number = data.get('salon_phone_number')
    salon_address = data.get('salon_address')
    salon_city = data.get('salon_city')
    salon_state = data.get('salon_state')
    salon_postal_code = data.get('salon_postal_code')
    salon_country = data.get('salon_country')
    master_tag_ids = data.get('master_tag_ids')

    #check if form is filled out, emails match 
    required_fields = [first_name, last_name, personal_email, personal_email_confirm, birth_year,
                       phone_number, gender, salon_name, salon_email, salon_email_confirm,
                       salon_phone_number, salon_address, salon_city, salon_state, salon_postal_code,
                       salon_country, master_tag_ids, username, password]
    if not all(required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    if personal_email != personal_email_confirm:
        return jsonify({'error': 'Emails do not match'}), 400
    if salon_email != salon_email_confirm:
        return jsonify({'error': 'Emails do not match'}), 400
    if master_tag_ids and not isinstance(master_tag_ids, list):
        return jsonify({'error': 'master_tag_ids must be a list'}), 400
    
    mysql = current_app.config['MYSQL']
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
            insert into salons(owner_id, name, description, email, phone_number, created_at, last_modified)
            values(%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(query, (owner_id, salon_name, description, salon_email, salon_phone_number, now, now))
        salon_id = cursor.lastrowid 

        #insert new salon address into addresses table
        query = """
            insert into addresses(entity_type, salon_id, customer_id, address, city, state, postal_code, country, created_at, last_modified)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(query, ('salon', salon_id, None, salon_address, salon_city, salon_state, salon_postal_code, salon_country, now, now))
        
        #insert salon tags
        if master_tag_ids:
            for master_tag_id in master_tag_ids:
                cursor.execute(
                    "insert ignore into entity_master_tags(entity_type, entity_id, master_tag_id) values (%s, %s, %s)",
                    ('salon', salon_id, master_tag_id)
                )
        
        mysql.connection.commit()
        session.pop('register_username', None)
        session.pop('register_password', None)
        return jsonify({'message': 'Salon registered successfully'}), 201
    
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
