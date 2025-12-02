from flask import Blueprint, request, jsonify, current_app, session
import json
from datetime import datetime

reviews_bp = Blueprint('reviews', __name__)

@reviews_bp.route('/salon/<int:salon_id>/reviews', methods=['GET'])
def get_reviews(salon_id):
    """
Get all reviews for a salon with replies
---
tags:
  - Reviews
parameters:
  - name: salon_id
    in: path
    required: true
    type: integer
    description: Salon ID
responses:
  200:
    description: Reviews retrieved successfully with reply count
  404:
    description: Salon not found
  500:
    description: Error fetching reviews
"""
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
        review_count = cursor.fetchone()[0]

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
                                'first_name', uu.first_name,
                                'last_name', uu.last_name,
                                'message', rr.message,
                                'created_at', rr.created_at
                            )
                        ), JSON_ARRAY()
                    )
                    from review_replies rr
                    left join users uu on rr.user_id = uu.user_id
                    where rr.review_id = r.review_id
                ) as replies_json,
                u.first_name,
                u.last_name,
                u.user_id
            from reviews r
            left join users u on u.user_id = r.customer_id
            where r.salon_id=%s
            order by r.review_date desc
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

@reviews_bp.route('/salon/<int:salon_id>/dashboard/reviews', methods=['GET'])
def recent_three(salon_id):
    """
Get recent 3 reviews for salon dashboard
---
tags:
  - Reviews
parameters:
  - name: salon_id
    in: path
    required: true
    type: integer
    description: Salon ID
responses:
  201:
    description: Recent reviews retrieved successfully
  500:
    description: Error fetching reviews
"""
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select users.first_name, concat(left(users.last_name, 1), '.') as last_initial, reviews.rating, reviews.comment
            from reviews
            join users on reviews.customer_id = users.user_id
            where salon_id = %s
            limit 3;
        """
        cursor.execute(query, (salon_id,))
        reviews = cursor.fetchall()
        cursor.close()
        return jsonify({'reviews': reviews}), 201
    except Exception as e:
        return jsonify({'error': 'Failed to fetch reviews', 'details': str(e)}), 500

def generate_iter_pages(current_page, total_pages, left_edge=2, right_edge=2, left_current=2, right_current=2):
    last = 0
    pages = []
    for num in range(1, total_pages + 1):
        if (
            num <= left_edge or
            (current_page - left_current - 1 < num < current_page + right_current) or
            num > total_pages - right_edge
        ):
            if last + 1 != num:
                pages.append('...')  # gap
            pages.append(num)
            last = num
    return pages

@reviews_bp.route('/salon/<int:salon_id>/reviews/pagination', methods=['GET'])
def get_paginated_reviews(salon_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        page = request.args.get('page', default=1, type=int)
        per_page = 10
        offset = (page - 1) * per_page

        #tbd might remove feature
        keywords = request.args.get('keywords', default="", type=str).strip()
        #
        rating = request.args.get('rating', default=-1, type=int)
        direction = request.args.get('direction', default="desc", type=str) #high to low/new to old
        order_by = request.args.get('order_by', default="review_date", type=str) #review_date or rating
        #recency, rating, ...
        has_img = request.args.get('has_img', default="false", type=str).lower() == "true"

        valid_order_by = {"review_date", "rating"}
        if order_by not in valid_order_by:
            order_by = "review_date"

        valid_direction = {"asc", "desc"}
        if direction not in valid_direction:
            direction = "desc"

        valid_rating = {-1,1,2,3,4,5}
        if rating not in valid_rating:
            rating = -1

        filters = ["r.salon_id = %s"] #idk if I should make it an fstring to insert salon_id
        params = [salon_id]

        salon_query = """
            select salon_id, owner_id
            from salons
            where salon_id=%s
        """
        cursor.execute(salon_query, (salon_id,))
        salon = cursor.fetchone()
        if not salon:
            return jsonify({"error": "Salon not found"}), 404
        owner_id = salon[1] #not used in new method might remove here

        #tbd keywords is difficult to implement
        if keywords:
            filters.append("(r.comment LIKE %s OR EXISTS ( \
                            SELECT 1 FROM review_replies rr \
                            WHERE rr.review_id = r.review_id \
                            AND rr.message LIKE %s))")
            params.append(f"%{keywords}%")
            params.append(f"%{keywords}%")

        if rating != -1:
            if rating == 1: 
                rating_query = "r.rating >= %s AND r.rating <= %s"
            else:
                rating_query = "r.rating > %s AND r.rating <= %s"
            filters.append(rating_query)
            params.append(rating-1) #lower bound ex. above 4 max 5
            params.append(rating) #upper bound passed as arg

        if has_img:
            filters.append("r.image_url IS NOT NULL AND r.image_url != ''")

        where_clause = "WHERE " + " AND ".join(filters) if filters else ""

        review_count_query = f"""
            select count(*)
            from reviews r
            {where_clause}
        """
        cursor.execute(review_count_query, params)
        total = cursor.fetchone()[0]

        query = f"""
            select 
                r.review_id,
                r.salon_id,
                r.customer_id,
                r.rating,
                r.comment,
                r.image_url,
                r.review_date,
                (
                    select EXISTS(
                        select 1 from review_replies rr
                        where rr.review_id = r.review_id
                            and rr.parent_reply_id is null
                    )
                ) as has_replies,
                u.first_name,
                u.last_name,
                u.user_id
            from reviews r
            left join users u on u.user_id = r.customer_id
            {where_clause}
            order by r.{order_by} {direction}
            limit %s offset %s
        """
        cursor.execute(query, (*params, per_page, offset))
        reviews = cursor.fetchall()

        total_pages = -(-total // per_page)
        iter_pages = generate_iter_pages(current_page=page, total_pages=total_pages)

        result = []
        for review in reviews:

            customer_name = f"{review[8]} {review[9][0].upper()}." if review[8] and review[9] else review[8] or "Anonymous"

            result.append({
                "review_id": review[0],
                "rating": review[3],
                "comment": review[4],
                "image_url": review[5],
                "review_date": review[6],
                "customer_name": customer_name,
                "customer_id": review[10],  
                "has_replies": bool(review[7])
            })
        return jsonify({
            'reviews': result, 
            "page": page,
            "review_count": total,
            "total_retrieved": len(reviews),
            'total_pages' : total_pages,
            'iter_pages': iter_pages
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch reviews', 'details': str(e)}), 500
    finally:
        cursor.close()

@reviews_bp.route('/salon/<int:salon_id>/reviews/<int:review_id>/replies')
def get_children_replies(salon_id, review_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        parent_id = request.args.get('parent_id', default=0, type=int)

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

        reply_count_query = f"""
            select count(*)
            FROM review_replies rr
            WHERE rr.review_id = %s
        """
        cursor.execute(reply_count_query, (review_id,))
        reply_count = cursor.fetchone()[0]

        replies_query = """
            SELECT 
                rr.reply_id,
                rr.user_id,
                u.first_name,
                u.last_name,
                rr.parent_reply_id,
                rr.message,
                rr.created_at,
                (
                    select EXISTS(
                        select 1 
                        from review_replies c
                        where c.parent_reply_id = rr.reply_id
                    )
                ) as has_replies
            FROM review_replies rr
            LEFT JOIN users u ON rr.user_id = u.user_id
            WHERE rr.review_id = %s
            ORDER BY rr.created_at DESC
        """
        cursor.execute(replies_query, (review_id,))
        replies = cursor.fetchall()

        result = []
        for reply in replies:
            if reply[1] == owner_id:
                display_name = "Owner"
            else:
                fn = reply[2]
                ln = reply[3]
                display_name = f"{fn} {ln[0].upper()}." if fn and ln else fn or "Anonymous"

            result.append({
                "reply_id": reply[0],
                "user_id": reply[1],
                "user": display_name,
                "parent_reply_id": reply[4],
                "message": reply[5],
                "created_at": reply[6],
                "has_replies": bool(reply[7])
            })

        return jsonify({
            'replies': result,
            'reply_count': reply_count #all replies but this query returns one level of replies
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch replies', 'details': str(e)}), 500
    finally:
        cursor.close()

@reviews_bp.route('/appointments/<int:appointment_id>/review', methods=['POST'])
def post_review(appointment_id):
    """
