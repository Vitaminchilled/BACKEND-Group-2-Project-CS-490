from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

promotions_bp = Blueprint('promotions', __name__)

#view only active promotions
@promotions_bp.route('/salon/<int:salon_id>/promotions', methods=['GET'])
def get_promotions(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select promo_id, name, description, start_date, end_date, promo_code, 
            case
                when is_percentage = true then concat(cast(discount_value as unsigned), '%%')
                else concat('$', discount_value)
            end as discount_display
            from promotions
            where salon_id = %s and is_active = true
            order by start_date desc
        """
        cursor.execute(query, (salon_id,))
        promotions = cursor.fetchall()
        cursor.close()

        if not promotions:
            return jsonify({'message': 'No active promotions found'}), 404
        
        result = []
        for promotion in promotions:
            result.append({
                'promo_id': promotion[0],
                'name': promotion[1],
                'description': promotion[2],
                'start_date': promotion[3].strftime('%Y-%m-%d'),
                'end_date': promotion[4].strftime('%Y-%m-%d'),
                'promo_code': promotion[5],
                'discount_display': promotion[6]
            })
        return jsonify({'salon_id': salon_id, 'active_promotions': result}), 200
    except Exception as e:
        return jsonify({'error': f'Error fetching promotions: {str(e)}'}), 500

#view all promotions (inactive or not)
@promotions_bp.route('/salon/<int:salon_id>/promotions/all', methods=['GET'])
def get_all_promotions(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select promo_id, name, description, start_date, end_date, promo_code, 
            case
                when is_percentage = true then concat(cast(discount_value as unsigned), '%%')
                else concat('$', discount_value)
            end as discount_display
            from promotions
            where salon_id = %s
            order by created_at desc
        """
        cursor.execute(query, (salon_id,))
        promotions = cursor.fetchall()
        cursor.close()

        if not promotions:
            return jsonify({'message': 'No promotions found'}), 404

        result = []
        for promotion in promotions:
            result.append({
                'promo_id': promotion[0],
                'name': promotion[1],
                'description': promotion[2],
                'start_date': promotion[3].strftime('%Y-%m-%d'),
                'end_date': promotion[4].strftime('%Y-%m-%d'),
                'promo_code': promotion[5],
                'discount_display': promotion[6]
            })

        return jsonify({'salon_id': salon_id, 'promotions': result}), 200

    except Exception as e:
        return jsonify({'error': f'Error fetching all promotions: {str(e)}'}), 500

#create a new promotion
@promotions_bp.route('/salon/<int:salon_id>/promotions', methods=['POST'])
def create_promotion(salon_id):
    data = request.json
    name = data.get('name')
    description = data.get('description')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    promo_code = data.get('promo_code')
    discount_value = data.get('discount_value')
    is_percentage = data.get('is_percentage', True)

    if not all([name, start_date, end_date, promo_code, discount_value]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            insert into promotions(salon_id, name, description, start_date, end_date, promo_code, discount_value, is_percentage)
            values(%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, name, description, start_date, end_date, promo_code, discount_value, is_percentage))
        mysql.connection.commit()
        promo_id = cursor.lastrowid
        cursor.close()

        return jsonify({'message': 'Promotion created successfully', 'promo_id': promo_id}), 201
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': f'Error creating promotion: {str(e)}'}), 500
    
#edit a promotion
@promotions_bp.route('/promotions/<int:promo_id>', methods=['PUT'])
def edit_promotion(promo_id):
    data = request.json
    name = data.get('name')
    description = data.get('description')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    promo_code = data.get('promo_code')
    discount_value = data.get('discount_value')
    is_percentage = data.get('is_percentage', True)

    if not all([name, start_date, end_date, promo_code, discount_value]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """ 
            update promotions
            set name = %s, description = %s, start_date = %s, end_date = %s, promo_code = %s, discount_value = %s, is_percentage = %s, last_modified = now()
            where promo_id = %s
        """
        values = (name, description, start_date, end_date, promo_code, discount_value, is_percentage, promo_id)
        cursor.execute(query, values)
        mysql.connection.commit()

        if cursor.rowcount == 0:
            return jsonify({'error': 'Promotion not found'}), 404
        return jsonify({'message': 'Promotion updated successfully'}), 200
    except Exception as e:
        print("Error updating promotion:", e)
        return jsonify({'error': str(e)}), 500

#disable a promotion
@promotions_bp.route('/promotions/<int:promo_id>/disable', methods=['PUT'])
def disable_promotion(promo_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            update promotions
            set is_active = false, last_modified = current_timestamp
            where promo_id = %s
        """
        cursor.execute(query, (promo_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Promotion disabled successfully'}), 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': f'Error disabling promotion: {str(e)}'}), 500

@promotions_bp.route('/promotions/<int:promo_id>/enable', methods=['PUT'])
def enable_promotion(promo_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select is_active
            from promotions
            where promo_id = %s
        """
        cursor.execute(query, (promo_id,))
        promo = cursor.fetchone()
        if not promo:
            cursor.close()
            return jsonify({'error': 'Promotion not found'}), 404
        
        if promo[0]:
            cursor.close()
            return jsonify({'message': 'Promotion is already active'}), 200
        
        query = """
            update promotions
            set is_active = true, last_modified = now()
            where promo_id = %s
        """
        cursor.execute(query, (promo_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Promotion enabled successfully', 'promo_id': promo_id}), 200
    except Exception as e:
        return jsonify({'error': f'Error enabling promotion: {str(e)}'}), 500

#check if a promo code is valid and return its details (good for checkouts)
@promotions_bp.route('/promotions/check/<string:promo_code>', methods=['GET'])
def check_promo(promo_code):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select promo_id, salon_id, name, discount_value, is_percentage, start_date, end_date, is_active
            from promotions
            where promo_code = %s
        """
        cursor.execute(query, (promo_code,))
        promotion = cursor.fetchone()
        cursor.close()

        if not promotion:
            return jsonify({'valid': False, 'message': 'Promo code not found'}), 404
        
        curr_date = datetime.now().date()
        start_date, end_date = promotion[5], promotion[6] 
        is_active = bool(promotion[7])

        if not is_active or not (start_date <= curr_date <= end_date):
            return jsonify({'valid': False, 'message': 'This promotion is expired'}), 400
        
        return jsonify({
            'valid': True,
            'promo_id': promotion[0],
            'salon_id': promotion[1],
            'name': promotion[2],
            'discount_value': float(promotion[3]),
            'is_percentage': bool(promotion[4])
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Error checking promo: {str(e)}'}), 500