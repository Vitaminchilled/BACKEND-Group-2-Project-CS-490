from flask import Flask
from flask_mysqldb import MySQL
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.secret_key = 'G76D-U89V-576V-7BT6'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '5283'
app.config['MYSQL_DB'] = 'salon'

mysql = MySQL(app)

#routes
import login
import register
import services

@app.route('/')
def home():
    return "it works!"

if __name__ == '__main__':
    app.run(debug=True)
