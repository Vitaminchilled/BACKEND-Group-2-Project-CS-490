from flask import Blueprint, request, jsonify, current_app, session
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)

# Get unread count for current user
@notifications_bp.route('/notifications/count', methods=['GET'])
def get_unread_count():
    """Get count of unread notifications for current user"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT COUNT(*) 
            FROM notifications 
            WHERE user_id = %s AND is_read = FALSE
        """
        cursor.execute(query, (user_id,))
        count = cursor.fetchone()[0]
        cursor.close()
        
        return jsonify({'count': count}), 200
    except Exception as e:
        print(f"Error getting notification count: {str(e)}")
        return jsonify({'error': 'Failed to get notification count'}), 500

# Get all notifications for current user
@notifications_bp.route('/notifications', methods=['GET'])
def get_notifications():
    """Get all notifications for current user (newest first)"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT notification_id, user_id, title, message, is_read, created_at
            FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 50
        """
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        
        notifications = []
        for row in rows:
            notifications.append({
                'notification_id': row[0],
                'user_id': row[1],
                'salon_name': 'Salon',  # Default since no salon_id in table
                'title': row[2],
                'message': row[3],
                'is_read': bool(row[4]),
                'created_at': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else None,
                'time_ago': get_time_ago(row[5]) if row[5] else 'Just now'
            })
        
        return jsonify({'notifications': notifications}), 200
    except Exception as e:
        print(f"Error getting notifications: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to get notifications'}), 500

# Mark single notification as read
@notifications_bp.route('/notifications/<int:notification_id>/read', methods=['PUT'])
def mark_as_read(notification_id):
    """Mark a single notification as read"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        query = """
            UPDATE notifications 
            SET is_read = TRUE 
            WHERE notification_id = %s AND user_id = %s
        """
        cursor.execute(query, (notification_id, user_id))
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({'message': 'Notification marked as read'}), 200
    except Exception as e:
        print(f"Error marking notification as read: {str(e)}")
        return jsonify({'error': 'Failed to mark notification as read'}), 500

# Mark all notifications as read
@notifications_bp.route('/notifications/read-all', methods=['PUT'])
def mark_all_as_read():
    """Mark all notifications as read for current user"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        query = """
            UPDATE notifications 
            SET is_read = TRUE 
            WHERE user_id = %s AND is_read = FALSE
        """
        cursor.execute(query, (user_id,))
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({'message': 'All notifications marked as read'}), 200
    except Exception as e:
        print(f"Error marking all notifications as read: {str(e)}")
        return jsonify({'error': 'Failed to mark all notifications as read'}), 500

# Get loyal customers (3+ appointments)
@notifications_bp.route('/salon/<int:salon_id>/customers/loyal', methods=['GET'])
def get_loyal_customers(salon_id):
    """Get customers with 3 or more appointments at this salon"""
    user_id = session.get('user_id')
    role = session.get('role')
    
    print(f"🔍 Session user_id: {user_id}")
    print(f"🔍 Session role: {role}")
    print(f"🔍 Requested salon_id: {salon_id}")
    print(f"🔍 GET /salon/{salon_id}/customers/loyal called")
    print(f"👤 User ID: {user_id}, Role: {role}")
    
    if not user_id or role != 'owner':
        print("❌ Unauthorized - not an owner")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT u.user_id, u.username, u.first_name, u.last_name, 
                   COUNT(a.appointment_id) as appointment_count
            FROM users u
            INNER JOIN appointments a ON u.user_id = a.customer_id
            WHERE a.salon_id = %s AND u.role = 'customer'
            GROUP BY u.user_id, u.username, u.first_name, u.last_name
            HAVING appointment_count >= 3
            ORDER BY appointment_count DESC
        """
        
        print(f"📊 Executing query for salon_id={salon_id}")
        cursor.execute(query, (salon_id,))
        rows = cursor.fetchall()
        print(f"✅ Query returned {len(rows)} rows")
        cursor.close()
        
        customers = []
        for row in rows:
            customer = {
                'user_id': row[0],
                'username': row[1],
                'name': f"{row[2]} {row[3]}" if row[2] and row[3] else row[1],
                'appointment_count': row[4]
            }
            customers.append(customer)
            print(f"👥 Customer: {customer}")
        
        result = {
            'salon_id': salon_id,
            'loyal_customers': customers,
            'count': len(customers)
        }
        print(f"📤 Sending response: {result}")
        return jsonify(result), 200
    except Exception as e:
        print(f"❌ Error getting loyal customers: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to get loyal customers'}), 500

# Search customers by name/username
@notifications_bp.route('/salon/<int:salon_id>/customers/search', methods=['GET'])
def search_customers(salon_id):
    """Search for customers who have appointments at this salon"""
    user_id = session.get('user_id')
    role = session.get('role')
    
    print(f"🔍 GET /salon/{salon_id}/customers/search called")
    print(f"👤 User ID: {user_id}, Role: {role}")
    
    if not user_id or role != 'owner':
        print("❌ Unauthorized - not an owner")
        return jsonify({'error': 'Unauthorized'}), 403
    
    search_term = request.args.get('q', '')
    print(f"🔎 Search term: '{search_term}'")
    
    if len(search_term) < 2:
        print("❌ Search term too short")
        return jsonify({'error': 'Search term must be at least 2 characters'}), 400
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT DISTINCT u.user_id, u.username, u.first_name, u.last_name,
                   COUNT(a.appointment_id) as appointment_count
            FROM users u
            INNER JOIN appointments a ON u.user_id = a.customer_id
            WHERE a.salon_id = %s 
            AND u.role = 'customer'
            AND (u.username LIKE %s 
                 OR u.first_name LIKE %s 
                 OR u.last_name LIKE %s
                 OR CONCAT(u.first_name, ' ', u.last_name) LIKE %s)
            GROUP BY u.user_id, u.username, u.first_name, u.last_name
            ORDER BY appointment_count DESC
            LIMIT 20
        """
        search_pattern = f"%{search_term}%"
        print(f"📊 Executing search query with pattern: {search_pattern}")
        cursor.execute(query, (salon_id, search_pattern, search_pattern, search_pattern, search_pattern))
        rows = cursor.fetchall()
        print(f"✅ Query returned {len(rows)} rows")
        cursor.close()
        
        customers = []
        for row in rows:
            customer = {
                'user_id': row[0],
                'username': row[1],
                'name': f"{row[2]} {row[3]}" if row[2] and row[3] else row[1],
                'appointment_count': row[4]
            }
            customers.append(customer)
            print(f"👥 Found customer: {customer}")
        
        print(f"📤 Sending {len(customers)} search results")
        return jsonify({'customers': customers}), 200
    except Exception as e:
        print(f"❌ Error searching customers: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to search customers'}), 500

# Send notification
@notifications_bp.route('/salon/<int:salon_id>/notifications/send', methods=['POST'])
def send_notification(salon_id):
    """Send notification to specific customers"""
    user_id = session.get('user_id')
    role = session.get('role')
    
    if not user_id or role != 'owner':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    recipient_ids = data.get('recipient_ids', [])
    title = data.get('title', '')
    message = data.get('message', '')
    
    if not recipient_ids or not title or not message:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        # Insert notification - matches actual table schema (user_id, title, message)
        query = """
            INSERT INTO notifications (user_id, title, message)
            VALUES (%s, %s, %s)
        """
        
        for recipient_id in recipient_ids:
            cursor.execute(query, (recipient_id, title, message))
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({
            'message': f'Notification sent to {len(recipient_ids)} customer(s)',
            'count': len(recipient_ids)
        }), 200
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error sending notification: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to send notification'}), 500

# Helper function to calculate "time ago"
def get_time_ago(timestamp):
    """Calculate human-readable time difference"""
    now = datetime.now()
    diff = now - timestamp
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"