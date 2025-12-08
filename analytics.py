from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
from start_time import SERVER_START_TIME

analytics_bp = Blueprint('analytics', __name__)

#FOR ADMINS 
#tracking errors
@analytics_bp.route('/admin/errors', methods=['GET'])
def admin_get_errors():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    limit = request.args.get('limit', 100)
    offset = request.args.get('offset', 0)

    query = """
        select error_id, message, details, endpoint, method, payload, user_id, created_at
        from error_logs
        order by created_at desc
        limit %s offset %s
    """
    cursor.execute(query, (limit, offset))
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

#tracking uptime
@analytics_bp.route('/admin/uptime', methods=['GET'])
def get_uptime():
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - SERVER_START_TIME).total_seconds()
    
    return jsonify({
        "uptime_seconds": uptime_seconds,
        "uptime_hours": round(uptime_seconds / 3600, 2),
        "status": "OK"
    })

# top 5 highest earning services
@analytics_bp.route('/admin/top-earning-services', methods=['GET'])
def admin_top_earning_services():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    query = """
        select salons.salon_id, salons.name, services.service_id, services.name,
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
    cursor = mysql.connection.cursor()

    query = """
        select salons.salon_id, salons.name, products.product_id, products.name,
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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

    query = "select count(*) as total_users from users"
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# total count of all salons
@analytics_bp.route('/admin/total-salons', methods=['GET'])
def admin_total_salons():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    query = "select count(*) as total_salons from salons"
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# total count of all genders
@analytics_bp.route('/admin/gender-distribution', methods=['GET'])
def admin_gender_distribution():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

    query = "select sum(points_redeemed) as total_points_redeemed from customer_points"

    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

# total vouchers redeemed platform wide
@analytics_bp.route('/admin/vouchers-redeemed', methods=['GET'])
def admin_vouchers_redeemed():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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

#generate a general report 
@analytics_bp.route('/admin/report-summary', methods=['GET'])
def admin_report_summary():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(dictionary=True)

    query = """
        select 
            (select count(*) from users) as total_users,
            (select count(*) from salons) as total_salons,
            (select sum(total_amount) from invoices) as total_revenue,
            (select count(*) from appointments) as total_appointments,
            (select sum(points_redeemed) from customer_points) as total_points_redeemed
    """
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return jsonify(result)

#FOR SALON OWNERS
# get salon's total appointments 
@analytics_bp.route('/salon/<int:salon_id>/total-appointments', methods=['GET'])
def salon_total_appointments(salon_id):
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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
    cursor = mysql.connection.cursor()

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

