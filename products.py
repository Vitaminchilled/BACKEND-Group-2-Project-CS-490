from flask import Blueprint, request, jsonify, current_app, session
from MySQLdb.cursors import DictCursor
from datetime import datetime
from flasgger import swag_from
from utils.logerror import log_error

products_bp = Blueprint('products_bp', __name__)

# View all products for a salon
@products_bp.route('/products/view', methods=['GET'])
def get_products():
    """
    View products
    ---
    tags:
      - Products
    consumes:
      - application/json
    parameters:
      - name: salon_id
        in: query
        type: integer
        required: true
        description: The salon ID to fetch products for
    responses:
      200:
        description: Products shown
      400:
        description: Missing salon_id
      500:
        description: error
    """
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
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Add a new product
@products_bp.route('/products', methods=['POST'])
def add_product():
    """
    Add products
    ---
    tags:
      - Products
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
          - salon_id
          - name
          - price
          properties:
            salon_id:
              type: integer
            name:
              type: string
            description:
              type: string
            price:
              type: number
              format: float
            stock_quantity:
              type: integer
            image_url:
              type: string
              format: url
    responses:
      201:
        description: Product added successfully
      400:
        description: Missing required fields (salon_id, name, price)
      500:
        description: error
    """
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
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Edit/update an existing product
@products_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """
Edit/update product
---
tags:
  - Products
consumes:
  - application/json
parameters:
  - name: product_id
    in: path
    type: integer
    required: true
    description: ID of the product to update
  - in: body
    name: body
    required: true
    schema:
      type: object
      properties:
        salon_id:
          type: integer
        name:
          type: string
        description:
          type: string
        price:
          type: number
          format: float
        stock_quantity:
          type: integer
        image_url:
          type: string
          format: uri
responses:
  200:
    description: Product updated successfully
  400:
    description: Missing salon_id
  401:
    description: No update fields provided
  403:
    description: Product does not belong to this salon
  404:
    description: Product not found
  500:
    description: Internal server error
    """

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
        return jsonify({'error': 'No update fields provided'}), 401

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
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Remove a product
@products_bp.route('/products/delete/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """
    Delete a product
    ---
    tags:
      - Products
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
        description: ID of the product to delete
      - name: salon_id
        in: query
        type: integer
        required: true
        description: The salon ID making the delete request
    responses:
      200:
        description: Product deleted successfully
      400:
        description: Missing salon_id
      403:
        description: Cannot delete another salon's product
      404:
        description: Product not found
      500:
        description: Internal server error
    """
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
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()