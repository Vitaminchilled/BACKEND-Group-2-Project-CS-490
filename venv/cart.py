from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

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
        return jsonify({'error': 'Error adding product'}), 500

#remove from cart
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
        return jsonify({'error': 'Error updating cart'}), 500
    
