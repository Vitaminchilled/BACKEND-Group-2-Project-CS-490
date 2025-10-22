from flask import Blueprint, request, jsonify, session
from flask import current_app

employees_bp = Blueprint('employees', __name__)

@employees_bp.route('/salon/<int:salon_id>/employees', methods=['GET'])
def get_employees(salon_id):
    pass

@employees_bp.route('/salon/<int:salon_id>/employees', methods=['POST'])
def add_employee(salon_id):
    pass

@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>', methods=['PUT'])
def update_employee(salon_id, employee_id):
    pass

@employees_bp.route('/salon/<int:salon_id>/employees/<int:employee_id>', methods=['DELETE'])
def delete_employee(salon_id, employee_id):
    pass



