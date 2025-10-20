from flask import request, jsonify
from app import app, mysql

@app.route('salon/services/add', methods=['POST'])
def add_service():

@app.route('salon/services/edit/<int:service_id>', methods=['PUT'])
def edit_service(service_id):

@app.route('salon/services/delete/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):

@app.route('salon/services/loyalty', methods=['POST'])
def service_loyalty():