Post a review for a completed appointment
---
tags:
  - Reviews
consumes:
  - application/json
parameters:
  - name: appointment_id
    in: path
    required: true
    type: integer
  - in: body
    name: body
    required: true
    schema:
      type: object
      properties:
        rating:
          type: integer
        comment:
          type: string
        image_url:
          type: string
      required:
        - rating
        - comment
responses:
  201:
    description: Review posted successfully
  400:
    description: Missing fields, appointment not completed, or review already exists
  401:
    description: Unauthorized
  403:
    description: Cannot review other users' appointments
  500:
    description: Failed to post review
"""
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
    """
Post a reply to a review
---
tags:
  - Reviews
consumes:
  - application/json
parameters:
  - name: review_id
    in: path
    required: true
    type: integer
  - in: body
    name: body
    required: true
    schema:
      type: object
      properties:
        reply:
          type: string
      required:
        - reply
responses:
  201:
    description: Reply posted successfully
  400:
    description: Reply cannot be empty
  401:
    description: Unauthorized
  500:
    description: Failed to post reply
"""
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
    """
Delete a review (admin or review owner only)
---
tags:
  - Reviews
parameters:
  - name: review_id
    in: path
    required: true
    type: integer
responses:
  200:
    description: Review deleted successfully
  401:
    description: Unauthorized
  404:
    description: Review not found
  500:
    description: Failed to delete review
"""
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        #find out who posted the review
        query = """
            select customer_id
            from reviews
            where review_id = %s
        """
        cursor.execute(query, (review_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Review not found'}), 404
        reviewer_id = row[0]

        user_id = session.get('user_id')
        user_role = session.get('role')
        if user_role != 'admin' and user_id != reviewer_id:
            return jsonify({'error': 'Unauthorized'}), 401

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

@reviews_bp.route('/reviews/reply/<int:reply_id>', methods=['DELETE'])
def delete_reply(reply_id):
    """
Delete a reply (admin or reply owner only)
---
tags:
  - Reviews
parameters:
  - name: reply_id
    in: path
    required: true
    type: integer
responses:
  200:
    description: Reply deleted successfully
  401:
    description: Unauthorized
  404:
    description: Reply not found
  500:
    description: Failed to delete reply
    """
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        #find out who posted the reply
        query = """
            select customer_id
            from review_replies
            where reply_id = %s
        """
        cursor.execute(query, (reply_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Review not found'}), 404
        replier_id = row[0]

        user_id = session.get('user_id') 
        user_role = session.get('role')
        if user_role != 'admin' and user_id != replier_id:
            return jsonify({'error': 'Unauthorized'}), 401

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
    
