from flask import Blueprint, request, jsonify, current_app, session
from datetime import datetime
from utils.logerror import log_error

cart_bp = Blueprint('cart', __name__)

#view cart
@cart_bp.route('/cart/<int:customer_id>/<int:salon_id>', methods=['GET'])
def view_cart(customer_id, salon_id):
    """
    View cart for a customer in a salon
    ---
    tags:
      - Carts
    parameters:
      - name: customer_id
        in: path
        required: true
        type: integer
      - name: salon_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Cart returned
      500:
        description: Error fetching cart
    """
    try:

        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        #check if cart is active
        query = """
            select cart_id
            from carts 
            where customer_id = %s and salon_id = %s and status = 'active'
        """
        cursor.execute(query, (customer_id, salon_id))
        cart = cursor.fetchone()
        if not cart:
            cursor.close()
            return jsonify({'cart': [], 'message': 'Cart is empty'}), 200

        cart_id = cart[0]

        #get cart items
        query = """
            select cart_items.cart_item_id, cart_items.product_id, cart_items.quantity, products.name, products.price, products.stock_quantity
            from cart_items
            join products on products.product_id = cart_items.product_id
            where cart_items.cart_id = %s
        """    
        cursor.execute(query, (cart_id,))
        items = cursor.fetchall()
        cursor.close()

        cart_list = []
        total = 0 
        for item in items:
            cart_item_id, product_id, quantity, name, price, stock_quantity = item
            subtotal = price * quantity
            total += subtotal
            cart_list.append({
                'cart_item_id': cart_item_id,
                'product_id': product_id,
                'name': name,
                'price': float(price),
                'quantity': quantity,
                'subtotal': float(subtotal),
                'stock_quantity': stock_quantity
            })
        return jsonify({'cart': cart_list, 'total': float(total)}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Error displaying cart'}), 500
    
#add to cart
@cart_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    """
    Add an item to the cart
    ---
    tags:
      - Carts
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            customer_id:
              type: integer
            salon_id:
              type: integer
            product_id:
              type: integer
            quantity:
              type: integer
    responses:
      201:
        description: Product added to cart
      500:
        description: Error adding product
    """
    try:
        data = request.json
        customer_id = data.get('customer_id')
        salon_id = data.get('salon_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)

        if not all([customer_id, salon_id, product_id]):
            return jsonify({'error': 'Missing required fields'}), 400

        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select cart_id
            from carts
            where customer_id = %s and salon_id = %s and status = 'active'
        """
        cursor.execute(query, (customer_id, salon_id))
        cart = cursor.fetchone()
        if not cart:
            #create a new cart for the salon
            cursor.execute("insert into carts(customer_id, salon_id) values(%s, %s)", (customer_id, salon_id))
            cart_id = cursor.lastrowid
        else:
            cart_id = cart[0]
        
        #check if the item exists
        query = """
            select quantity
            from cart_items
            where cart_id = %s and product_id = %s
        """
        cursor.execute(query, (cart_id, product_id))
        item = cursor.fetchone()
        if item:
            new_quantity = item[0] + quantity
            cursor.execute('update cart_items set quantity = %s where cart_id = %s and product_id = %s', (new_quantity, cart_id, product_id))
        else:
            cursor.execute('insert into cart_items(cart_id, product_id, quantity) values(%s, %s, %s)', (cart_id, product_id, quantity))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Product added to cart', 'cart_id': cart_id}), 201
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Error adding product'}), 500

#remove from cart -- GOOD
@cart_bp.route('/cart/remove', methods=['DELETE'])
def remove_from_cart():
    """
    Remove an item from the cart
    ---
    tags:
      - Carts
    consumes:
      - application/json
    parameters:
      - in: body
        required: true
        schema:
            type: object
            properties:
              cart_item_id:
                type: integer
    responses:
      200:
        description: Item removed
      500:
        description: Error removing product
    """
    try:
        data = request.json
        cart_item_id = data.get('cart_item_id')
        if not cart_item_id:
            return jsonify({'error': 'cart_item_id required'}), 400

        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            delete from cart_items
            where cart_item_id = %s
        """
        cursor.execute(query, (cart_item_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Item removed from cart'}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Error removing product'}), 500
    
#update quantity
@cart_bp.route('/cart/update', methods=['PUT'])
def update_cart_quantity():
    """
    Update cart item quantity
    ---
    tags:
      - Carts
    consumes:
      - application/json
    parameters:
      - in: body
        required: true
        schema:
          type: object
          properties:
            cart_item_id:
              type: integer
            quantity:
              type: integer
    responses:
      200:
        description: Quantity updated
      500:
        description: Error updating cart
    """
    try:
        data = request.json
        cart_item_id = data.get('cart_item_id')
        quantity = data.get('quantity')

        if cart_item_id is None or quantity is None:
          return jsonify({'error': 'cart_item_id and quantity required'}), 400
        
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        if quantity < 1:
            query = """
                delete from cart_items
                where cart_item_id = %s
            """
            cursor.execute(cart_item_id,)
            mysql.connection.commit()
            cursor.close()
            return jsonify({'message': 'Cart item removed'}), 200 
        
        query = """
            update cart_items 
            set quantity = %s 
            where cart_item_id = %s
        """
        cursor.execute(query, (quantity, cart_item_id))
           
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Cart quantity updated'}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Error updating cart'}), 500
    

