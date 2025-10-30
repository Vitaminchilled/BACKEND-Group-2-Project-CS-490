from flask import Blueprint, request, jsonify, session
from flask import current_app

loyalty_bp = Blueprint('loyalty', __name__)

#customers/salons can view loyalty
@loyalty_bp.route('/loyalty/<int:salon_id>', methods=['GET'])
def get_loyalty(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select master_tags.name, loyalty_programs.name, loyalty_programs.points_required,
            case
                when loyalty_programs.is_percentage = true then concat(cast(loyalty_programs.discount_value as unsigned), '%%')
                else concat('$', loyalty_programs.discount_value)
            end as discount_display
            from loyalty_programs
            join master_tags on master_tags.master_tag_id = loyalty_programs.master_tag_id
            where (loyalty_programs.end_date is null or loyalty_programs.end_date >= curdate())
            and salon_id = %s;
        """
        cursor.execute(query, (salon_id,))
        loyalty = cursor.fetchall()
        return jsonify(loyalty), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch loyalty programs', 'details': str(e)}), 500

#salons can add loyalty
@loyalty_bp.route('/loyalty/<int:salon_id>', methods=['POST'])
def add_loyalty(salon_id):
    data = request.get_json()
    name = data.get('name')
    tag_name = request.json.get('tag_name')
    points_required = data.get('points_required')
    discount_value = data.get('discount_value')
    is_percentage = data.get('is_percentage')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not all([name, tag_name, points_required, discount_value, is_percentage, start_date, end_date]):
        return jsonify({"error": "Missing required fields"}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()
    query = """
        select master_tag_id
        from master_tags
        where name = %s
    """
    cursor.execute(query, (tag_name,))
    tag_info = cursor.fetchone()
    master_tag_id = tag_info[0]

    try:
        query = """
            insert into loyalty_programs
            (salon_id, master_tag_id, name, points_required, discount_value, is_percentage, start_date, end_date)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, master_tag_id, name, points_required, discount_value, is_percentage, start_date, end_date))
        mysql.connection.commit()
        return jsonify({"message": "Loyalty program added successfully"}), 201
    except Exception as e:
        return jsonify({"error": "Failed to add loyalty program"}), 500 

#salons can edit loyalty 
#salons can disable loyalty
#customer obtains loyalty voucher
#loyalty used at checkout
