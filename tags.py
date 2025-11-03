from flask import Blueprint, jsonify, current_app

tags_bp = Blueprint('tags', __name__)

@tags_bp.route('/master-tags', methods=['GET'])
def get_master_tags():
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select master_tag_id, name
            from master_tags
            order by master_tag_id
        """
        cursor.execute(query)
        master_tags = cursor.fetchall()
        cursor.close()
        return jsonify({
            'master_tags': [{
                "master_tag_id": master_tag[0],
                "name": master_tag[1]
            }for master_tag in master_tags]
        }), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch master tags', 'details': str(e)}), 500
    
@tags_bp.route('/tags/<int:master_tag_id>', methods=['GET'])
def get_tags(master_tag_id):
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        query = """
            select tag_id, name
            from tags 
            where master_tag_id = %s
            order by tag_id
        """
        cursor.execute(query, (master_tag_id,))
        tags = cursor.fetchall()
        cursor.close()
        return jsonify({'tags': tags}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch tags', 'details': str(e)}), 500