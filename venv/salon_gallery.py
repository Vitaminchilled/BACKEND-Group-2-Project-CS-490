import os
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
#all the photos will be gathered from google or online image hosting site

salon_gallery_bp = Blueprint('salon_gallery', __name__)

#get salon pictures
@salon_gallery_bp.route('/salon/<int:salon_id>/gallery', methods=['GET'])
def get_gallery(salon_id):
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
        cursor.close()
        return jsonify({'error': 'The salon galley could not be displayed'}), 500

#get salon's primary picture
@salon_gallery_bp.route('/salon/<int:salon_id>/image', methods=['GET'])
def get_salon_image(salon_id):
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
        cursor.close()
        return jsonify({'error': 'No profile picture to be displayed'}), 500

#get emloyees pictures
@salon_gallery_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>/image', methods=['GET'])
def get_employee_image(salon_id, employee_id):
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
        cursor.close()
        return jsonify({'error': 'No employee photo to be displayed'}), 500
    
#get service thumbnails
@salon_gallery_bp.route('/salon/<int:salon_id>/services/<int:service_id>/image', methods=['GET'])
def get_service_image(salon_id, service_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select gallery_id, salon_id, service_id, image_url, created_at, last_modified
            from salon_gallery
            where salon_id = %s and service_id = %s
        """
        cursor.execute(query, (salon_id, service_id))
        image = cursor.fetchone()
        cursor.close()

        return jsonify({
            'gallery_id': image[0],
            'salon_id': image[1],
            'service_id': image[2],
            'image_url': image[3],
            'created_at': image[4].strftime('%Y-%m-%d %H:%M:%S') if image[4] else None,
            'last_modified': image[5].strftime('%Y-%m-%d %H:%M:%S') if image[5] else None
        }), 200
    except Exception as e:
        cursor.close()
        return jsonify({'error': 'No service photo to be displayed'}), 500
    
@salon_gallery_bp.route('/salon/<int:salon_id>/gallery/upload', methods=['POST'])
def upload_image(salon_id):
    data = request.json
    image_url = data.get('image_url')
    description = data.get('description', '')
    employee_id = data.get('employee_id', None)  # For employee profile pictures
    service_id = data.get('service_id', None)    # For service thumbnails
    is_primary = data.get('is_primary', False) # For salon profile pictures

    if not image_url:
        return jsonify({'error': 'image_url is required'}), 400
    
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        if employee_id:
            query = """
                select employee_id 
                from employees
                where employee_id = %s and salon_id = %s
            """
            cursor.execute(query, (employee_id, salon_id))
            if not cursor.fetchone():
                cursor.close()
                return jsonify({'error': f'Employee {employee_id} does not belong to salon {salon_id}'}), 400
            
        if service_id:
            query = """
                select service_id
                from services
                where service_id = %s and salon_id = %s
            """
            cursor.execute(query, (service_id, salon_id))
        if not cursor.fetchone():
            cursor.close()
            return jsonify({'error': f'Service {service_id} does not belong to salon {salon_id}'}), 400
            
        #remove the previous profile photo
        if is_primary and not employee_id and not service_id:
            query = """
                update salon_gallery
                set is_primary = false 
                where salon_id = %s and is_primary = true
            """
            cursor.execute(query, (salon_id,))

        query = """
            insert into salon_gallery(salon_id, image_url, description, employee_id, service_id, is_primary)
            values(%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (salon_id, image_url, description, employee_id, service_id, is_primary))
        mysql.connection.commit()
        gallery_id = cursor.lastrowid
        cursor.close()
        return jsonify({
            'message': 'Image added successfully',
            'gallery_id': gallery_id,
            'image_url': image_url
        }), 201
    except Exception as e:
        return jsonify({'error': f'Failed to upload image: {str(e)}'}), 500

@salon_gallery_bp.route('/salon/gallery/<int:gallery_id>/update', methods=['PUT'])
def update_image(gallery_id):
    pass

@salon_gallery_bp.route('/salon/gallery/<int:gallery_id>/delete', methods=['DELETE'])
def delete_image(gallery_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select gallery_id, is_primary
            from salon_gallery 
            where gallery_id = %s
        """
        cursor.execute(query, (gallery_id,))
        image = cursor.fetchone()
        if not image:
            cursor.close()
            return jsonify({'error': 'Image not found'}), 404
        
        query = """
            delete from salon_gallery
            where gallery_id = %s
        """
        cursor.execute(query, (gallery_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Image deleted successfully', 'gallery_id': gallery_id}), 200

    except Exception as e:
        return jsonify({'error': f'Failed to delete image: {str(e)}'}), 500