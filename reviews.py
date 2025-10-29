from flask import Blueprint, request, jsonify, session
import json
from flask import current_app

reviews_bp = Blueprint('reviews', __name__)

@reviews_bp.route('/salon/reviews/<int:salon_id>', methods=['GET'])
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

        query = """
            select 
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
                            'reply_id', rr.reply_id,
                            'user_id', rr.user_id,
                            'parent_reply_id', rr.parent_reply_id,
                            'message', rr.message,
                            'created_at', rr.created_at
                        )
                    ), JSON_ARRAY())
                    from review_replies rr
                    where rr.review_id = r.review_id
                ) as replies
            from reviews r
            where salon_id=%s
        """
        cursor.execute(query, (salon_id,))
        reviews = cursor.fetchall()

        result = []
        for review in reviews:
            replies_json = review[7]
            try:
                replies = json.loads(replies_json) if replies_json else []
            except Exception:
                replies = []

        cursor.close()
        return jsonify({
            'reviews': [{
                "review_id": review[0],
                "salon_id": review[1],
                "customer_id": review[2],
                "rating": review[3],
                "comment": review[4],
                "image_url": review[5],
                "review_date": review[6],
                "replies": replies
            } for review in reviews]
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch reviews', 'details': str(e)}), 500