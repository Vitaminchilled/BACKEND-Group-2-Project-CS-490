from flask import Blueprint, request, jsonify, session
from flask import current_app

loyalty_bp = Blueprint('loyalty', __name__)

#customers/salons can view active loyalty
@loyalty_bp.route('/loyalty/<int:salon_id>', methods=['GET'])
def get_active_loyalty(salon_id):
    """
    Get active loyalty programs for a salon
    ---
    tags:
      - Loyalty
    parameters:
      - name: salon_id
        in: path
        type: integer
        required: true
        description: Salon ID
    responses:
      200:
        description: List of active loyalty programs
      500:
        description: Failed to fetch loyalty programs
    """
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select loyalty_programs.name, loyalty_programs.points_required, group_concat(tags.name order by tags.name separator ', ') as tags,
            case
                when loyalty_programs.is_percentage = true then concat(cast(loyalty_programs.discount_value as unsigned), '%%')
                else concat('$', loyalty_programs.discount_value)
            end
            from loyalty_programs
            join entity_tags on entity_tags.entity_type = 'loyalty' and entity_tags.entity_id = loyalty_programs.loyalty_program_id
            join tags on tags.tag_id = entity_tags.tag_id
            where (loyalty_programs.end_date is null or loyalty_programs.end_date > curdate())
            and loyalty_programs.salon_id = %s
            group by loyalty_programs.loyalty_program_id;
        """
        cursor.execute(query, (salon_id,))
        loyalty = cursor.fetchall()
        return jsonify(loyalty), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch loyalty programs', 'details': str(e)}), 500

#salons can view active and inactive loyalty programs
@loyalty_bp.route('/loyalty/viewall/<int:salon_id>', methods=['GET'])
def get_loyalty(salon_id):
    """
    Get all loyalty programs for a salon (active and inactive)
    ---
    tags:
      - Loyalty
    parameters:
      - name: salon_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Loyalty programs returned successfully
      500:
        description: Failed to fetch loyalty programs
    """
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select loyalty_programs.name, loyalty_programs.points_required, group_concat(tags.name order by tags.name separator ', ') as tags,
            case
                when loyalty_programs.is_percentage = true then concat(cast(loyalty_programs.discount_value as unsigned), '%%')
                else concat('$', loyalty_programs.discount_value)
            end as discount_display
            from loyalty_programs
            join entity_tags on entity_tags.entity_type = 'loyalty' and entity_tags.entity_id = loyalty_programs.loyalty_program_id
            join tags on tags.tag_id = entity_tags.tag_id
            where loyalty_programs.salon_id = %s
            group by loyalty_programs.loyalty_program_id;
        """
        cursor.execute(query, (salon_id,))
        loyalty = cursor.fetchall()
        return jsonify(loyalty), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch loyalty programs', 'details': str(e)}), 500

