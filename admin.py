from flask import Blueprint, request, jsonify, session
from flask import current_app
from utils.emails import send_email
from utils.logerror import log_error

admin_bp = Blueprint('admin', __name__)


#Admin User Page - Retrieve all users (DONE)
@admin_bp.route('/admin/users', methods=['GET'])
def get_users():
    """
    Admin Page user retrival
    ---
    tags:
      - Admin Page
    responses:
      200:
        description: Success
      500:
        description: Failed to fetch users
    """
    try:
        #make sure admin is logged in
        session_user_role = session.get("role")
        if session_user_role != 'admin':
            log_error("Unauthorized access attempt to fetch users", session.get("user_id"))
            return jsonify({'error': 'Unauthorized access'}), 403
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select *
            from users
            where role != 'admin'
            order by 'role'
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        cursor.close()
        data = [dict(zip(cols, row)) for row in rows]
        return jsonify({'users': data}), 200
    except Exception as e:
        #save error to audit logs
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to fetch users', 'details': str(e)}), 500

#Admin Salon page - Retrieve all salons that are verified (DONE)
@admin_bp.route('/admin/verifiedSalons', methods=['GET'])
def allSalons():
    """
    Admin Page salon retrival
    ---
    tags:
      - Admin Page
    responses:
      200:
        description: Success
      500:
        description: Failed to fetch salons
    """
    try:
        #make sure admin is logged in
        session_user_role = session.get("role")
        if session_user_role != 'admin':
            log_error("Unauthorized access attempt to fetch salons", session.get("user_id"))
            return jsonify({'error': 'Unauthorized access'}), 403
        
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
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500

#Admin Verify page - Retrieve all salons that need verification (DONE)
@admin_bp.route('/admin/salonsToVerify', methods=['GET'])
def salonsToVerify():
    """
    Admin Page unverified salon retrival
    ---
    tags:
      - Admin Page
    responses:
      200:
        description: salons
      500:
        description: Failed to fetch salons
    """
    try:
        #make sure admin is logged in
        session_user_role = session.get("role")
        if session_user_role != 'admin':
            log_error("Unauthorized access attempt to fetch unverified salons", session.get("user_id"))
            return jsonify({'error': 'Unauthorized access'}), 403
        
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
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to fetch salons', 'details': str(e)}), 500

#Admin Verify page - Handles verifying and rejecting salons (DONE)
@admin_bp.route('/admin/verifySalon', methods=['POST'])
def verifySalon():
    """
    Admin verify page
    ---
    tags:
      - Admin Page
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            salon_id:
              type: integer
            is_verified:
              type: boolean
    responses:
      200:
        description: Data received successfully
      500:
        description: Failed to verify salon
    """
    try:
        #make sure admin is logged in
        session_user_role = session.get("role")
        if session_user_role != 'admin':
            log_error("Unauthorized access attempt to verify salon", session.get("user_id"))
            return jsonify({'error': 'Unauthorized access'}), 403
        
        data = request.get_json()
        salon_id = data["salon_id"]
        is_verified = data["is_verified"]

        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = mysql.connection.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        #get salon owner info
        '''cursor.execute("""
                select owner_id, email, name
                from salons 
                where salon_id = %s
            """, (salon_id,))
        owner_id, salon_email, salon_name = cursor.fetchone() '''

        cursor.execute("""
            select owner_id, email, name
            from salons 
            where salon_id = %s
        """, (salon_id,))
            
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return jsonify({"error": "Salon not found"}), 404
        owner_id, salon_email, salon_name = row

        if(is_verified):
            cursor.execute("""
                UPDATE salons
                SET is_verified = TRUE
                WHERE salon_id = %s
            """, (salon_id,))
        
        #notify the owner via email
        '''    try:
                send_email(
                    to=salon_email,
                    subject="Salon Application Approved",
                    body=f"Dear {salon_name},\n\nCongratulations! Your salon application has been approved. You can now start offering your services on our platform.\n\nBest regards,\nSalon Management Team"
                )
            except Exception as e:
                log_error(str(e), session.get("user_id"))
                print(f"Failed to send approval email: {e}")
        else:
            reason = data.get("reason", "No reason provided")
            #log the reason for rejection
            cursor.execute("""
                insert into salon_rejections(salon_id, admin_id, reason)
                values (%s, %s, %s)
            """, (salon_id, session.get("user_id"), reason))'''

            #notify the owner via email   
            
            cursor.execute("""
                insert into notifications(user_id, title, message)
                values (%s, %s, %s)
            """, (owner_id, "Salon Application Rejected", f"Dear {salon_name}, your salon application has been rejected for the following reason: {reason}"))

            '''try:
                send_email(
                    to=salon_email,
                    subject="Salon Application Rejected",
                    body=f"Dear {salon_name},\n\nWe regret to inform you that your salon application has been rejected for the following reason:\n\n{reason}\n\nIf you have any questions, please contact our support team.\n\nBest regards,\nSalon Management Team"
                )
            except Exception as e:
                log_error(str(e), session.get("user_id"))
                print(f"Failed to send rejection email: {e}")'''

            #delete the salon's data from all related tables
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
            cursor.execute("DELETE FROM carts WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM appointments WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM carts WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM employee_salaries WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM salon_gallery WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM employees WHERE salon_id = %s", (salon_id,))
            cursor.execute("DELETE FROM addresses WHERE salon_id = %s AND entity_type = 'salon'", (salon_id,))
            cursor.execute("DELETE FROM salons WHERE salon_id = %s", (salon_id,))
            #cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

        conn.commit()
        cursor.close()
        return jsonify({
            "message": "Data received successfully",
            "salon_id": salon_id,
            "is_verified": is_verified
        }), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to verify salon', 'details': str(e)}), 500

