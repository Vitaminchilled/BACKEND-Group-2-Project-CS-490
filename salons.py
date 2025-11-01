#lizeth backend adjust later

from flask import Blueprint, request, jsonify, session
from flask import current_app

salons_bp = Blueprint('salons', __name__)

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

@salons_bp.route('/salon/all', methods=['GET'])
def get_salons():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        page = request.args.get('page', default=1, type=int)
        per_page = 7
        offset = (page - 1) * per_page

        business_name = request.args.get('business_name', default="", type=str)
        category = request.args.get('category', default="", type=str)
        employee_first = request.args.get('employee_first', default="", type=str)
        employee_last = request.args.get('employee_last', default="", type=str)
        filters = []
        params = []

        if business_name:
            filters.append("salons.name LIKE %s")
            params.append(f"%{business_name}%")
        
        if category:
            filters.append("master_tags.name LIKE %s")
            params.append(f"%{category}%")

        if employee_first or employee_last:
            employee_filter = "salons.salon_id IN (SELECT salon_id FROM employees WHERE "
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
            SELECT COUNT(*)
            FROM salons
            JOIN master_tags ON master_tags.master_tag_id = salons.master_tag_id
            LEFT JOIN salon_analytics ON salon_analytics.salon_id = salons.salon_id
            {where_clause}
        """
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        query = f"""
            select salons.salon_id, 
                    owner_id, salons.master_tag_id, 
                    salons.name as salon_name, 
                    master_tags.name as tag_name, 
                    description, 
                    email, 
                    phone_number, 

                    salon_analytics.average_rating as rating
            from salons
            join master_tags 
            on master_tags.master_tag_id = salons.master_tag_id
            left join salon_analytics 
            on salon_analytics.salon_id = salons.salon_id
            {where_clause}
            order by salons.salon_id
            limit %s offset %s
        """
        cursor.execute(query, (*params, per_page, offset))
        salons = cursor.fetchall()
        cursor.close()

        total_pages = -(-total // per_page)
        iter_pages = generate_iter_pages(current_page=page, total_pages=total_pages)

        return jsonify({
            'salons': [{
                "salon_id": salon[0],
                "owner_id": salon[1],
                "master_tag_id": salon[2],
                "salon_name": salon[3],
                "tag_name": salon[4],
                "description": salon[5],
                "email": salon[6],
                "phone_number": salon[7],
                "rating": salon[8]
            } for salon in salons],
            'page' : page,
            'total_retrieved' : len(salons),
            'total_pages' : total_pages,
            'iter_pages': iter_pages
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500
    
@salons_bp.route('/salon/<int:salon_id>/header', methods=['GET'])
def get_salon_info(salon_id):
    try: 
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        salon_query = """
            select salons.salon_id, 
                    salons.owner_id, 
                    salons.master_tag_id,
                    salons.name, 
                    description, 
                    email, 
                    phone_number, 

                    address, 
                    city, 
                    state, 
                    postal_code, 
                    country,
                    salon_analytics.average_rating
            from salons
            left join addresses
            on addresses.salon_id = salons.salon_id
            left join salon_analytics 
            on salon_analytics.salon_id = salons.salon_id
            where salons.salon_id=%s
        """
        cursor.execute(salon_query, (salon_id,))
        salon = cursor.fetchone()
        if not salon:
            return jsonify({"error": "Salon not found"}), 404
        
        cursor.execute("""select name from tags where master_tag_id=%s""", (salon[2],))
        tags = [tag[0] for tag in cursor.fetchall()]

        cursor.close()

        return jsonify({
            'salon': {
                "salon_id": salon[0],
                "owner_id": salon[1],
                "master_tag_id": salon[2],
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
            'tags' : tags, #tag list ex.["Salon Hair Cut","Blowout","Hair Wash","Hair Dye","Styling"]
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch salon', 'details': str(e)}), 500