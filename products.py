from flask import Blueprint, request, jsonify, current_app, session
from MySQLdb.cursors import DictCursor
from datetime import datetime
from flasgger import swag_from
from utils.logerror import log_error
from s3_uploads import S3Uploader

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
      - multipart/form-data
    parameters:
      - in: formData
        name: salon_id
        type: integer
        required: true
      - in: formData
        name: name
        type: string
        required: true
      - in: formData
        name: description
        type: string
      - in: formData
        name: price
        type: number
        format: float
        required: true
      - in: formData
        name: stock_quantity
        type: integer
      - in: formData
        name: image
        type: file
        required: false
        description: Product image file
    responses:
      201:
        description: Product added successfully
      400:
        description: Missing required fields
      500:
        description: error
    """

    # Read form data
    salon_id = request.form.get('salon_id')
    name = request.form.get('name')
    description = request.form.get('description', '')
    price = request.form.get('price')
    stock_quantity = request.form.get('stock_quantity', 0)

    # File support
    uploaded_file = request.files.get('image')

    if not all([salon_id, name, price]):
        return jsonify({'error': 'Missing required fields (salon_id, name, price)'}), 400

    # Default image URL is None unless uploaded
    image_url = None

    # Upload image if provided
    if uploaded_file:
        try:
            image_url = S3Uploader.upload_image_to_s3(uploaded_file)
        except Exception as e:
            log_error(str(e), session.get("user_id"))
            return jsonify({'error': f"Image upload failed: {str(e)}"}), 500

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
  - multipart/form-data
parameters:
  - name: product_id
    in: path
    type: integer
    required: true
    description: ID of the product to update
  - in: formData
    name: salon_id
    type: integer
    required: true
  - in: formData
    name: name
    type: string
  - in: formData
    name: description
    type: string
  - in: formData
    name: price
    type: number
    format: float
  - in: formData
    name: stock_quantity
    type: integer
  - in: formData
    name: image
    type: file
    required: false
    description: Optional new product image
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

    # Read form data (for file upload support)
    salon_id = request.form.get('salon_id')
    if not salon_id:
        return jsonify({'error': 'Missing salon_id'}), 400

    # Get fields from form data
    fields = []
    values = []
    for key in ['name', 'description', 'price', 'stock_quantity']:
        value = request.form.get(key)
        if value is not None:
            fields.append(f"{key} = %s")
            values.append(value)

    uploaded_file = request.files.get('image')
    if not fields and not uploaded_file:
        return jsonify({'error': 'No update fields provided'}), 401

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        cursor.execute("SELECT salon_id, image_url FROM products WHERE product_id = %s", (product_id,))
        product = cursor.fetchone()

        if not product:
            return jsonify({'error': 'Product not found'}), 404
        if product['salon_id'] != int(salon_id):
            return jsonify({'error': 'Unauthorized: This product does not belong to your salon'}), 403

        # Check for uploaded file
        #uploaded_file = request.files.get('image')
        if uploaded_file:
            try:
                if product.get('image_url'):
                    S3Uploader.delete_image_from_s3(product['image_url'])
                
                image_url = S3Uploader.upload_image_to_s3(uploaded_file)
                fields.append("image_url = %s")
                values.append(image_url)
            except Exception as e:
                log_error(str(e), session.get("user_id"))
                return jsonify({'error': f"Image upload failed: {str(e)}"}), 500

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
