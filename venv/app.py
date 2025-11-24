from flask import Flask
from flask_mysqldb import MySQL
from flask_cors import CORS
from flask_mail import Mail
from flask_mail import Message
from flasgger import Swagger

app = Flask(__name__)
CORS(app)

app.secret_key = 'G76D-U89V-576V-7BT6'

app.config.update(
    MYSQL_HOST='localhost',
    MYSQL_USER='root',
    MYSQL_PASSWORD='1111',
    MYSQL_DB='salon'
)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = "wearevanity.co@gmail.com"
app.config['MAIL_PASSWORD'] = "xsqlypwrnixgxrct"
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mysql = MySQL(app)
mail = Mail(app)
app.config['MYSQL'] = mysql

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Vanity API",
        "description": "API documentation for salon management backend",
        "version": "1.0"
    },
    "basePath": "/"
}

Swagger(app, template=swagger_template) 


from login import login_bp
from register import register_bp
from services import services_bp
from tags import tags_bp
from employees import employees_bp
from salon import salon_bp
from appointments import appointments_bp
from loyalty import loyalty_bp
from promotions import promotions_bp
from admin import admin_bp
from reviews import reviews_bp
from payment import payment_bp
from salon_gallery import salon_gallery_bp
from cart import cart_bp
from products import products_bp
from user_dashboard import user_dashboard_bp

app.register_blueprint(login_bp)
app.register_blueprint(register_bp)
app.register_blueprint(services_bp)
app.register_blueprint(tags_bp)
app.register_blueprint(employees_bp)
app.register_blueprint(salon_bp)
app.register_blueprint(appointments_bp)
app.register_blueprint(loyalty_bp)
app.register_blueprint(promotions_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(salon_gallery_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(products_bp)
app.register_blueprint(user_dashboard_bp)

@app.route('/')
def home():
    return "it works!"

@app.route("/email")
def email():
    from emails import send_email
    try:
        send_email(
            to="alexiades.v@gmail.com",
            subject="Test Email",
            body="This is a test from Flask-Mail."
        )
        return "Email sent successfully!"
    except Exception as e:
        return f"Email failed: {e}"

if __name__ == '__main__':
    app.run(debug=True)
