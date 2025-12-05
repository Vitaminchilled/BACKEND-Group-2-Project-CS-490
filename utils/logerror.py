import traceback
import json
from flask import request, current_app

def log_error(error_message, user_id=None):
    try:
        mysql = current_app.config.get('MYSQL')
        if not mysql:
            print("MYSQL not initialized in current_app.config!")
            return

        conn = mysql.connection
        cursor = conn.cursor()

        # --- SAFE REQUEST EXTRACTION ---
        try:
            endpoint = request.path
            method = request.method
            payload = request.get_json(silent=True)
        except Exception:
            endpoint = None
            method = None
            payload = None

        # Ensure valid JSON for JSON columns
        payload_json = json.dumps(payload) if payload is not None else None

        # --- GET TRACEBACK SAFELY ---
        tb = traceback.format_exc()
        if tb.strip() == "NoneType: None\n" or tb.strip() == "":
            details = error_message
        else:
            details = tb

        # Ensure `details` is JSON-safe (string)
        if not isinstance(details, str):
            details = str(details)

        cursor.execute("""
            INSERT INTO error_logs (
                message,
                details,
                endpoint,
                method,
                payload,
                user_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            error_message,
            details,
            endpoint,
            method,
            payload_json,
            user_id
        ))

        conn.commit()
        cursor.close()

        print("Error logged successfully")

    except Exception as e:
        print("Failed to write to error_logs:", e)
