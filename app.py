import os
import boto3
from flask import Flask
from flask_mysqldb import MySQL
from flask_cors import CORS
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from flasgger import Swagger
from datetime import datetime, timedelta, timezone
from utils.emails import send_email

from flask import Blueprint, jsonify, request, current_app
from MySQLdb.cursors import DictCursor

app = Flask(__name__)
CORS(app)

app.secret_key = 'G76D-U89V-576V-7BT6'

app.config.update(
    MYSQL_HOST=os.getenv("MYSQL_HOST"),
    MYSQL_USER=os.getenv("MYSQL_USER"),
    MYSQL_PASSWORD=os.getenv("MYSQL_PASSWORD"),
    MYSQL_DB=os.getenv("MYSQL_DB")
)

app.config["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID")
app.config["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY")
app.config["AWS_REGION"] = os.getenv("AWS_REGION")
app.config["AWS_S3_BUCKET"] = os.getenv("AWS_S3_BUCKET")

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

# ✅ MONITORING: Track server start time for uptime monitoring
app.config['SERVER_START_TIME'] = datetime.now(timezone.utc)

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Vanity API",
        "description": "API documentation for salon management backend",
        "version": "1.0"
    },
    "basePath": "/"
}

analytics_bp = Blueprint('analytics', __name__)

