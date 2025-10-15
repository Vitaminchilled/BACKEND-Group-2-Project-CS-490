from flask import Flask, jsonify, request
from flask_mysqldb import MySQL
from flask_cors import CORS

app = Flask(__name__)
CORS(app) 

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root' 
app.config['MYSQL_PASSWORD'] = '5283' #put your own mysql password here
app.config['MYSQL_DB'] = 'salon' #put your own database name here
mysql = MySQL(app)

@app.route('/')
def home():
    return "its working!"

@app.route('/users')
def top_films():
    cursor = mysql.connection.cursor()
    query = """
        select * from users
    """
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
