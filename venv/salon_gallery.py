import os
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from werkzeug.utils import secure_filename

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
    pass

@salon_gallery_bp.route('/salon/gallery/<int:gallery_id>/update', methods=['PUT'])
def update_image(gallery_id):
    pass

@salon_gallery_bp.route('/salon/gallery/<int:gallery_id>/delete', methods=['DELETE'])
def delete_image(gallery_id):
    pass