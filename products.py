from flask import Blueprint, request, jsonify, current_app
from MySQLdb.cursors import DictCursor
from datetime import datetime

products_bp = Blueprint('products_bp', __name__)

# View all products for a salon
@products_bp.route('/products/view', methods=['GET'])
def get_products():
    salon_id = request.args.get('salon_id')

    if not salon_id:
        return jsonify({'error': 'Missing salon_id'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("""
            SELECT product_id, salon_id, name, description, price, stock_quantity, image_url, created_at
            FROM products
            WHERE salon_id = %s
            ORDER BY created_at DESC
        """, (salon_id,))
        products = cursor.fetchall()
        return jsonify({'products': products}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Add a new product
@products_bp.route('/products', methods=['POST'])
def add_product():
    data = request.get_json()

    salon_id = data.get('salon_id')
    name = data.get('name')
    description = data.get('description', '')
    price = data.get('price')
    stock_quantity = data.get('stock_quantity', 0)
    image_url = data.get('image_url', None)

    if not all([salon_id, name, price]):
        return jsonify({'error': 'Missing required fields (salon_id, name, price)'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("""
            INSERT INTO products (salon_id, name, description, price, stock_quantity, image_url, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (salon_id, name, description, price, stock_quantity, image_url))
        mysql.connection.commit()

        return jsonify({'message': 'Product added successfully'}), 201

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Edit/update an existing product
@products_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json()
    salon_id = data.get('salon_id')

    if not salon_id:
        return jsonify({'error': 'Missing salon_id'}), 400

    fields = []
    values = []

    for key in ['name', 'description', 'price', 'stock_quantity', 'image_url']:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])

    if not fields:
        return jsonify({'error': 'No update fields provided'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("SELECT salon_id FROM products WHERE product_id = %s", (product_id,))
        product = cursor.fetchone()

        if not product:
            return jsonify({'error': 'Product not found'}), 404
        if product['salon_id'] != int(salon_id):
            return jsonify({'error': 'Unauthorized: This product does not belong to your salon'}), 403

        # Update product
        query = f"UPDATE products SET {', '.join(fields)}, last_modified = NOW() WHERE product_id = %s"
        values.append(product_id)
        cursor.execute(query, tuple(values))
        mysql.connection.commit()

        return jsonify({'message': 'Product updated successfully'}), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Remove a product
@products_bp.route('/products/delete/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    salon_id = request.args.get('salon_id')

    if not salon_id:
        return jsonify({'error': 'Missing salon_id'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("SELECT salon_id FROM products WHERE product_id = %s", (product_id,))
        product = cursor.fetchone()

        if not product:
            return jsonify({'error': 'Product not found'}), 404
        if product['salon_id'] != int(salon_id):
            return jsonify({'error': 'Unauthorized: Cannot delete another salon\'s product'}), 403

        cursor.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        mysql.connection.commit()

        return jsonify({'message': 'Product deleted successfully'}), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()