#salons can add loyalty
@loyalty_bp.route('/loyalty/<int:salon_id>', methods=['POST'])
def add_loyalty(salon_id):
    """
    Add a new loyalty program
    ---
    tags:
      - Loyalty
    consumes:
      - application/json
    parameters:
      - name: salon_id
        in: path
        type: integer
        required: true
      - in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            tag_names:
              type: array
              items:
                type: string
            points_required:
              type: integer
            discount_value:
              type: number
            is_percentage:
              type: boolean
            start_date:
              type: string
              description: YYYY-MM-DD
            end_date:
              type: string
              description: YYYY-MM-DD
    responses:
      201:
        description: Loyalty program added successfully
      400:
        description: Missing required fields or tag list invalid
      500:
        description: Failed to add loyalty program
    """
    data = request.get_json()
    name = data.get('name')
    tag_names = data.get('tag_names')  
    points_required = data.get('points_required')
    discount_value = data.get('discount_value')
    is_percentage = data.get('is_percentage')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not all([name, tag_names, points_required, discount_value, start_date, end_date]) or is_percentage is None:
        return jsonify({"error": "Missing required fields"}), 400
    
    if not isinstance(tag_names, list):
        return jsonify({"error": "tag_names must be a list"}), 400
   
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            insert into loyalty_programs
            (salon_id, name, points_required, discount_value, is_percentage, start_date, end_date)
            values (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, name, points_required, discount_value, is_percentage, start_date, end_date))
        loyalty_program_id = cursor.lastrowid

        for name in tag_names:
            cursor.execute("select tag_id from tags where name = %s", (name,))
            tag = cursor.fetchone()
            if tag:
                tag_id = tag[0]
                cursor.execute("insert into entity_tags (entity_type, entity_id, tag_id) values (%s, %s, %s)", ('loyalty', loyalty_program_id, tag_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Loyalty program added successfully"}), 201
    except Exception as e:
        return jsonify({"error": "Failed to add loyalty program"}), 500 

#salons can edit loyalty
@loyalty_bp.route('/loyalty/<int:loyalty_program_id>', methods=['PUT'])
def edit_loyalty(loyalty_program_id):
    """
    Edit an existing loyalty program
    ---
    tags:
      - Loyalty
    consumes:
      - application/json
    parameters:
      - name: loyalty_program_id
        in: path
        required: true
        type: integer
      - in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            tag_names:
              type: array
              items:
                type: string
            points_required:
              type: integer
            discount_value:
              type: number
            is_percentage:
              type: boolean
            start_date:
              type: string
            end_date:
              type: string
    responses:
      200:
        description: Loyalty program updated successfully
      400:
        description: Missing required fields or invalid tag list
      500:
        description: Failed to update loyalty program
    """
    data = request.get_json()
    name = data.get('name')
    tag_names = data.get('tag_names')
    points_required = data.get('points_required')
    discount_value = data.get('discount_value')
    is_percentage = data.get('is_percentage')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not all([name, tag_names, points_required, discount_value, start_date, end_date]) or is_percentage is None:
        return jsonify({"error": "Missing required fields"}), 400
    
    if not isinstance(tag_names, list):
        return jsonify({"error": "tag_names must be a list"}), 400
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            update loyalty_programs
            set name = %s, points_required = %s, discount_value = %s, is_percentage = %s, start_date = %s, end_date = %s
            where loyalty_program_id = %s
        """
        cursor.execute(query, (name, points_required, discount_value, is_percentage, start_date, end_date, loyalty_program_id))

        #clear old tag names
        cursor.execute("delete from entity_tags where entity_type = 'loyalty' and entity_id = %s", (loyalty_program_id,))
        for name in tag_names:
            cursor.execute("select tag_id from tags where name = %s", (name,))
            tag = cursor.fetchone()
            if tag:
                tag_id = tag[0]
                cursor.execute("insert into entity_tags (entity_type, entity_id, tag_id) values (%s, %s, %s)", ('loyalty', loyalty_program_id, tag_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "Loyalty program updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Failed to update loyalty program"}), 500 

#salons can disable loyalty
@loyalty_bp.route('/loyalty/<int:loyalty_program_id>/disable', methods=['PATCH'])
def disable_loyalty(loyalty_program_id):
    """
    Disable a loyalty program immediately
    ---
    tags:
      - Loyalty
    parameters:
      - name: loyalty_program_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Loyalty program disabled
      500:
        description: Failed to disable loyalty program
    """
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            update loyalty_programs
            set end_date = curdate()
            where loyalty_program_id = %s
        """
        cursor.execute(query, (loyalty_program_id,))
        mysql.connection.commit()
        return jsonify({"message": "Loyalty program disabled"}), 200
    except Exception as e:
        return jsonify({"error": "Failed to disable loyalty program"}), 500 

#salons can enable loyalty
@loyalty_bp.route('/loyalty/viewall/<int:loyalty_program_id>/enable', methods=['PATCH'])
def enable_loyalty(loyalty_program_id):
    """
    Re-enable a previously disabled loyalty program
    ---
    tags:
      - Loyalty
    parameters:
      - name: loyalty_program_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Loyalty program enabled
      500:
        description: Failed to enable loyalty program
    """
    try: 
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            update loyalty_programs
            set end_date = null
            where loyalty_program_id = %s
        """
        cursor.execute(query, (loyalty_program_id,))
        mysql.connection.commit()
        return jsonify({"message": "Loyalty program enabled"}), 200
    except Exception as e:
        return jsonify({"error": "Failed to enable loyalty program"}), 500

#display customer loyalty points
@loyalty_bp.route('/loyalty/<int:salon_id>/points/<int:customer_id>', methods=['GET'])
def get_customer_points(salon_id, customer_id):
    """
    Get loyalty points for a specific customer at a salon
    ---
    tags:
      - Loyalty
    parameters:
      - name: salon_id
        in: path
        type: integer
        required: true
      - name: customer_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Loyalty points returned
      404:
        description: No points found for this customer
      500:
        description: Error retrieving customer points
    """
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select points_earned, points_redeemed, available_points
            from customer_points
            where salon_id = %s and customer_id = %s
        """
        cursor.execute(query, (salon_id, customer_id))
        points = cursor.fetchone()

        if not points:
            return jsonify({"error": "No points found for this customer at this salon"}), 404
        
        result = {
            "points_earned": points[0],
            "points_redeemed": points[1],
            "available_points": points[2]
        }

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch customer points", "details": str(e)}), 500
    
#customer collects loyalty voucher
@loyalty_bp.route('/loyalty/<int:salon_id>/claim', methods=['POST'])
def claim_voucher(salon_id):
    """
    Redeem points for a loyalty voucher
    ---
    tags:
      - Loyalty
    consumes:
      - application/json
    parameters:
      - name: salon_id
        in: path
        required: true
        type: integer
      - in: body
        required: true
        schema:
          type: object
          properties:
            customer_id:
              type: integer
            loyalty_program_id:
              type: integer
    responses:
      201:
        description: Voucher claimed successfully
      400:
        description: Missing fields or insufficient points
      404:
        description: Customer has no points record
      500:
        description: Voucher claim failed
    """
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
    """
    Get all unredeemed loyalty vouchers for a customer
    ---
    tags:
      - Loyalty
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: List of vouchers returned
      500:
        description: Failed to retrieve vouchers
    """
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select salons.name, loyalty_programs.name,
            case
                when loyalty_programs.is_percentage = true then concat(cast(loyalty_programs.discount_value as unsigned), '%%')
                else concat('$', loyalty_programs.discount_value)
            end as discount_display
            from customer_vouchers
            join salons on customer_vouchers.salon_id = salons.salon_id
            join loyalty_programs on customer_vouchers.loyalty_program_id = loyalty_programs.loyalty_program_id
            where customer_vouchers.redeemed = 0 and customer_id = %s;
        """
        cursor.execute(query, (customer_id,))
        vouchers = cursor.fetchall()
        return jsonify(vouchers), 200
    except Exception as e:
        return jsonify({"error": "No vouchers availables"}), 500
