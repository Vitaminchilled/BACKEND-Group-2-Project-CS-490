from flask import Blueprint, request, jsonify, session
import json
from flask import current_app

reviews_bp = Blueprint('reviews', __name__)

@reviews_bp.route('/salon/<int:salon_id>/reviews', methods=['GET'])
def get_reviews(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        salon_query = """
            select salon_id
            from salons
            where salon_id=%s
        """
        cursor.execute(salon_query, (salon_id,))
        salon = cursor.fetchone()
        if not salon:
            return jsonify({"error": "Salon not found"}), 404
        
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
                    select COALESCE(
                    JSON_ARRAYAGG(
                        JSON_OBJECT(
                            'user_first_name', uu.first_name,
                            'user_last_name', uu.last_name,
                            'username', uu.username,
                            'email', uu.email,
                            'reply_id', rr.reply_id,
                            'user_id', rr.user_id,
                            'parent_reply_id', rr.parent_reply_id,
                            'message', rr.message,
                            'created_at', rr.created_at
                        )
                    ), JSON_ARRAY())
                    from review_replies rr
                    left join users uu on rr.user_id = uu.user_id
                    where rr.review_id = r.review_id
                ) as replies_json,
                u.first_name,
                u.last_name,
                u.username,
                u.email
            FROM reviews r
            left join users u on u.user_id = r.customer_id
            where r.salon_id=%s
        """
        cursor.execute(query, (salon_id,))
        reviews = cursor.fetchall()

        result = []
        for review in reviews:
            try:
                replies = json.loads(review[7]) if review[7] else []
            except Exception:
                replies = []

            result.append({
                "review_id": review[0],
                "salon_id": review[1],
                "customer_id": review[2],
                "rating": review[3],
                "comment": review[4],
                "image_url": review[5],
                "review_date": review[6],
                "replies": replies,
                "user_first_name": review[8],
                "user_last_name": review[9],
                "username": review[10],
                "email": review[11]
            })

        cursor.close()
        return jsonify({'reviews': result, "review_count": review_count}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch reviews', 'details': str(e)}), 500