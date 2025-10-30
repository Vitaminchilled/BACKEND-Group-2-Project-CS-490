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
@loyalty_bp.route('/loyalty/<int:program_id>', methods=['PUT'])
def edit_loyalty(program_id):
    data = request.get_json()
    name = data.get('name')
    tag_name = data.get('tag_name')
    points_required = data.get('points_required')
    discount_value = data.get('discount_value')
    is_percentage = data.get('is_percentage')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    if not all([name, tag_name, points_required, discount_value, is_percentage, start_date, end_date]):
        return jsonify({"error": "Missing required fields"}), 400
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
            update loyalty_programs
            set name = %s, master_tag_id = %s, points_required = %s, discount_value = %s, is_percentage = %s, start_date = %s, end_date = %s
            where loyalty_program_id = %s
        """
        cursor.execute(query, (name, master_tag_id, points_required, discount_value, is_percentage, start_date, end_date))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Loyalty program updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Failed to update loyalty program"}), 500 

#salons can disable loyalty
@loyalty_bp.route('/loyalty/<int:program_id>/disable', methods=['PATCH'])
def disable_loyalty(program_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            update loyalty_programs
            set end_date = curdate()
            where loyalty_program_id = %s
        """
        cursor.execute(query, (program_id,))
        mysql.connection.commit()
        return jsonify({"message": "Loyalty program disabled"}), 200
    except Exception as e:
        return jsonify({"error": "Failed to disable loyalty program"}), 500 

#customer collects loyalty voucher
@loyalty_bp.route('/loyalty/<int:salon_id>/claim', methods=['POST'])
def claim_voucher(salon_id):
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        loyalty_program_id = data.get('loyalty_program_id')
        
        if not all([customer_id, loyalty_program_id]):
            return jsonify({"error": "Missing required fields"}), 400
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        #check customer's avaiable points
        query = """ 
            select available_points
            from customer_points
            where salon_id = %s and customer_id = %s
        """
        cursor.execute(query, (salon_id, customer_id))
        points = cursor.fetchone()
        if not points:
            return jsonify({"error": "Customer has no points for this salon"}), 404
        available_points = points[0]

        #check amount of points needed
        query = """
            select points_required
            from loyalty_programs
            where loyalty_program_id = %s
        """
        cursor.execute(query, (loyalty_program_id,))
        loyalty = cursor.fetchone()
        points_required = loyalty[0]

        if available_points < points_required:
            return jsonify({"error": "Not enough points"}), 400
        
        #when a customer has enough points
        query = """
            update customer_points
            set available_points = available_points - %s,
            points_redeemed = points_redeemed + %s
            where customer_id = %s and salon_id = %s
        """
        cursor.execute(query, (points_required, points_required, customer_id, salon_id))
        query = """
            insert into customer_vouchers(customer_id, salon_id, loyalty_program_id)
            values(%s, %s, %s)
        """
        cursor.execute(query, (customer_id, salon_id, loyalty_program_id))
        mysql.connection.commit()
        return jsonify({"message": "Voucher claimed successfully"}), 201
    except Exception as e:
        return jsonify({"error": "Voucher cannot be claimed at this time"}), 500

#customer tracks loyalty vouchers
@loyalty_bp.route('/loyalty/<int:customer_id>/vouchers', methods=['GET'])
def get_vouchers(customer_id):
    pass
