import traceback
from flask import request, current_app

def log_error(error_message, user_id=None):
    try:
        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = conn.cursor()

        endpoint = request.path if request else None
        method = request.method if request else None
        payload = request.get_json(silent=True) if request else None

        cursor.execute("""
            insert into error_logs (
                message,
                details,
                endpoint,
                method,
                payload,
                user_id
            )
            values (%s, %s, %s, %s, %s, %s)
        """, (
            error_message,
            traceback.format_exc(),
            endpoint,
            method,
            str(payload),
            user_id
        ))

        conn.commit()
        cursor.close()

    except Exception as e:
        print("Failed to write to error_logs:", e)
