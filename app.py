from flask import Flask, request, jsonify, session
from flask_mysqldb import MySQL
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.secret_key = 'G76D-U89V-576V-7BT6'

app.config.update(
    MYSQL_HOST='localhost',
    MYSQL_USER='root',
    MYSQL_PASSWORD='Luca15',
    MYSQL_DB='salon'
)

mysql = MySQL(app)
app.config['MYSQL'] = mysql

from login import login_bp
from register import register_bp
from services import services_bp
from tags import tags_bp
from salons import salons_bp #lizeth
from salon import salon_bp #ben
from employees import employees_bp
from appointments import appointments_bp
from reviews import reviews_bp


app.register_blueprint(appointments_bp)
app.register_blueprint(login_bp)
app.register_blueprint(register_bp)
app.register_blueprint(services_bp)
app.register_blueprint(tags_bp)
app.register_blueprint(salons_bp) #lizeth salons
app.register_blueprint(salon_bp) #ben salons
app.register_blueprint(employees_bp)
app.register_blueprint(reviews_bp)

@app.route('/')
def home():
    return "it works!"

if __name__ == '__main__':
    app.run(debug=True)
