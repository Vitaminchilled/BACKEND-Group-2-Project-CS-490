from flask import Flask
from flask_mysqldb import MySQL
from flask_cors import CORS
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from flasgger import Swagger
from datetime import datetime, timedelta
from utils.emails import send_email

app = Flask(__name__)
CORS(app)

app.secret_key = 'G76D-U89V-576V-7BT6'

app.config.update(
    MYSQL_HOST='localhost',
    MYSQL_USER='root',
    MYSQL_PASSWORD='5283',
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
from users import users_bp
from analytics import analytics_bp

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
app.register_blueprint(users_bp)
app.register_blueprint(analytics_bp)

scheduled_appointments = set()
#send customer's email updates for appointments 24 hours before the appointment 
def send_appointment_reminder():
    with app.app_context():
        mysql = app.config['MYSQL']
        cursor = mysql.connection.cursor()

        now = datetime.now()
        reminder_time = now + timedelta(hours=24)
        reminder_window_end = reminder_time + timedelta(hours=8)

        query = """
            select users.email, appointments.appointment_date, appointments.start_time, salons.name as salon_name, appointments.appointment_id
            from appointments
            join users on appointments.customer_id = users.user_id
            join salons on appointments.salon_id = salons.salon_id
            where appointments.appointment_date = %s
        """
        cursor.execute(query, (reminder_time.date(),))
        appointments = cursor.fetchall()
        cursor.close()

        for email, appointment_date, appointment_time, salon_name, appointment_id in appointments:
            appt_datetime = datetime.combine(appointment_date, appointment_time)
            if reminder_time <= appt_datetime <= reminder_window_end:
                if appointment_id in scheduled_appointments:
                    continue

                subject = f"Reminder: Appointment at {salon_name}"
                body = (
                    f"Dear Customer,\n\n"
                    f"This is a reminder for your appointment at {salon_name} "
                    f"on {appointment_date} at {appointment_time}.\n\nThank you!"
                )
                send_email(email, subject, body)

                scheduled_appointments.add(appointment_id)
        
scheduler = BackgroundScheduler()
scheduler.add_job(send_appointment_reminder, 'interval', hours=8)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=True)
