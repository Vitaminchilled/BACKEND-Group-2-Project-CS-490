from flask import Blueprint, request, jsonify, session
from flask import current_app
import re
from utils.logerror import log_error

users_bp = Blueprint('users', __name__)


#User details page
@users_bp.route('/userDetails', methods=['POST'])
def userDetails():
    try:
        data = request.get_json()
        user_id = data["user_id"]

        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = mysql.connection.cursor()
        cursor.execute("""
            select *
            from users
            where user_id = %s
        """, (user_id,))

        result = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        user_data = dict(zip(columns, result))
        cursor.close() 
        return jsonify(user_data), 200
    
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Failed to fetch user details', 'details': str(e)}), 500
    
#User details page - Update and Validation
@users_bp.route('/updateUserDetails', methods=['POST'])
def updateUserDetails():
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        print("\n\n DATA received:")
        print(data)
        print("\n\n")

        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        updates = {k: v for k, v in data.items() if k != 'user_id'}

        if not updates:
            return jsonify({"message": "No fields provided for update"}), 400

        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        current = cursor.fetchone()
        if not current:
            cursor.close()
            return jsonify({"error": "User not found"}), 404

        columns = [desc[0] for desc in cursor.description]
        current_user = dict(zip(columns, current))

        def valid_email(email):
            return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email)

        field_errors = {}
        fields_to_update = {}

        if "full_name" in updates:
            name = (updates["full_name"] or "").strip()
            parts = name.split()

            if len(parts) != 2:
                field_errors.setdefault("full_name", []).append("Name must include exactly first and last name (two words).")
            else:
                first, last = parts
                if first != (current_user.get("first_name") or ""):
                    fields_to_update["first_name"] = first
                if last != (current_user.get("last_name") or ""):
                    fields_to_update["last_name"] = last

        if "username" in updates:
            username = (updates["username"] or "").strip()
            if username == "":
                field_errors.setdefault("username", []).append("Username cannot be empty.")
            else:
                if username != (current_user.get("username") or ""):
                    if len(username) < 3:
                        field_errors.setdefault("username", []).append("Username must be at least 3 characters.")
                    else:
                        cursor.execute(
                            "SELECT user_id FROM users WHERE username = %s AND user_id != %s",
                            (username, user_id)
                        )
                        if cursor.fetchone():
                            field_errors.setdefault("username", []).append("Username already taken.")
                        else:
                            if "username" not in field_errors:
                                fields_to_update["username"] = username

        if "email" in updates:
            email = (updates["email"] or "").strip()
            if email == "":
                field_errors.setdefault("email", []).append("Email cannot be empty.")
            else:
                if email != (current_user.get("email") or ""):
                    if not valid_email(email):
                        field_errors.setdefault("email", []).append("Email format is invalid.")
                    else:
                        cursor.execute(
                            "SELECT user_id FROM users WHERE email = %s AND user_id != %s",
                            (email, user_id)
                        )
                        if cursor.fetchone():
                            field_errors.setdefault("email", []).append("Email is already in use.")
                        else:
                            if "email" not in field_errors:
                                fields_to_update["email"] = email

        if "phone_number" in updates:
            phone = (updates["phone_number"] or "").strip()
            if phone != (current_user.get("phone_number") or ""):
                if phone:
                    if not phone.isdigit():
                        field_errors.setdefault("phone_number", []).append("Phone number must contain only digits.")
                    if len(phone) != 10:
                        field_errors.setdefault("phone_number", []).append("Phone number must contain 10 digits.")
                    if "phone_number" not in field_errors:
                        fields_to_update["phone_number"] = phone
                else:
                    fields_to_update["phone_number"] = ""

        #return any errors
        if field_errors:
            cursor.close()
            return jsonify({
                "error": "Validation failed",
                "message": "One or more fields contain errors. Fix them and try again.",
                "field_errors": field_errors
            }), 400

        if not fields_to_update:
            cursor.close()
            return jsonify({"message": "No changes detected"}), 200

        set_clause = ", ".join([f"{key} = %s" for key in fields_to_update.keys()])
        values = list(fields_to_update.values())
        values.append(user_id)

        query = f"UPDATE users SET {set_clause} WHERE user_id = %s"
        cursor.execute(query, tuple(values))
        conn.commit()
        cursor.close()

        return jsonify({"message": "User details updated successfully"}), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        if 'cursor' in locals() and cursor:
            cursor.close()
        return jsonify({"error": "Failed to update user details", "details": str(e)}), 500