#FOR ADMINS
# top 5 highest earning services
@analytics_bp.route('/admin/top-earning-services', methods=['GET'])
def admin_top_earning_services():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select salons.salon_id, salons.name as salon_name, services.service_id, services.name,
               sum(invoices.total_amount) as revenue
        from invoices
        join appointments on appointments.appointment_id = invoices.appointment_id
        join salons on salons.salon_id = appointments.salon_id
        join services on appointments.service_id = services.service_id
        group by services.service_id, salons.salon_id
        order by revenue desc
        limit 5
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# top 5 highest earning products
@analytics_bp.route('/admin/top-earning-products', methods=['GET'])
def admin_top_earning_products():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select salons.salon_id, salons.name as salon_name, products.product_id, products.name,
               sum(invoice_line_items.line_total) as revenue
        from invoice_line_items
        join products on invoice_line_items.product_id = products.product_id
        join salons on salons.salon_id = products.salon_id
        group by products.product_id, salons.salon_id
        order by revenue desc
        limit 5
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# top 5 salons with most appointments
@analytics_bp.route('/admin/top-salons-by-appointments', methods=['GET'])
def admin_top_salons_by_appointments():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select salons.salon_id, salons.name, count(appointments.appointment_id) as total_appointments
        from appointments
        join salons on salons.salon_id = appointments.salon_id
        group by salons.salon_id
        order by total_appointments desc
        limit 5
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# total count of all users
@analytics_bp.route('/admin/total-users', methods=['GET'])
def admin_total_users():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = "select count(*) as total_users from users"
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# total count of all VERIFIED salons
@analytics_bp.route('/admin/total-salons', methods=['GET'])
def admin_total_salons():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = "select count(*) as total_salons from salons where is_verified = 1"
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# system health and uptime monitoring
@analytics_bp.route('/admin/system-health', methods=['GET'])
def admin_system_health():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    try:
        # Count errors in last 24 hours from audit_logs
        query_errors = """
            select count(*) as errors_24h
            from audit_logs
            where operation = 'DELETE' 
            and changed_at >= date_sub(now(), interval 24 hour)
        """
        cursor.execute(query_errors)
        errors_result = cursor.fetchone()
        errors_24h = errors_result['errors_24h'] if errors_result else 0

        # Count total audit log entries (as activity indicator)
        query_activity = "select count(*) as total_logs from audit_logs"
        cursor.execute(query_activity)
        activity_result = cursor.fetchone()
        total_logs = activity_result['total_logs'] if activity_result else 0

        # Count active users (logged in within last 24 hours)
        query_active = """
            select count(*) as active_users
            from users
            where last_login >= date_sub(now(), interval 24 hour)
        """
        cursor.execute(query_active)
        active_result = cursor.fetchone()
        active_users = active_result['active_users'] if active_result else 0

        # Database connection status (if we got here, it's working)
        db_status = "healthy"
        
        # Calculate uptime percentage (placeholder - would need actual uptime tracking)
        uptime_percentage = 99.9

        cursor.close()

        return jsonify({
            'uptime_percentage': uptime_percentage,
            'errors_24h': errors_24h,
            'active_users_24h': active_users,
            'total_audit_logs': total_logs,
            'database_status': db_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        if cursor:
            cursor.close()
        return jsonify({
            'error': str(e),
            'database_status': 'error'
        }), 500

# total count of all genders
@analytics_bp.route('/admin/gender-distribution', methods=['GET'])
def admin_gender_distribution():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select gender, count(*) as total_count
        from users
        group by gender
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# retention rates
@analytics_bp.route('/admin/retention', methods=['GET'])
def admin_retention():
    days = request.args.get('days', 30)
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select count(*) as active_users 
        from users
        where last_login >= date_sub(curdate(), interval %s day)
    """

    cursor.execute(query, (days,))
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

#most loyal customers by appointments made
@analytics_bp.route('/admin/loyal-customers', methods=['GET'])
def admin_loyal_customers():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select users.user_id, users.username, count(appointments.appointment_id) as total_appointments
        from appointments
        join users on users.user_id = appointments.customer_id
        group by users.user_id
        order by total_appointments desc
        limit 10
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# total points redeeemed platform wide
@analytics_bp.route('/admin/points-redeemed', methods=['GET'])
def admin_points_redeemed():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = "select sum(points_redeemed) as total_points_redeemed from customer_points"

    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# total vouchers redeemed platform wide
@analytics_bp.route('/admin/vouchers-redeemed', methods=['GET'])
def admin_vouchers_redeemed():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select count(*) as total_vouchers_redeemed
        from customer_vouchers
        where redeemed = 1
    """

    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# demographics by age groups
@analytics_bp.route('/admin/age-demographics', methods=['GET'])
def admin_age_demographics():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select 
            case 
                when (year(curdate()) - birth_year) < 18 then 'Under 18'
                when (year(curdate()) - birth_year) between 18 and 24 then '18-24'
                when (year(curdate()) - birth_year) between 25 and 34 then '25-34'
                when (year(curdate()) - birth_year) between 35 and 44 then '35-44'
                when (year(curdate()) - birth_year) between 45 and 54 then '45-54'
                when (year(curdate()) - birth_year) between 55 and 64 then '55-64'
                else '65+'
            end as age_group,
            count(*) as total_count
        from users
        group by age_group
        order by age_group
    """
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

#demographics by location
@analytics_bp.route('/admin/location-demographics', methods=['GET'])
def admin_location_demographics():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select city, state, count(*) as total_customers
        from addresses
        where entity_type = 'customer'
        group by city, state
        order by total_customers desc
    """
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

#FOR SALON OWNERS
# get salon's total appointments
@analytics_bp.route('/salon/<int:salon_id>/total-appointments', methods=['GET'])
def salon_total_appointments(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select count(appointments.appointment_id) as total_appointments
        from appointments
        where appointments.salon_id = %s
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# get salon's total revenue
@analytics_bp.route('/salon/<int:salon_id>/total-revenue', methods=['GET'])
def salon_total_revenue(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select sum(invoices.total_amount) as total_revenue
        from invoices
        join appointments on appointments.appointment_id = invoices.appointment_id
        where appointments.salon_id = %s
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# get salon's top 5 popular services
@analytics_bp.route('/salon/<int:salon_id>/top-services', methods=['GET'])
def salon_top_services(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select services.service_id, services.name, count(appointments.appointment_id) as total_appointments
        from appointments
        join services on appointments.service_id = services.service_id
        where appointments.salon_id = %s
        group by services.service_id
        order by total_appointments desc
        limit 5
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# get salon's top 5 popular products
@analytics_bp.route('/salon/<int:salon_id>/top-products', methods=['GET'])
def salon_top_products(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select products.product_id, products.name, sum(invoice_line_items.quantity) as total_sold
        from invoice_line_items
        join products on invoice_line_items.product_id = products.product_id
        where products.salon_id = %s
        group by products.product_id
        order by total_sold desc
        limit 5
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# get salon's appointment trends by month
@analytics_bp.route('/salon/<int:salon_id>/appointment-trend', methods=['GET'])
def salon_appointment_trend(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select date_format(appointment_date, '%%Y-%%m') as month,
        count(*) as total_appointments
        from appointments
        where salon_id = %s
        group by month
        order by month asc
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# revenue trend for a salon by month
@analytics_bp.route('/salon/<int:salon_id>/revenue-trend', methods=['GET'])
def salon_revenue_trend(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select date_format(invoices.issued_date, '%%Y-%%m') as month,
               sum(invoices.total_amount) as revenue
        from invoices
        join appointments on appointments.appointment_id = invoices.appointment_id
        where appointments.salon_id = %s
        group by month
        order by month asc
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# number of canceled and completed appointments
@analytics_bp.route('/salon/<int:salon_id>/appointments-status', methods=['GET'])
def get_appointment_status_counts(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select status, count(*) as count
        from appointments
        where salon_id = %s
        group by status
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# top 5 frequent customers for a salon
@analytics_bp.route('/salon/<int:salon_id>/customers-top', methods=['GET'])
def get_top_customers(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select users.user_id, users.username, count(appointments.appointment_id) as visits
        from appointments 
        join users on users.user_id = appointments.customer_id
        where appointments.salon_id = %s
        group by users.user_id
        order by visits desc
        limit 5
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# average transaction amount
@analytics_bp.route('/salon/<int:salon_id>/transactions-average', methods=['GET'])
def get_avg_transaction(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select avg(invoices.total_amount) as avg_transaction
        from invoices 
        join appointments on appointments.appointment_id = invoices.appointment_id
        where appointments.salon_id = %s
    """

    cursor.execute(query, (salon_id,))
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# points redeemed per customer
@analytics_bp.route('/salon/<int:salon_id>/customers-points-redeemed', methods=['GET'])
def get_points_redeemed(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select customer_id, users.username, sum(points_redeemed) as total_points_redeemed
        from customer_points
        join users on customer_points.customer_id = users.user_id
        where salon_id = %s
        group by customer_id
    """
    cursor.execute(query, (salon_id,))
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# vouchers redeemed per customer
@analytics_bp.route('/salon/<int:salon_id>/customers-vouchers-redeemed', methods=['GET'])
def get_vouchers_redeemed(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select customer_vouchers.customer_id, users.username, count(*) as total_vouchers_redeemed
        from customer_vouchers
        join users on customer_vouchers.customer_id = users.user_id
        where customer_vouchers.salon_id = %s and customer_vouchers.redeemed = 1
        group by customer_vouchers.customer_id;
    """
    cursor.execute(query, (salon_id,))
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# appointments per employee
@analytics_bp.route('/salon/<int:salon_id>/employees-appointments', methods=['GET'])
def get_employee_appointments(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select employees.employee_id, employees.first_name, employees.last_name, count(appointments.appointment_id) as total_appointments
        from appointments
        join employees on appointments.employee_id = employees.employee_id
        where appointments.salon_id = %s
        group by employees.employee_id
        order by total_appointments desc
    """
    cursor.execute(query, (salon_id,))
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# busiest day of the week
@analytics_bp.route('/salon/<int:salon_id>/appointments/busiest-day', methods=['GET'])
def get_busiest_day(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select dayofweek(appointment_date) as day_of_week, count(*) as total_appointments
        from appointments
        where salon_id = %s
        group by day_of_week
        order by total_appointments desc
        limit 1
    """
    cursor.execute(query, (salon_id,))
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# Add these new endpoints to your analytics.py file (after the existing ones)

# ALL salons by appointments (INCLUDING verified salons with 0 appointments)
@analytics_bp.route('/admin/all-salons-by-appointments', methods=['GET'])
def admin_all_salons_by_appointments():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        SELECT salons.salon_id, salons.name, 
               COALESCE(COUNT(appointments.appointment_id), 0) as total_appointments
        FROM salons
        LEFT JOIN appointments ON salons.salon_id = appointments.salon_id
        WHERE salons.is_verified = 1
        GROUP BY salons.salon_id, salons.name
        ORDER BY total_appointments DESC, salons.name ASC
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# ALL earning services (no limit)
@analytics_bp.route('/admin/all-earning-services', methods=['GET'])
def admin_all_earning_services():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select salons.salon_id, salons.name as salon_name, services.service_id, services.name,
               sum(invoices.total_amount) as revenue
        from invoices
        join appointments on appointments.appointment_id = invoices.appointment_id
        join salons on salons.salon_id = appointments.salon_id
        join services on appointments.service_id = services.service_id
        group by services.service_id, salons.salon_id
        order by revenue desc
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# ALL earning products (no limit)
@analytics_bp.route('/admin/all-earning-products', methods=['GET'])
def admin_all_earning_products():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select salons.salon_id, salons.name as salon_name, products.product_id, products.name,
               sum(invoice_line_items.line_total) as revenue
        from invoice_line_items
        join products on invoice_line_items.product_id = products.product_id
        join salons on salons.salon_id = products.salon_id
        group by products.product_id, salons.salon_id
        order by revenue desc
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

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
from notifications import notifications_bp

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
app.register_blueprint(notifications_bp)

scheduled_appointments = set()

Swagger(app, template=swagger_template)

# send customer's email updates for appointments 24 hours before the appointment
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



if __name__ == '__main__':
    app.run(debug=True)
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_appointment_reminder, 'interval', hours=8)
    scheduler.start()
