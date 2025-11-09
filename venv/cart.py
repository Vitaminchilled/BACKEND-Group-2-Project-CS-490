from flask import Blueprint, request, jsonify, current_app
from MySQLdb.cursors import DictCursor
from datetime import datetime
from decimal import Decimal

cart_bp = Blueprint('cart_bp', __name__)

# List all available products
@cart_bp.route('/cart/list', methods=['GET'])
def list_products():
    salon_id = request.args.get('salon_id')

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        if salon_id:
            cursor.execute("""
                SELECT product_id, salon_id, name, description, price, stock_quantity, image_url
                FROM products
                WHERE salon_id = %s AND stock_quantity > 0
            """, (salon_id,))
        else:
            cursor.execute("""
                SELECT product_id, salon_id, name, description, price, stock_quantity, image_url
                FROM products
                WHERE stock_quantity > 0
            """)
        products = cursor.fetchall()
        return jsonify({'products': products}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Add product to cart
@cart_bp.route('/cart/add-to-cart', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    customer_id = data.get('customer_id')
    salon_id = data.get('salon_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    if not all([customer_id, salon_id, product_id]):
        return jsonify({'error': 'Missing required fields'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Check or create active cart
        cursor.execute("""
            SELECT cart_id FROM carts 
            WHERE customer_id = %s AND salon_id = %s AND status = 'active'
        """, (customer_id, salon_id))
        cart = cursor.fetchone()

        if not cart:
            cursor.execute("""
                INSERT INTO carts (customer_id, salon_id, status) VALUES (%s, %s, 'active')
            """, (customer_id, salon_id))
            cart_id = cursor.lastrowid
        else:
            cart_id = cart['cart_id']

        # Check product stock
        cursor.execute("SELECT stock_quantity FROM products WHERE product_id = %s", (product_id,))
        product = cursor.fetchone()
        if not product or product['stock_quantity'] < quantity:
            return jsonify({'error': 'Insufficient stock'}), 400

        # Add or update cart item
        cursor.execute("""
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
        """, (cart_id, product_id, quantity))

        mysql.connection.commit()
        return jsonify({'message': 'Product added to cart successfully'}), 201

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Checkout products in cart
@cart_bp.route('/cart/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    customer_id = data.get('customer_id')
    salon_id = data.get('salon_id')
    wallet_id = data.get('wallet_id')

    if not all([customer_id, salon_id, wallet_id]):
        return jsonify({'error': 'Missing required fields'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Get active cart and items
        cursor.execute("""
            SELECT cart_id FROM carts 
            WHERE customer_id = %s AND salon_id = %s AND status = 'active'
        """, (customer_id, salon_id))
        cart = cursor.fetchone()
        if not cart:
            return jsonify({'error': 'No active cart found'}), 404
        cart_id = cart['cart_id']

        cursor.execute("""
            SELECT ci.cart_item_id, ci.product_id, ci.quantity, p.price
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.product_id
            WHERE ci.cart_id = %s
        """, (cart_id,))
        items = cursor.fetchall()
        if not items:
            return jsonify({'error': 'Cart is empty'}), 400

        subtotal = sum(i['price'] * i['quantity'] for i in items)
        tax = (subtotal * Decimal('0.07')).quantize(Decimal('0.01'))
        total = (subtotal + tax).quantize(Decimal('0.01'))

        # Create invoice
        issued_date = datetime.now().date()
        cursor.execute("""
            INSERT INTO invoices (customer_id, wallet_id, issued_date, status, subtotal_amount, tax_amount, total_amount)
            VALUES (%s, %s, %s, 'paid', %s, %s, %s)
        """, (customer_id, wallet_id, issued_date, subtotal, tax, total))
        invoice_id = cursor.lastrowid

        # Create invoice line items
        for item in items:
            cursor.execute("""
                INSERT INTO invoice_line_items (invoice_id, item_type, product_id, description, quantity, unit_price)
                VALUES (%s, 'product', %s, (SELECT name FROM products WHERE product_id = %s), %s, %s)
            """, (invoice_id, item['product_id'], item['product_id'], item['quantity'], item['price']))

            # Decrease stock
            cursor.execute("""
                UPDATE products SET stock_quantity = stock_quantity - %s WHERE product_id = %s
            """, (item['quantity'], item['product_id']))

        # Mark cart completed
        cursor.execute("UPDATE carts SET status = 'completed' WHERE cart_id = %s", (cart_id,))

        mysql.connection.commit()
        return jsonify({'message': 'Checkout completed successfully', 'invoice_id': invoice_id, 'total_amount': total}), 201

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
