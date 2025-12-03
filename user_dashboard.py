from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta, time as dt_time, date
from MySQLdb.cursors import DictCursor

user_dashboard_bp = Blueprint('user_dashboard_bp', __name__)

def convert_mysql_objects(obj):
    if isinstance(obj, timedelta):
        total_seconds = int(obj.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    elif isinstance(obj, (datetime, date, dt_time)):
        return obj.isoformat()

    elif isinstance(obj, list):
        return [convert_mysql_objects(x) for x in obj]

    elif isinstance(obj, dict):
        return {k: convert_mysql_objects(v) for k, v in obj.items()}

    return obj

# to populate user dash

@user_dashboard_bp.route('/user_dashboard', methods=['GET'])
def customer_dashboard():
    customer_id = request.args.get('customer_id')

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Get user profile
        cursor.execute("""
            SELECT user_id, first_name, last_name, email, phone_number, gender, birth_year, created_at
            FROM users
            WHERE user_id = %s AND role = 'customer'
        """, (customer_id,))
        profile = cursor.fetchone()
        if profile:
            profile = dict(profile)


        if not profile:
            return jsonify({'error': 'Customer not found'}), 404

        # Upcoming appointments
        cursor.execute("""
            SELECT a.appointment_id, a.appointment_date, a.start_time, a.end_time, a.status,
                   s.name AS salon_name, sv.name AS service_name
            FROM appointments a
            JOIN salons s ON a.salon_id = s.salon_id
            JOIN services sv ON a.service_id = sv.service_id
            WHERE a.customer_id = %s AND a.status = 'booked' AND a.appointment_date >= CURDATE()
            ORDER BY a.appointment_date ASC
        """, (customer_id,))
        upcoming_appointments = [dict(row) for row in cursor.fetchall()]

        # Past appointments
        cursor.execute("""
            SELECT a.appointment_id, a.appointment_date, a.start_time, a.end_time, a.status,
                   s.name AS salon_name, sv.name AS service_name
            FROM appointments a
            JOIN salons s ON a.salon_id = s.salon_id
            JOIN services sv ON a.service_id = sv.service_id
            WHERE a.customer_id = %s AND a.appointment_date < CURDATE()
            ORDER BY a.appointment_date DESC
        """, (customer_id,))
        past_appointments = [dict(row) for row in cursor.fetchall()]

        # Payment history
        cursor.execute("""
            SELECT i.invoice_id, i.issued_date, i.total_amount, i.status,
                   s.name AS salon_name
            FROM invoices i
            LEFT JOIN appointments a ON i.appointment_id = a.appointment_id
            LEFT JOIN salons s ON a.salon_id = s.salon_id
            WHERE i.customer_id = %s
            ORDER BY i.issued_date DESC
        """, (customer_id,))
        payment_history = [dict(row) for row in cursor.fetchall()]

        # Verified salons and employees
        cursor.execute("""
            SELECT s.salon_id, s.name AS salon_name, s.email, s.phone_number,
                   e.employee_id, e.first_name AS employee_first_name, e.last_name AS employee_last_name
            FROM salons s
            LEFT JOIN employees e ON s.salon_id = e.salon_id
            WHERE s.is_verified = TRUE
            ORDER BY s.name ASC
        """)
        verified_salons = [dict(row) for row in cursor.fetchall()]

        response_data = {
            'profile': profile,
            'upcoming_appointments': upcoming_appointments,
            'past_appointments': past_appointments,
            'payment_history': payment_history,
            'verified_salons': verified_salons
        }

        return jsonify(convert_mysql_objects(response_data)), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()


# searching of salons

@user_dashboard_bp.route('/search_salons', methods=['GET'])
def search_salons():
    """
    Search salons by various criteria including name, location, and tags
    """
    search_query = request.args.get('q', '')
    city = request.args.get('city', '')
    state = request.args.get('state', '')
    master_tag = request.args.get('master_tag', '')
    tag_name = request.args.get('tag', '')
    verified_only = request.args.get('verified_only', 'false').lower() == 'true'
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        query = """
            SELECT DISTINCT s.salon_id, s.name, s.description, s.email, s.phone_number, 
                   s.is_verified, s.created_at,
                   a.address, a.city, a.state, a.postal_code,
                   GROUP_CONCAT(DISTINCT mt.name) as master_tags,
                   GROUP_CONCAT(DISTINCT t.name) as specific_tags,
                   AVG(r.rating) as average_rating,
                   COUNT(r.review_id) as review_count
            FROM salons s
            LEFT JOIN addresses a ON s.salon_id = a.salon_id AND a.entity_type = 'salon'
            LEFT JOIN entity_master_tags emt ON s.salon_id = emt.entity_id AND emt.entity_type = 'salon'
            LEFT JOIN master_tags mt ON emt.master_tag_id = mt.master_tag_id
            LEFT JOIN entity_tags et ON s.salon_id = et.entity_id AND et.entity_type = 'service'
            LEFT JOIN tags t ON et.tag_id = t.tag_id
            LEFT JOIN reviews r ON s.salon_id = r.salon_id
            WHERE 1=1
        """
        
        params = []
        
        if search_query:
            query += " AND (s.name LIKE %s OR s.description LIKE %s)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        
        if city:
            query += " AND a.city LIKE %s"
            params.append(f'%{city}%')
            
        if state:
            query += " AND a.state = %s"
            params.append(state)
            
        if master_tag:
            query += " AND mt.name = %s"
            params.append(master_tag)
            
        if tag_name:
            query += " AND t.name = %s"
            params.append(tag_name)
            
        if verified_only:
            query += " AND s.is_verified = TRUE"
        
        query += """
            GROUP BY s.salon_id, s.name, s.description, s.email, s.phone_number, 
                     s.is_verified, s.created_at, a.address, a.city, a.state, a.postal_code
            ORDER BY s.is_verified DESC, average_rating DESC, s.name ASC
        """
        
        cursor.execute(query, params)
        salons = [dict(row) for row in cursor.fetchall()]
        
        for salon in salons:
            if salon['master_tags']:
                salon['master_tags'] = list(set(salon['master_tags'].split(',')))
            else:
                salon['master_tags'] = []
                
            if salon['specific_tags']:
                salon['specific_tags'] = list(set(salon['specific_tags'].split(',')))
            else:
                salon['specific_tags'] = []
        
        return jsonify(convert_mysql_objects({
            'salons': salons,
            'count': len(salons)
        })), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Get all available master tags for filtering

@user_dashboard_bp.route('/available_master_tags', methods=['GET'])
def get_available_master_tags():

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("""
            SELECT mt.master_tag_id, mt.name, COUNT(DISTINCT emt.entity_id) as salon_count
            FROM master_tags mt
            LEFT JOIN entity_master_tags emt ON mt.master_tag_id = emt.master_tag_id AND emt.entity_type = 'salon'
            GROUP BY mt.master_tag_id, mt.name
            ORDER BY salon_count DESC, mt.name ASC
        """)
        
        master_tags = [dict(row) for row in cursor.fetchall()]
        
        return jsonify(convert_mysql_objects({
            'master_tags': master_tags
        })), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Get info about specific salon

@user_dashboard_bp.route('/salon_details/<int:salon_id>', methods=['GET'])
def get_salon_details(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("""
            SELECT s.salon_id, s.name, s.description, s.email, s.phone_number, 
                   s.is_verified, s.created_at,
                   a.address, a.city, a.state, a.postal_code,
                   u.first_name as owner_first_name, u.last_name as owner_last_name
            FROM salons s
            LEFT JOIN addresses a ON s.salon_id = a.salon_id AND a.entity_type = 'salon'
            LEFT JOIN users u ON s.owner_id = u.user_id
            WHERE s.salon_id = %s
        """, (salon_id,))
        
        salon = cursor.fetchone()
        if not salon:
            return jsonify({'error': 'Salon not found'}), 404
            
        salon = dict(salon)
        
        # Get master tags
        cursor.execute("""
            SELECT mt.master_tag_id, mt.name
            FROM entity_master_tags emt
            JOIN master_tags mt ON emt.master_tag_id = mt.master_tag_id
            WHERE emt.entity_type = 'salon' AND emt.entity_id = %s
        """, (salon_id,))
        salon['master_tags'] = [dict(row) for row in cursor.fetchall()]
        
        # Get services
        cursor.execute("""
            SELECT service_id, name, description, duration_minutes, price
            FROM services
            WHERE salon_id = %s AND is_active = TRUE
            ORDER BY price ASC
        """, (salon_id,))
        salon['services'] = [dict(row) for row in cursor.fetchall()]
        
        # Get employees
        cursor.execute("""
            SELECT e.employee_id, e.first_name, e.last_name, e.description,
                   GROUP_CONCAT(DISTINCT mt.name) as specialties
            FROM employees e
            LEFT JOIN entity_master_tags emt ON e.employee_id = emt.entity_id AND emt.entity_type = 'employees'
            LEFT JOIN master_tags mt ON emt.master_tag_id = mt.master_tag_id
            WHERE e.salon_id = %s
            GROUP BY e.employee_id, e.first_name, e.last_name, e.description
        """, (salon_id,))
        
        employees = []
        for row in cursor.fetchall():
            employee = dict(row)
            if employee['specialties']:
                employee['specialties'] = employee['specialties'].split(',')
            else:
                employee['specialties'] = []
            employees.append(employee)
        
        salon['employees'] = employees
        
        # Get operating hours
        cursor.execute("""
            SELECT day, open_time, close_time, is_closed
            FROM operating_hours
            WHERE salon_id = %s
            ORDER BY FIELD(day, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        """, (salon_id,))
        salon['operating_hours'] = [dict(row) for row in cursor.fetchall()]
        
        # Get reviews summary
        cursor.execute("""
            SELECT 
                AVG(rating) as average_rating,
                COUNT(*) as total_reviews,
                COUNT(CASE WHEN rating = 5 THEN 1 END) as five_star,
                COUNT(CASE WHEN rating = 4 THEN 1 END) as four_star,
                COUNT(CASE WHEN rating = 3 THEN 1 END) as three_star,
                COUNT(CASE WHEN rating = 2 THEN 1 END) as two_star,
                COUNT(CASE WHEN rating = 1 THEN 1 END) as one_star
            FROM reviews
            WHERE salon_id = %s
        """, (salon_id,))
        salon['reviews_summary'] = dict(cursor.fetchone())
        
        # Get recent reviews
        cursor.execute("""
            SELECT r.review_id, r.rating, r.comment, r.review_date,
                   u.first_name, u.last_name
            FROM reviews r
            JOIN users u ON r.customer_id = u.user_id
            WHERE r.salon_id = %s
            ORDER BY r.review_date DESC
            LIMIT 5
        """, (salon_id,))
        salon['recent_reviews'] = [dict(row) for row in cursor.fetchall()]
        
        return jsonify(convert_mysql_objects(salon)), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#favorite a salon
@user_dashboard_bp.route('/favorite_salon', methods=['POST'])
def favorite_salon():
    data = request.get_json()
    customer_id = data.get('customer_id')
    salon_id = data.get('salon_id')

    if not customer_id or not salon_id:
        return jsonify({'error': 'Missing customer_id or salon_id'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    try:
        #check if the salon is favorited 
        cursor.execute("""
            select 1 from saved_salons
            where customer_id = %s and salon_id = %s
        """, (customer_id, salon_id))
        if cursor.fetchone():
            return jsonify({'message': 'Salon already favorited'}), 200

        cursor.execute("""
            insert into saved_salons (customer_id, salon_id, saved_at)
            values (%s, %s, now())
        """, (customer_id, salon_id))
        mysql.connection.commit()

        return jsonify({'message': 'Salon favorited successfully'}), 201

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()

#unfavorite a salon
@user_dashboard_bp.route('/unfavorite_salon', methods=['POST'])
def unfavorite_salon():
    data = request.get_json()
    customer_id = data.get('customer_id')
    salon_id = data.get('salon_id')

    if not customer_id or not salon_id:
        return jsonify({'error': 'Missing customer_id or salon_id'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    try:
        cursor.execute("""
            delete from saved_salons
            where customer_id = %s and salon_id = %s
        """, (customer_id, salon_id))
        mysql.connection.commit()

        return jsonify({'message': 'Salon unfavorited successfully'}), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()

#display the list of favorited salons
@user_dashboard_bp.route('/favorited_salons', methods=['GET'])
def get_favorited_salons():
    customer_id = request.args.get('customer_id')

    if not customer_id:
        return jsonify({'error': 'Missing customer_id'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("""
            select s.salon_id, s.name, s.description, s.email, s.phone_number, 
                   s.is_verified, s.created_at,
                   a.address, a.city, a.state, a.postal_code,
                   group_concat(distinct mt.name) as master_tags,
                   group_concat(distinct t.name) as specific_tags,
                   avg(r.rating) as average_rating,
                   count(r.review_id) as review_count
            from saved_salons ss
            join salons s on ss.salon_id = s.salon_id
            left join addresses a on s.salon_id = a.salon_id and a.entity_type = 'salon'
            left join entity_master_tags emt on s.salon_id = emt.entity_id and emt.entity_type = 'salon'
            left join master_tags mt on emt.master_tag_id = mt.master_tag_id
            left join entity_tags et on s.salon_id = et.entity_id and et.entity_type = 'service'
            left join tags t on et.tag_id = t.tag_id
            left join reviews r on s.salon_id = r.salon_id
            where ss.customer_id = %s
            group by s.salon_id, s.name, s.description, s.email, s.phone_number, 
                     s.is_verified, s.created_at, a.address, a.city, a.state, a.postal_code
            order by s.is_verified desc, average_rating desc, s.name asc
        """, (customer_id,))
        
        salons = [dict(row) for row in cursor.fetchall()]
        
        for salon in salons:
            if salon['master_tags']:
                salon['master_tags'] = list(set(salon['master_tags'].split(',')))
            else:
                salon['master_tags'] = []
                
            if salon['specific_tags']:
                salon['specific_tags'] = list(set(salon['specific_tags'].split(',')))
            else:
                salon['specific_tags'] = []
        
        return jsonify(convert_mysql_objects({
            'favorited_salons': salons,
            'count': len(salons)
        })), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    