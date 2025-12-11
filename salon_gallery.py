import os
from flask import Blueprint, request, jsonify, current_app, session
from datetime import datetime
from utils.logerror import log_error
from s3_uploads import S3Uploader
salon_gallery_bp = Blueprint('salon_gallery', __name__)

#get salon pictures
@salon_gallery_bp.route('/salon/<int:salon_id>/gallery', methods=['GET'])
def get_gallery(salon_id):
    """
Get all gallery images for a salon
---
tags:
  - Salon Gallery
parameters:
  - name: salon_id
    in: path
    required: true
    type: integer
    description: Salon ID
responses:
  200:
    description: Gallery images retrieved successfully
  404:
    description: No images found for this salon
  500:
    description: Error fetching gallery
"""
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select gallery_id, salon_id, image_url, description, created_at, last_modified
            from salon_gallery
            where salon_id = %s
            order by created_at desc
        """
        cursor.execute(query, (salon_id,))
        images = cursor.fetchall()
        cursor.close()

        if not images:
            return jsonify({'message': 'No images found for this salon'}), 404
        
        gallery = []
        for image in images:
            gallery.append({
                    'gallery_id': image[0],
                    'salon_id': image[1],
                    'image_url': image[2],
                    'description': image[3],
                    'created_at': image[4].strftime('%Y-%m-%d %H:%M:%S') if image[4] else None,
                    'last_modified': image[5].strftime('%Y-%m-%d %H:%M:%S') if image[5] else None
                })
        
        return jsonify({'salon_id': salon_id, 'gallery': gallery}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        cursor.close()
        return jsonify({'error': 'The salon galley could not be displayed'}), 500

#get salon's primary picture
@salon_gallery_bp.route('/salon/<int:salon_id>/image', methods=['GET'])
def get_salon_image(salon_id):
    """
Get salon's primary profile picture
---
tags:
  - Salon Gallery
parameters:
  - name: salon_id
    in: path
    required: true
    type: integer
    description: Salon ID
responses:
  200:
    description: Primary salon image retrieved successfully
  500:
    description: No profile picture found
"""
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select gallery_id, salon_id, image_url, created_at, last_modified
            from salon_gallery
            where salon_id = %s and is_primary = true
        """
        cursor.execute(query, (salon_id,))
        image = cursor.fetchone()
        cursor.close()

        return jsonify({
            'gallery_id': image[0],
            'salon_id': image[1],
            'image_url': image[2],
            'created_at': image[3].strftime('%Y-%m-%d %H:%M:%S') if image[3] else None,
            'last_modified': image[4].strftime('%Y-%m-%d %H:%M:%S') if image[4] else None
        }), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        cursor.close()
        return jsonify({'error': 'No profile picture to be displayed'}), 500

#get emloyees pictures
@salon_gallery_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>/image', methods=['GET'])
def get_employee_image(salon_id, employee_id):
    """
Get employee profile picture
---
tags:
  - Salon Gallery
parameters:
  - name: salon_id
    in: path
    required: true
    type: integer
  - name: employee_id
    in: path
    required: true
    type: integer
responses:
  200:
    description: Employee image retrieved successfully
  500:
    description: No employee photo found
"""
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select gallery_id, salon_id, employee_id, image_url, created_at, last_modified
            from salon_gallery
            where salon_id = %s and employee_id = %s
        """
        cursor.execute(query, (salon_id, employee_id))
        image = cursor.fetchone()
        cursor.close()

        return jsonify({
            'gallery_id': image[0],
            'salon_id': image[1],
            'employee_id': image[2],
            'image_url': image[3],
            'created_at': image[4].strftime('%Y-%m-%d %H:%M:%S') if image[4] else None,
            'last_modified': image[5].strftime('%Y-%m-%d %H:%M:%S') if image[5] else None
        }), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        cursor.close()
        return jsonify({'error': 'No employee photo to be displayed'}), 500
    
#get product thumbnails
@salon_gallery_bp.route('/salon/<int:salon_id>/products/<int:product_id>/image', methods=['GET'])
def get_product_image(salon_id, product_id):
    """
Get product thumbnail image
---
tags:
  - Salon Gallery
parameters:
  - name: salon_id
    in: path
    required: true
    type: integer
  - name: product_id
    in: path
    required: true
    type: integer
responses:
  200:
    description: Product image retrieved successfully
  500:
    description: No product photo found
"""
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select gallery_id, salon_id, product_id, image_url, created_at, last_modified
            from salon_gallery
            where salon_id = %s and product_id = %s
        """
        cursor.execute(query, (salon_id, product_id))
        image = cursor.fetchone()
        cursor.close()

        return jsonify({
            'gallery_id': image[0],
            'salon_id': image[1],
            'product_id': image[2],
            'image_url': image[3],
            'created_at': image[4].strftime('%Y-%m-%d %H:%M:%S') if image[4] else None,
            'last_modified': image[5].strftime('%Y-%m-%d %H:%M:%S') if image[5] else None
        }), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        cursor.close()
        return jsonify({'error': 'No product photo to be displayed'}), 500


