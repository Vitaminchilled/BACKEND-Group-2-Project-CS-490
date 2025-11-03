from flask import Blueprint, request, jsonify, current_app, session
import json
from datetime import datetime

reviews_bp = Blueprint('reviews', __name__)

@reviews_bp.route('/salon/<int:salon_id>/reviews', methods=['GET'])
def get_reviews(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        salon_query = """
            select salon_id, owner_id
            from salons
            where salon_id=%s
        """
        cursor.execute(salon_query, (salon_id,))
        salon = cursor.fetchone()
        if not salon:
            return jsonify({"error": "Salon not found"}), 404
        owner_id = salon[1] 

        review_count_query = """
            select count(*)
            from reviews
            where salon_id=%s
        """
        cursor.execute(review_count_query, (salon_id,))
        review_count = cursor.fetchone()

        query = """
            SELECT 
                r.review_id,
                r.salon_id,
                r.customer_id,
                r.rating,
                r.comment,
                r.image_url,
                r.review_date,
                (
                    SELECT COALESCE(
                        JSON_ARRAYAGG(
                            JSON_OBJECT(
                                'reply_id', rr.reply_id,
                                'user_id', rr.user_id,
                                'first_name', uu.first_name,
                                'last_name', uu.last_name,
                                'message', rr.message,
                                'created_at', rr.created_at
                            )
                        ), JSON_ARRAY()
                    )
                    FROM review_replies rr
                    LEFT JOIN users uu ON rr.user_id = uu.user_id
                    WHERE rr.review_id = r.review_id
                ) AS replies_json,
                u.first_name,
                u.last_name,
                u.user_id
            FROM reviews r
            LEFT JOIN users u ON u.user_id = r.customer_id
            WHERE r.salon_id=%s
            ORDER BY r.review_date DESC
        """
        cursor.execute(query, (salon_id,))
        reviews = cursor.fetchall()

        result = []
        for review in reviews:
            try:
                replies = json.loads(review[7]) if review[7] else []
            except Exception:
                replies = []

            customer_name = f"{review[8]} {review[9][0].upper()}." if review[8] and review[9] else review[8] or "Anonymous"
            formatted_replies = []
            for reply in replies:
                if reply["user_id"] == owner_id:
                    display_name = "Owner"
                else:
                    fn = reply.get("first_name", "")
                    ln = reply.get("last_name", "")
                    display_name = f"{fn} {ln[0].upper()}." if fn and ln else fn or "Anonymous"

                formatted_replies.append({
                    "reply_id": reply["reply_id"],
                    "user_id": reply["user_id"],
                    "user": display_name,
                    "message": reply["message"],
                    "created_at": reply["created_at"]
                })

            result.append({
                "review_id": review[0],
                "rating": review[3],
                "comment": review[4],
                "image_url": review[5],
                "review_date": review[6],
                "customer_name": customer_name,
                "customer_id": review[10],  
                "replies": formatted_replies
            })

        cursor.close()
        return jsonify({'reviews': result, "review_count": review_count}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to fetch reviews', 'details': str(e)}), 500


@reviews_bp.route('/appointments/<int:appointment_id>/review', methods=['POST'])
def post_review(appointment_id):
    try: 
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json()
        rating = data.get('rating')
        comment = data.get('comment')
        image_url = data.get('image_url', None)
        
        if not rating or not comment: 
            return jsonify({'error': 'Missing rating or comment'}), 400
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        #user must have completed an appointment
        query = """
            select salon_id, customer_id, status
            from appointments
            where appointment_id = %s
        """
        cursor.execute(query, (appointment_id,))
        appointment = cursor.fetchone()
        salon_id, customer_id, status = appointment
        if customer_id != user_id:
            return jsonify({'error': 'You can only review your own appointments'}), 403
        if status != 'completed':
            return jsonify({'error': 'You can only review completed appointments'}), 400
        
        #user cannot review the same appointment twice
        query = """
            select review_id
            from reviews
            where appointment_id = %s
        """
        cursor.execute(query, (appointment_id,))
        if cursor.fetchone():
            return jsonify({'error': 'Review already exists for this appointment'}), 400
        
        now = datetime.now()
        query = """
            insert into reviews(appointment_id, customer_id, salon_id, rating, comment, image_url, review_date)
            values(%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (appointment_id, user_id, salon_id, rating, comment, image_url, now))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Review posted successfully'}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to post review'}), 500

@reviews_bp.route('/reviews/<int:review_id>/reply', methods=['POST'])
def post_reply(review_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json()
        reply = data.get('reply')
        if not reply:
            return jsonify({'error': 'Replies cannot be empty'}), 400
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        now = datetime.now()
        query = """
            insert into review_replies(review_id, user_id, message, created_at)
            values(%s, %s, %s, %s)
        """
        cursor.execute(query, (review_id, user_id, reply, now))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Reply posted successfully'}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to post reply'}), 500

@reviews_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
def delete_review(review_id):
    try:
        user_role = session.get('role')
        if user_role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 401
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            delete from review_replies
            where review_id = %s
        """
        cursor.execute(query, (review_id,))
        query = """
            delete from reviews
            where review_id = %s
        """
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Review deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to delete review'}), 500

@reviews_bp.route('/reviews/<int:reply_id>', methods=['DELETE'])
def delete_reply(reply_id):
    try:
        user_role = session.get('role')
        if user_role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 401
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            delete from review_replies
            where reply_id = %s
        """
        cursor.execute(query, (reply_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Reply deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to delete reply'}), 500
    
