from flask import Blueprint, request, jsonify, session
from flask import current_app
import json
from utils.emails import send_email
from flask_mail import Message
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
from datetime import datetime, timedelta
from utils.logerror import log_error

salon_bp = Blueprint('salon', __name__)

#Can be used on Landing to salon names and their rating
@salon_bp.route('/salonData', methods=['GET'])
def salonData():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select s.name, s.salon_id, avg(r.rating) as average_rating
            from salons s
            join reviews r on r.salon_id = s.salon_id
            group by s.name, s.salon_id
            limit 6;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        data = [dict(zip(columns, row)) for row in rows]
        return jsonify({'salons': data}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500

    
def generate_iter_pages(current_page, total_pages, left_edge=2, right_edge=2, left_current=2, right_current=2):
    last = 0
    pages = []
    for num in range(1, total_pages + 1):
        if (
            num <= left_edge or
            (current_page - left_current - 1 < num < current_page + right_current) or
            num > total_pages - right_edge
        ):
            if last + 1 != num:
                pages.append('...')  # gap
            pages.append(num)
            last = num
    return pages

@salon_bp.route('/salon/all', methods=['GET'])
def get_salons():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        page = request.args.get('page', default=1, type=int)
        per_page = 7
        offset = (page - 1) * per_page

        business_name = request.args.get('business_name', default="", type=str)
        categories = request.args.getlist("categories")
        employee_first = request.args.get('employee_first', default="", type=str)
        employee_last = request.args.get('employee_last', default="", type=str)

        filters = ["s.is_verified = 1"]
        params = []

        if business_name:
            filters.append("s.name LIKE %s")
            params.append(f"%{business_name}%")
        
        if categories:
            placeholders = ', '.join(['%s'] * len(categories))

            category_filter = f"""
                s.salon_id IN (
                    SELECT e.entity_id 
                    FROM entity_master_tags e 
                    LEFT JOIN master_tags m
                    ON m.master_tag_id = e.master_tag_id
                    WHERE e.entity_type = 'salon' AND 
                    m.name in ({placeholders})
                    GROUP BY e.entity_id
                    HAVING COUNT(DISTINCT m.name) >= %s
                )
            """
            
            filters.append(category_filter)
            params.extend(categories)
            params.append(len(categories))

        if employee_first or employee_last:
            employee_filter = "s.salon_id IN (SELECT salon_id FROM employees WHERE "
            subconditions = []
            subparams = []

            if employee_first:
                subconditions.append("first_name LIKE %s")
                subparams.append(f"%{employee_first}%")
            if employee_last:
                subconditions.append("last_name LIKE %s")
                subparams.append(f"%{employee_last}%")

            employee_filter += " AND ".join(subconditions) + ")"
            filters.append(employee_filter)
            params.extend(subparams)

        where_clause = "WHERE " + " AND ".join(filters) if filters else ""

        count_query = f"""
            SELECT COUNT(DISTINCT s.salon_id)
            from salons s
            left join entity_master_tags e
                on e.entity_id = s.salon_id and e.entity_type = 'salon'
            left join master_tags m 
                on m.master_tag_id = e.master_tag_id
            left join salon_analytics sa
                on sa.salon_id = s.salon_id
            {where_clause}
        """
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        query = f"""
            select s.salon_id, 
                    s.owner_id,
                    s.name as salon_name,
                    COALESCE(
                        JSON_ARRAYAGG(m.name), 
                        JSON_ARRAY()
                    ) as tag_names,
                    s.description, 
                    s.email, 
                    s.phone_number,
                    sa.average_rating
            from salons s
            left join entity_master_tags e
                on e.entity_id = s.salon_id and e.entity_type = 'salon'
            left join master_tags m 
                on m.master_tag_id = e.master_tag_id
            left join salon_analytics sa
                on sa.salon_id = s.salon_id
            {where_clause}
            group by s.salon_id
            order by s.salon_id
            limit %s offset %s
        """
        cursor.execute(query, (*params, per_page, offset))
        salons = cursor.fetchall()
        cursor.close()

        total_pages = -(-total // per_page)
        iter_pages = generate_iter_pages(current_page=page, total_pages=total_pages)

        result = []
        for salon in salons:
            try:
                tags = json.loads(salon[3]) if salon[3] else []
            except Exception:
                tags = []

            result.append({
                "salon_id": salon[0],
                "owner_id": salon[1],
                "salon_name": salon[2],
                "tag_names": tags,
                "description": salon[4],
                "email": salon[5],
                "phone_number": salon[6],
                "average_rating": salon[7]
            })

        return jsonify({
            'salons': result,
            'page' : page,
            'total_retrieved' : len(salons),
            'total_pages' : total_pages,
            'iter_pages': iter_pages
        }), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500
    
@salon_bp.route('/salon/<int:salon_id>/header', methods=['GET'])
def get_salon_info(salon_id):
    try: 
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        salon_query = """
            select 
                s.salon_id, 
                s.owner_id, 
                (
                    select COALESCE(
                        JSON_ARRAYAGG(
                            JSON_OBJECT(
                                'tag_id', t.tag_id,
                                'name', t.name
                            )
                        ), JSON_ARRAY()
                    )
                    from entity_master_tags e
                    left join master_tags m 
                    on m.master_tag_id = e.master_tag_id
                    left join tags t
                    on t.master_tag_id = m.master_tag_id
                    where e.entity_id = s.salon_id and e.entity_type = 'salon'
                ) as tag_names,
                s.name, 
                s.description, 
                s.email, 
                s.phone_number, 
                ad.address, 
                ad.city, 
                ad.state, 
                ad.postal_code, 
                ad.country,
                sa.average_rating,
                (
                    select COALESCE(
                        JSON_ARRAYAGG(
                            JSON_OBJECT(
                                'master_tag_id', m.master_tag_id,
                                'name', m.name
                            )
                        ), JSON_ARRAY()
                    )
                    from entity_master_tags e
                    left join master_tags m 
                    on m.master_tag_id = e.master_tag_id
                    where e.entity_id = s.salon_id and e.entity_type = 'salon'
                ) as master_tags
            from salons s
            left join addresses ad
            on ad.salon_id = s.salon_id
            left join salon_analytics sa
            on sa.salon_id = s.salon_id
            where s.salon_id=%s
        """
        cursor.execute(salon_query, (salon_id,))
        salon = cursor.fetchone()
        if not salon:
            return jsonify({"error": "Salon not found"}), 404
        
        tag_list = []
        try:
            tag_list = json.loads(salon[2]) if salon[2] else []
        except Exception:
            tag_list = []

        master_tag_list = []
        try:
            master_tag_list = json.loads(salon[13]) if salon[13] else []
        except Exception:
            master_tag_list = []

        cursor.close()

        return jsonify({
            'salon': {
                "salon_id": salon[0],
                "owner_id": salon[1],
                "salon_name": salon[3],
                "description": salon[4],
                "email": salon[5],
                "phone_number": salon[6],
                "address": salon[7],
                "city": salon[8],
                "state": salon[9],
                "postal_code": salon[10],
                "country": salon[11],
                "average_rating": salon[12]
            },
            'tags' : tag_list,
            'master_tags' : master_tag_list
        }), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to fetch salon', 'details': str(e)}), 500
    
#send promotional emails to all customers of the salon who favorited the salon or had an appointment there
@salon_bp.route('/salon/<int:salon_id>/promotions/email', methods=['POST'])
def send_promotional_email(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        data = request.get_json()
        promotional_message = data.get('message', '')
        if not promotional_message:
            return jsonify({'error': 'Promotional message is required'}), 400

        query = """
            select distinct users.email
            from users
            join saved_salons on users.user_id = saved_salons.customer_id
            left join appointments on users.user_id = appointments.customer_id
            where (saved_salons.salon_id = 1 or appointments.salon_id = 1)
        """
        cursor.execute(query, (salon_id, salon_id))
        customers = cursor.fetchall()
        cursor.close()

        if not customers:
            return jsonify({'message': 'No customers found for promotional email'}), 200

        subject = "Exclusive Promotion from Your Favorite Salon!"
        for customer in customers:
            customer_email = customer[0]
            body = f"Dear Customer,\n\n{promotional_message}\n\nBest regards,\nYour Favorite Salon"
            send_email(to_address=customer_email, subject=subject, body=body)
        return jsonify({'message': 'Promotional emails sent successfully'}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to send promotional emails', 'details': str(e)}), 500