@salon_gallery_bp.route('/salon/<int:salon_id>/gallery/upload', methods=['POST'])
def upload_image(salon_id):
    """
Upload image to salon gallery
---
tags:
  - Salon Gallery
consumes:
  - multipart/form-data
parameters:
  - name: salon_id
    in: path
    required: true
    type: integer
  - name: image
    in: formData
    required: true
    type: file
  - name: description
    in: formData
    type: string
  - name: employee_id
    in: formData
    type: integer
  - name: service_id
    in: formData
    type: integer
  - name: is_primary
    in: formData
    type: boolean
responses:
  201:
    description: Image uploaded
  400:
    description: Invalid input
  500:
    description: Failed
"""
    image = request.files.get('image')
    description = request.form.get('description', '')
    employee_id = request.form.get('employee_id')
    service_id = request.form.get('service_id')
    is_primary = request.form.get('is_primary', "false").lower() == "true"

    employee_id = int(employee_id) if employee_id else None
    service_id = int(service_id) if service_id else None

    if not image:
        return jsonify({'error': 'Image file is required'}), 400

    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        if employee_id:
            cursor.execute("""
                SELECT employee_id FROM employees
                WHERE employee_id = %s AND salon_id = %s
            """, (employee_id, salon_id))

            if not cursor.fetchone():
                cursor.close()
                return jsonify({'error': f'Employee {employee_id} does not belong to salon {salon_id}'}), 400

        if service_id:
            cursor.execute("""
                SELECT service_id FROM services
                WHERE service_id = %s AND salon_id = %s
            """, (service_id, salon_id))

            if not cursor.fetchone():
                cursor.close()
                return jsonify({'error': f'Service {service_id} does not belong to salon {salon_id}'}), 400

        if is_primary and not employee_id and not service_id:
            cursor.execute("""
                SELECT image_url FROM salon_gallery
                WHERE salon_id = %s AND is_primary = TRUE
            """, (salon_id,))
            old_primary = cursor.fetchone()

            if old_primary and old_primary[0]:
                S3Uploader.delete_image_from_s3(old_primary[0])

            cursor.execute("""
                UPDATE salon_gallery
                SET is_primary = FALSE
                WHERE salon_id = %s AND is_primary = TRUE
            """, (salon_id,))

        image_url = S3Uploader.upload_image_to_s3(image)

        cursor.execute("""
            INSERT INTO salon_gallery 
            (salon_id, image_url, description, employee_id, service_id, is_primary, created_at, last_modified)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (salon_id, image_url, description, employee_id, service_id, is_primary))

        mysql.connection.commit()
        gallery_id = cursor.lastrowid
        cursor.close()

        return jsonify({
            "message": "Image uploaded successfully",
            "gallery_id": gallery_id,
            "image_url": image_url
        }), 201

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': f"Failed to upload image: {str(e)}"}), 500


@salon_gallery_bp.route('/salon/gallery/<int:gallery_id>/update', methods=['PUT'])
def update_image(gallery_id):
    """
Update gallery image
---
tags:
  - Salon Gallery
consumes:
  - multipart/form-data
parameters:
  - name: gallery_id
    in: path
    required: true
    type: integer
  - name: image
    in: formData
    type: file
    description: New image file
  - name: description
    in: formData
    type: string
    description: New image description
responses:
  200:
    description: Image updated successfully
  400:
    description: No fields to update provided
  404:
    description: Gallery image not found
  500:
    description: Failed to update image
"""
    image = request.files.get('image')
    description = request.form.get('description')

    if not any([image, description]):
        return jsonify({'error': 'No fields to update provided'}), 400

    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        # Get existing data
        cursor.execute("""
            SELECT image_url, description
            FROM salon_gallery
            WHERE gallery_id = %s
        """, (gallery_id,))
        gallery = cursor.fetchone()

        if not gallery:
            cursor.close()
            return jsonify({'error': 'Gallery image not found'}), 404

        old_image_url = gallery[0]
        old_description = gallery[1]

        new_image_url = old_image_url

        if image:
            new_image_url = S3Uploader.upload_image_to_s3(image)

            if old_image_url:
                S3Uploader.delete_image_from_s3(old_image_url)

        if description is None:
            description = old_description

        cursor.execute("""
            UPDATE salon_gallery
            SET image_url = %s,
                description = %s,
                last_modified = NOW()
            WHERE gallery_id = %s
        """, (new_image_url, description, gallery_id))

        mysql.connection.commit()
        cursor.close()

        return jsonify({'message': 'Image updated successfully'}), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': f'Failed to update image: {str(e)}'}), 500
    

@salon_gallery_bp.route('/salon/gallery/<int:gallery_id>/delete', methods=['DELETE'])
def delete_image(gallery_id):
    """
Delete gallery image
---
tags:
  - Salon Gallery
parameters:
  - name: gallery_id
    in: path
    required: true
    type: integer
responses:
  200:
    description: Image deleted successfully
  404:
    description: Image not found
  500:
    description: Failed to delete image
"""
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT image_url, salon_id, is_primary
            FROM salon_gallery
            WHERE gallery_id = %s
        """, (gallery_id,))
        row = cursor.fetchone()

        if not row:
            cursor.close()
            return jsonify({'error': 'Image not found'}), 404

        image_url = row[0]
        salon_id = row[1]
        is_primary = row[2]

        if image_url:
            S3Uploader.delete_image_from_s3(image_url)

        cursor.execute("""
            DELETE FROM salon_gallery
            WHERE gallery_id = %s
        """, (gallery_id,))
        mysql.connection.commit()
        
        if is_primary:
            cursor.execute("""
                UPDATE salon_gallery
                SET is_primary = FALSE
                WHERE salon_id = %s
            """, (salon_id,))
            mysql.connection.commit()

        cursor.close()

        return jsonify({
            'message': 'Image deleted successfully',
            'gallery_id': gallery_id
        }), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': f'Failed to delete image: {str(e)}'}), 500