#Admin User page - Deletes specific user (WORKS)
@admin_bp.route('/admin/deleteUser', methods=['DELETE'])
def deleteUser():
    """
    Delete a user
    ---
    tags:
      - Admin Page
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: ID of the user to delete
    responses:
      200:
        description: User Deleted
      500:
        description: Failed to delete user
    """
    try:
        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = mysql.connection.cursor()

        #make sure admin is logged in
        session_user_role = session.get("role")
        if session_user_role != 'admin':
            log_error("Unauthorized access attempt to delete user", session.get("user_id"))
            return jsonify({'error': 'Unauthorized access'}), 403
        
        data = request.get_json()
        user_id = data["user_id"]


        cursor.execute("SELECT role, email, first_name FROM users WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        role = user_data[0]
        user_email = user_data[1]
        user_name = user_data[2]

        #notify why the account was deleted
        '''try:
            send_email(
                to=user_email,
                subject="Account Deletion Notice",
                body=f"Dear {user_name},\n\nWe would like to inform you that your account has been deleted by the administration team. If you have any questions or believe this was done in error, please contact our support team.\n\nBest regards,\nSalon Management Team"
            )
        except Exception as e:
            log_error(str(e), session.get("user_id"))
            print(f"Failed to send account deletion email: {e}")'''

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        if role == 'owner':
            #Get owners salon
            cursor.execute("SELECT salon_id FROM salons WHERE owner_id = %s", (user_id,))
            owned_salon = cursor.fetchone()

            if owned_salon:
                salon_id = owned_salon[0]
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                cursor.execute("DELETE FROM salon_analytics WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM promotions WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM loyalty_programs WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM products WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM services WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM customer_points WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM customer_vouchers WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM carts WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM appointments WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM time_slots WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM employee_salaries WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM salon_gallery WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM employees WHERE salon_id = %s", (salon_id,))
                cursor.execute("DELETE FROM addresses WHERE salon_id = %s AND entity_type = 'salon'", (salon_id,))
                cursor.execute("DELETE FROM salons WHERE salon_id = %s", (salon_id,))
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        
        cursor.execute("DELETE FROM reviews WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM review_replies WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM user_history WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM customer_points WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM customer_vouchers WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM carts WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM invoice_line_items WHERE invoice_id IN (SELECT invoice_id FROM invoices WHERE customer_id = %s)", (user_id,))
        cursor.execute("DELETE FROM invoices WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM wallets WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM appointments WHERE customer_id = %s", (user_id,))
        cursor.execute("DELETE FROM addresses WHERE customer_id = %s AND entity_type = 'customer'", (user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        conn.commit()
        cursor.close()
        return jsonify({
            "message": "User Deleted"
        }), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        conn.rollback()
        return jsonify({'error': 'Failed to delete user', 'details': str(e)}), 500
