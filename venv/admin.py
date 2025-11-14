from flask import Blueprint, request, jsonify, session
from flask import current_app

admin_bp = Blueprint('admin', __name__)


#Admin User Page - Retrieve all users (DONE)
@admin_bp.route('/admin/users', methods=['GET'])
def get_users():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select *
            from users
            where role != 'admin'
            order by role
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        cursor.close()
        data = [dict(zip(cols, row)) for row in rows]
        return jsonify({'users': data}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch users', 'details': str(e)}), 500
    

#Admin Salon page - Retrieve all salons that are verified (DONE)
@admin_bp.route('/admin/verifiedSalons', methods=['GET'])
def allSalons():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select 	s.salon_id,
                    s.name,
                    s.email,
                    s.phone_number,
                    s.created_at,
                    a.address,
                    a.city,
                    a.state,
                    a.postal_code,
                    a.country,
                    u.first_name as owner_first_name,
                    u.last_name as owner_last_name,
                    u.email as owner_email,
                    u.phone_number as owner_phone_number,
                    u.birth_year as owner_birth_year
            from salons s 
            join users u on u.user_id = s.owner_id
            join addresses a on a.salon_id = s.salon_id
            where   s.is_verified = true;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        cursor.close()
        data = [dict(zip(cols, row)) for row in rows]
        return jsonify({'salons': data}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500

#Admin Verify page - Retrieve all salons that need verification (DONE)
@admin_bp.route('/admin/salonsToVerify', methods=['GET'])
def salonsToVerify():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select 	s.salon_id,
                    s.name,
                    s.email,
                    s.phone_number,
                    s.created_at,
                    a.address,
                    a.city,
                    a.state,
                    a.postal_code,
                    a.country,
                    u.first_name as owner_first_name,
                    u.last_name as owner_last_name,
                    u.email as owner_email,
                    u.phone_number as owner_phone_number,
                    u.birth_year as owner_birth_year
            from salons s 
            join users u on u.user_id = s.owner_id
            join addresses a on a.salon_id = s.salon_id
            where   s.is_verified = false;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        cursor.close()
        data = [dict(zip(cols, row)) for row in rows]
        return jsonify({'salons': data}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500

#Admin Verify page - Handles verifying and rejecting salons (DONE)
@admin_bp.route('/admin/verifySalon', methods=['POST'])
def verifySalon():
    try:
        data = request.get_json()
        salon_id = data["salon_id"]
        is_verified = data["is_verified"]

        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = mysql.connection.cursor()
        if(is_verified):
            cursor.execute("""
                UPDATE salons
                SET is_verified = TRUE
                WHERE salon_id = %s
            """, (salon_id,))
        else:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cursor.execute("""
                DELETE FROM review_replies 
                WHERE review_id IN (SELECT review_id FROM reviews WHERE salon_id = %s)
            """, (salon_id,))
            cursor.execute("""
                DELETE FROM invoice_line_items 
                WHERE product_id IN (SELECT product_id FROM products WHERE salon_id = %s)
                OR service_id IN (SELECT service_id FROM services WHERE salon_id = %s)
            """, (salon_id, salon_id))
            cursor.execute("DELETE FROM reviews WHERE salon_id = %s", (salon_id,))
            cursor.execute("""
                DELETE FROM invoices 
                WHERE appointment_id IN (SELECT appointment_id FROM appointments WHERE salon_id = %s)
            """, (salon_id,))
            cursor.execute("""
                DELETE FROM cart_items 
                WHERE cart_id IN (SELECT cart_id FROM carts WHERE salon_id = %s)
            """, (salon_id,))
            cursor.execute("DELETE FROM customer_vouchers WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM appointments WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM carts WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM employee_schedules WHERE salon_id = %s", (salon_id,)) 
            cursor.execute("DELETE FROM employee_salaries WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM time_slots WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM salon_gallery WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM entity_master_tags WHERE entity_id = %s AND entity_type = 'salon'", (salon_id,))
            cursor.execute("DELETE FROM products WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM services WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM operating_hours WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM addresses WHERE salon_id = %s AND entity_type = 'salon'", (salon_id,))
            cursor.execute("DELETE FROM employees WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM loyalty_programs WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM promotions WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM customer_points WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM salon_analytics WHERE salon_id = %s", (salon_id,))
            cursor.execute("UPDATE user_history SET favorite_salon_id = NULL WHERE favorite_salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM salons WHERE salon_id = %s", (salon_id,))
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        conn.commit()
        cursor.close()
        return jsonify({
            "message": "Data received successfully",
            "salon_id": salon_id,
            "is_verified": is_verified
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to verify salon', 'details': str(e)}), 500


#Admin User page - Deletes specific user (WORKS)
@admin_bp.route('/admin/deleteUser', methods=['DELETE'])
def deleteUser():
    try:
        data = request.get_json()
        user_id = data["user_id"]

        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = mysql.connection.cursor()

        cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        role = user_data[0]

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

        if role == 'owner':
            #Get owners salon
            cursor.execute("SELECT salon_id FROM salons WHERE owner_id = %s", (user_id,))
            owned_salon = cursor.fetchone()

            if owned_salon:
                salon_id = owned_salon[0]
                cursor.execute("""
                    DELETE FROM review_replies 
                    WHERE review_id IN (SELECT review_id FROM reviews WHERE salon_id = %s)
                """, (salon_id,))
                cursor.execute("""
                    DELETE FROM invoice_line_items 
                    WHERE product_id IN (SELECT product_id FROM products WHERE salon_id = %s)
                    OR service_id IN (SELECT service_id FROM services WHERE salon_id = %s)
                """, (salon_id, salon_id))
                cursor.execute("DELETE FROM reviews WHERE salon_id = %s", (salon_id,))
                cursor.execute("""
                    DELETE FROM invoices 
                    WHERE appointment_id IN (SELECT appointment_id FROM appointments WHERE salon_id = %s)
                """, (salon_id,))
                cursor.execute("""
                    DELETE FROM cart_items 
                    WHERE cart_id IN (SELECT cart_id FROM carts WHERE salon_id = %s)
                """, (salon_id,))
                cursor.execute("DELETE FROM customer_vouchers WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM appointments WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM carts WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM employee_schedules WHERE salon_id = %s", (salon_id,)) 
                cursor.execute("DELETE FROM employee_salaries WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM time_slots WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM salon_gallery WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM entity_master_tags WHERE entity_id = %s AND entity_type = 'salon'", (salon_id,))
                cursor.execute("DELETE FROM products WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM services WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM operating_hours WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM addresses WHERE salon_id = %s AND entity_type = 'salon'", (salon_id,))
                cursor.execute("DELETE FROM employees WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM loyalty_programs WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM promotions WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM customer_points WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM salon_analytics WHERE salon_id = %s", (salon_id,))
                cursor.execute("UPDATE user_history SET favorite_salon_id = NULL WHERE favorite_salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM salons WHERE salon_id = %s", (salon_id,))

        cursor.execute("DELETE FROM reviews WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM review_replies WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM invoice_line_items WHERE invoice_id IN (SELECT invoice_id FROM invoices WHERE customer_id = %s)", (user_id,))
        cursor.execute("DELETE FROM invoices WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM wallets WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM carts WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM customer_vouchers WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM customer_points WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM user_history WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM appointments WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM addresses WHERE customer_id = %s AND entity_type = 'customer'", (user_id,))
        cursor.execute("UPDATE audit_logs SET changed_by = NULL WHERE changed_by = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
        cursor.close()
        return jsonify({
            "message": "User Deleted"
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to delete user', 'details': str(e)}), 500
