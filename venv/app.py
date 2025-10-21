from flask import Flask
from flask_mysqldb import MySQL
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.secret_key = 'G76D-U89V-576V-7BT6'

app.config.update(
    MYSQL_HOST='localhost',
    MYSQL_USER='root',
    MYSQL_PASSWORD='5283',
    MYSQL_DB='salon'
)

mysql = MySQL(app)
app.config['MYSQL'] = mysql

from login import login_bp
from register import register_bp

app.register_blueprint(login_bp)
app.register_blueprint(register_bp)

@app.route('/')
def home():
    return "it works!"

if __name__ == '__main__':
    app.run(debug=True)