#User cart page -- GOOD
@cart_bp.route('/cart/cartItems', methods=['POST'])
def cartItems():
    """
    Retrieves all active cart items and their product details for a given customer id
    ---
    tags:
      - Carts
    responses:
      200:
        description: Successfully retrieved cart items
      500:
        description: Failed to fetch cart items
      400:
        description: missing user_id
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'Missing user_id in request'}), 400

        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            SELECT
                p.product_id,
                p.name AS product_name,
                p.description,
                p.stock_quantity,
                p.price AS unit_price,
                c.cart_id,
                c.salon_id,
                ci.cart_item_id,
                ci.quantity,
                (ci.quantity * p.price) AS line_total,
                s.name AS salon_name
            FROM
                carts c
            JOIN
                cart_items ci ON c.cart_id = ci.cart_id
            JOIN
                products p ON ci.product_id = p.product_id
            JOIN
                salons s ON c.salon_id = s.salon_id
            WHERE
                c.customer_id = %s
                AND c.status = 'active'
            ORDER BY
                ci.added_at;
        """

        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        cursor.close()
        data = [dict(zip(cols, row)) for row in rows]
        return jsonify({'items': data}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Error viewing cart'}), 500

@cart_bp.route('/cart/getSavedPaymentInfo', methods=['POST'])
def getSavedPaymentInfo():
    """
    Retrieves saved addresses and payment methods for a customer
    ---
    tags:
      - Carts
    responses:
      200:
        description: Successfully retrieved saved payment info
      400:
        description: Missing user_id
      500:
        description: Error retrieving payment info
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'Missing user_id in request'}), 400

        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        address_query = """
            SELECT 
                address_id,
                address,
                city,
                state,
                postal_code,
                country
            FROM addresses
            WHERE customer_id = %s AND entity_type = 'customer'
            ORDER BY last_modified DESC
        """
        cursor.execute(address_query, (user_id,))
        address_rows = cursor.fetchall()
        address_cols = [desc[0] for desc in cursor.description]
        addresses = [dict(zip(address_cols, row)) for row in address_rows]
        
        wallet_query = """
            SELECT 
                w.wallet_id,
                w.last_four,
                w.exp_year,
                w.exp_month,
                w.card_type,
                w.is_default,
                w.billing_address_id,
                a.address AS billing_address,
                a.city AS billing_city,
                a.state AS billing_state,
                a.postal_code AS billing_postal_code,
                a.country AS billing_country
            FROM wallets w
            LEFT JOIN addresses a ON w.billing_address_id = a.address_id
            WHERE w.customer_id = %s
            ORDER BY w.is_default DESC, w.last_modified DESC
        """
        cursor.execute(wallet_query, (user_id,))
        wallet_rows = cursor.fetchall()
        wallet_cols = [desc[0] for desc in cursor.description]
        wallets = [dict(zip(wallet_cols, row)) for row in wallet_rows]
        
        cursor.close()
        
        return jsonify({
            'addresses': addresses,
            'wallets': wallets
        }), 200
        
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': 'Error retrieving saved payment info'}), 500


@cart_bp.route('/cart/processPayment', methods=['POST'])
def processPayment():
    """
    Processes payment for cart items
    ---
    tags:
      - Carts
    responses:
      200:
        description: Payment processed successfully
      400:
        description: Missing required fields or invalid data
      500:
        description: Error processing payment
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        payment_data = data.get('payment_data')
        applied_rewards = data.get('applied_rewards', {})
        
        if not user_id or not payment_data:
            return jsonify({'error': 'Missing required payment information'}), 400

        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = conn.cursor()
        
        cart_query = """
            SELECT
                c.cart_id,
                c.salon_id,
                ci.cart_item_id,
                ci.product_id,
                ci.quantity,
                p.name AS product_name,
                p.price AS unit_price,
                (ci.quantity * p.price) AS line_total,
                s.name AS salon_name
            FROM carts c
            JOIN cart_items ci ON c.cart_id = ci.cart_id
            JOIN products p ON ci.product_id = p.product_id
            JOIN salons s ON c.salon_id = s.salon_id
            WHERE c.customer_id = %s AND c.status = 'active'
        """
        cursor.execute(cart_query, (user_id,))
        cart_items = cursor.fetchall()
        cart_cols = [desc[0] for desc in cursor.description]
        cart_items_list = [dict(zip(cart_cols, row)) for row in cart_items]
        
        if not cart_items_list:
            cursor.close()
            return jsonify({'error': 'No items in cart'}), 400
        address_id = None
        if payment_data.get('rememberAddress') or payment_data.get('remember_address'):
            address_check = """
                SELECT address_id FROM addresses 
                WHERE customer_id = %s 
                AND address = %s 
                AND city = %s 
                AND state = %s 
                AND postal_code = %s
                AND entity_type = 'customer'
            """
            cursor.execute(address_check, (
                user_id,
                payment_data['address'],
                payment_data['city'],
                payment_data['state'],
                payment_data['postal_code']
            ))
            existing_address = cursor.fetchone()
            
            if existing_address:
                address_id = existing_address[0]
            else:
                address_insert = """
                    INSERT INTO addresses (entity_type, customer_id, address, city, state, postal_code, country)
                    VALUES ('customer', %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(address_insert, (
                    user_id,
                    payment_data['address'],
                    payment_data['city'],
                    payment_data['state'],
                    payment_data['postal_code'],
                    payment_data.get('country', 'US')
                ))
                address_id = cursor.lastrowid
        wallet_id = None
        if payment_data.get('rememberCard') or payment_data.get('remember_card'):
            card_number = payment_data['card_number'].replace(' ', '')
            last_four = card_number[-4:]
            
            card_type = 'other'
            first_digit = card_number[0] if len(card_number) > 0 else ''
            first_two = card_number[0:2] if len(card_number) >= 2 else ''
            first_four = card_number[0:4] if len(card_number) >= 4 else ''
            
            if first_digit == '4':
                card_type = 'visa'
            elif first_two in ['51', '52', '53', '54', '55']:
                card_type = 'mastercard'
            elif first_two in ['34', '37']:
                card_type = 'amex'
            elif first_four == '6011':
                card_type = 'discover'
            
            wallet_insert = """
                INSERT INTO wallets (customer_id, billing_address_id, last_four, exp_year, exp_month, card_type, is_default)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute("SELECT COUNT(*) FROM wallets WHERE customer_id = %s", (user_id,))
            wallet_count = cursor.fetchone()
            is_first_card = wallet_count[0] == 0 if wallet_count else True
            
            cursor.execute(wallet_insert, (
                user_id,
                address_id,
                last_four,
                payment_data['exp_year'],
                payment_data['exp_month'],
                card_type,
                is_first_card
            ))
            wallet_id = cursor.lastrowid
        
        salon_totals = {}
        for item in cart_items_list:
            salon_id = str(item['salon_id'])
            if salon_id not in salon_totals:
                salon_totals[salon_id] = {
                    'items': [],
                    'subtotal': 0
                }
            salon_totals[salon_id]['items'].append(item)
            salon_totals[salon_id]['subtotal'] += float(item['line_total'])
        
        invoice_ids = []
        for salon_id, salon_data in salon_totals.items():
            subtotal = salon_data['subtotal']

            discount = 0
            reward_used = None
            if salon_id in applied_rewards and applied_rewards[salon_id]:
                reward = applied_rewards[salon_id]
                if reward.get('is_percentage'):
                    discount = subtotal * (float(reward.get('discount_value', 0)) / 100)
                else:
                    discount = float(reward.get('discount_value', 0))
                reward_used = reward.get('loyalty_program_id')
            
            final_subtotal = subtotal - discount
            tax = final_subtotal * 0.07 
            total = final_subtotal + tax
            
            invoice_insert = """
                INSERT INTO invoices (customer_id, wallet_id, issued_date, status, subtotal_amount, tax_amount, total_amount)
                VALUES (%s, %s, CURDATE(), 'paid', %s, %s, %s)
            """
            cursor.execute(invoice_insert, (user_id, wallet_id, final_subtotal, tax, total))
            invoice_id = cursor.lastrowid
            invoice_ids.append(invoice_id)
            
            for item in salon_data['items']:
                line_item_insert = """
                    INSERT INTO invoice_line_items (invoice_id, item_type, product_id, description, quantity, unit_price)
                    VALUES (%s, 'product', %s, %s, %s, %s)
                """
                cursor.execute(line_item_insert, (
                    invoice_id,
                    item['product_id'],
                    item['product_name'],
                    item['quantity'],
                    item['unit_price']
                ))
            
            for item in salon_data['items']:
                stock_update = """
                    UPDATE products 
                    SET stock_quantity = stock_quantity - %s 
                    WHERE product_id = %s
                """
                cursor.execute(stock_update, (item['quantity'], item['product_id']))
            
            points_earned = int(final_subtotal)
            points_check = """
                SELECT points_id, points_earned, points_redeemed, available_points 
                FROM customer_points 
                WHERE salon_id = %s AND customer_id = %s
            """
            cursor.execute(points_check, (salon_id, user_id))
            existing_points = cursor.fetchone()
            
            if existing_points:
                points_update = """
                    UPDATE customer_points 
                    SET points_earned = points_earned + %s,
                        available_points = available_points + %s
                    WHERE salon_id = %s AND customer_id = %s
                """
                cursor.execute(points_update, (points_earned, points_earned, salon_id, user_id))
            else:
                points_insert = """
                    INSERT INTO customer_points (salon_id, customer_id, points_per_dollar, points_earned, points_redeemed, available_points)
                    VALUES (%s, %s, 1.00, %s, 0, %s)
                """
                cursor.execute(points_insert, (salon_id, user_id, points_earned, points_earned))
            
            if reward_used:
                points_deduct = """
                    UPDATE customer_points 
                    SET points_redeemed = points_redeemed + %s,
                        available_points = available_points - %s
                    WHERE salon_id = %s AND customer_id = %s
                """
                reward_points_query = """
                    SELECT points_required FROM loyalty_programs WHERE loyalty_program_id = %s
                """
                cursor.execute(reward_points_query, (reward_used,))
                reward_points_result = cursor.fetchone()
                points_to_deduct = reward_points_result[0] if reward_points_result else 0
                
                cursor.execute(points_deduct, (points_to_deduct, points_to_deduct, salon_id, user_id))
        
        cursor.execute("UPDATE carts SET status = 'completed' WHERE customer_id = %s AND status = 'active'", (user_id,))
        total_spent = sum([float(st['subtotal']) for st in salon_totals.values()])
        history_check = "SELECT user_history_id FROM user_history WHERE user_id = %s"
        cursor.execute(history_check, (user_id,))
        existing_history = cursor.fetchone()
        
        if existing_history:
            history_update = """
                UPDATE user_history 
                SET total_spent = total_spent + %s,
                    last_visit_date = CURDATE()
                WHERE user_id = %s
            """
            cursor.execute(history_update, (total_spent, user_id))
        else:
            history_insert = """
                INSERT INTO user_history (user_id, total_spent, last_visit_date)
                VALUES (%s, %s, CURDATE())
            """
            cursor.execute(history_insert, (user_id, total_spent))
        
        conn.commit()
        cursor.close()
        
        return jsonify({
            'message': 'Payment processed successfully',
            'invoice_ids': invoice_ids
        }), 200
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        log_error(str(e), session.get("user_id"))
        print(f"Payment processing error: {str(e)}")  # For debugging
        return jsonify({'error': f'Error processing payment: {str(e)}'}), 500
    

@cart_bp.route('/cart/allAvailableRewards', methods=['POST'])
def allAvailableRewards():
    """
    Retrieves available loyalty rewards for a customer at specific salons
    Only returns rewards where the customer has enough points
    ---
    tags:
      - Carts
    responses:
      200:
        description: Successfully retrieved available rewards
      400:
        description: Missing or invalid parameters
      500:
        description: Error fetching rewards
    """
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        salon_ids = data.get("salon_ids")
        
        if not user_id or not salon_ids or not isinstance(salon_ids, list):
            return jsonify({"error": "Missing or invalid user_id or salon_ids list."}), 400
        
        mysql = current_app.config['MYSQL']
        conn = mysql.connection
        cursor = conn.cursor()
        salon_ids_placeholders = ','.join(['%s'] * len(salon_ids))
        
        sql_query = f"""
            SELECT
                s.salon_id,
                s.name AS salon_name,
                COALESCE(cp.available_points, 0) AS available_points,
                lp.loyalty_program_id,
                lp.name AS reward_name,
                lp.points_required,
                lp.discount_value,
                lp.is_percentage
            FROM 
                salons s
            LEFT JOIN 
                customer_points cp ON cp.salon_id = s.salon_id AND cp.customer_id = %s
            LEFT JOIN 
                loyalty_programs lp ON s.salon_id = lp.salon_id
                    AND (lp.end_date IS NULL OR lp.end_date >= CURDATE())
                    AND lp.points_required <= COALESCE(cp.available_points, 0)
            WHERE 
                s.salon_id IN ({salon_ids_placeholders})
            ORDER BY
                s.salon_id, lp.points_required
        """
        params = [user_id] + salon_ids
        
        cursor.execute(sql_query, params)
        results = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        salon_rewards = {}
        
        for row in results:
            row_dict = dict(zip(column_names, row))
            salon_id = row_dict['salon_id']
            
            if salon_id not in salon_rewards:
                salon_rewards[salon_id] = {
                    'salon_id': salon_id,
                    'salon_name': row_dict['salon_name'],
                    'available_points': row_dict['available_points'],
                    'rewards': []
                }
            
            if row_dict['loyalty_program_id'] is not None:
                salon_rewards[salon_id]['rewards'].append({
                    'loyalty_program_id': row_dict['loyalty_program_id'],
                    'reward_name': row_dict['reward_name'],
                    'points_required': row_dict['points_required'],
                    'discount_value': float(row_dict['discount_value']),
                    'is_percentage': bool(row_dict['is_percentage'])
                })
        
        cursor.close()
        return jsonify(list(salon_rewards.values())), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        print(f"Error fetching rewards: {str(e)}")
        return jsonify({'error': 'Error fetching salon loyalty rewards'}), 500