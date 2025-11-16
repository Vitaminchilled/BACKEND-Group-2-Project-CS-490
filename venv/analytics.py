from flask import Blueprint, jsonify, request, current_app

analytics_bp = Blueprint('analytics', __name__)

#FOR ADMINS 
# top 5 highest earning services
query = """
    select salons.salon_id, salons.name, services.service_id, services.name, sum(invoices.total_amount) as revenue
    from invoices
    join appointments on appointments.appointment_id = invoices.appointment_id
    join salons on salons.salon_id = appointments.salon_id
    join services on appointments.service_id = services.service_id
    group by services.service_id, salons.salon_id
    order by revenue desc
    limit 5
"""

# top 5 highest earning products
query = """
    select salons.salon_id, salons.name, products.product_id, products.name, sum(invoice_line_items.line_total) as revenue
    from invoice_line_items
    join products on invoice_line_items.product_id = products.product_id
    join salons on salons.salon_id = products.salon_id
    group by products.product_id, salons.salon_id
    order by revenue desc
    limit 5
"""

# top 5 salons with most appointments
query = """
    select salons.salon_id, salons.name, count(appointments.appointment_id) as total_appointments
    from appointments
    join salons on salons.salon_id = appointments.salon_id
    group by salons.salon_id
    order by total_appointments desc
    limit 5
"""

# total count of all users
query = "select count(*) as total_users from users";


# total count of all salons
query = "select count(*) as total_salons from salons";

# total count of all genders
query = """
    select gender, count(*) as total_count
    from users
    group by gender
"""

# retention rates
query = """
    select count(*) as active_users 
    from users
    where last_login >= date_sub(curdate(), interval  %s day)
"""

#most loyal customers by appointments made
query = """
    select users.user_id, users.username, count(appointments.appointment_id) as total_appointments
    from appointments
    join users on users.user_id = appointments.customer_id
    group by users.user_id
    order by total_appointments desc
    limit 10
"""

# total points redeeemed platform wide
query = """
    select sum(points_redeemed) as total_points_redeemed
    from customer_points
"""

# total vouchers redeemed platform wide
query = """
    select count(*) as total_vouchers_redeemed
    from vouchers
    where redeemed = 1
"""

# demographics by age groups


#FOR SALON OWNERS
# get salon's total appointments 
query = """
    select salons.salon_id, salons.name, count(appointments.appointment_id) as total_appointments
    from appointments
    join salons on salons.salon_id = appointments.salon_id
    where salons.salon_id = %s
"""

# get salon's total revenue
query = """
    select salons.salon_id, salons.name, sum(invoices.total_amount) as total_revenue
    from invoices
    join appointments on appointments.appointment_id = invoices.appointment_id
    join salons on salons.salon_id = appointments.salon_id
    where salons.salon_id = %s
"""

# get salon's top 5 popular services
query = """
    select services.service_id, services.name, count(appointments.appointment_id) as total_appointments
    from appointments   
    join services on appointments.service_id = services.service_id
    where appointments.salon_id = %s
    group by services.service_id
    order by total_appointments desc
    limit 5
"""

# get salon's top 5 popular products 
query = """
    select products.product_id, products.name, sum(invoice_line_items.quantity) as total_sold
    from invoice_line_items
    join products on invoice_line_items.product_id = products.product_id
    where products.salon_id = %s
    group by products.product_id
    order by total_sold desc
    limit 5
"""

# get salon's appointment trends by month
query = """
    select date_format(appointment_date, '%Y-%m') as month,
        count(*) as total_appointments
    from appointments
    where salon_id = %s
    group by month
    order by month asc
"""

# revenue trend for a salon by month
query = """
    select date_format(invoices.issued_date, '%Y-%m') as month,
        sum(invoices.total_amount) as revenue
    from invoices
    join appointments on appointments.appointment_id = invoices.appointment_id
    where appointments.salon_id = %s
    group by month
    order by month asc
"""

# number of canceled and completed appointments
query = """
    select status, count(*) as count
    from appointments
    where salon_id = %s
    group by status
"""

# top 5 frequent customers for a salon
query = """
    select users.user_id, users.username, count(appointments.appointment_id) as visits
    from appointments 
    join users on users.user_id = appointments.customer_id
    where appointments.salon_id = %s
    group by users.user_id
    order by visits desc
    limit 5
"""

# average transaction amount
query = """
    select avg(invoices.total_amount) as avg_transaction
    from invoices 
    join appointments on appointments.appointment_id = invoices.appointment_id
    where appointments.salon_id = %s
"""

# points redeemed per customer
query = """
    select customer_id, users.username, sum(points_redeemed) as total_points_redeemed
    from customer_points
    join users on customer_points.customer_id = users.user_id
    where salon_id = 1
    group by customer_id
"""

# vouchers redeemed per customer
query = """
    select customer_vouchers.customer_id, users.username, count(*) as total_vouchers_redeemed
    from customer_vouchers
    join users on customer_vouchers.customer_id = users.user_id
    where customer_vouchers.salon_id = %s and customer_vouchers.redeemed = 1
    group by customer_vouchers.customer_id;
"""

# appointments per employee
query = """
    select employees.employee_id, employees.first_name, employees.last_name, count(appointments.appointment_id) as total_appointments
    from appointments
    join employees on appointments.employee_id = employees.employee_id
    where appointments.salon_id = %s
    group by employees.employee_id
    order by total_appointments desc
"""

# busiest day of the week
query = """
    select dayofweek(appointment_date) as day_of_week, count(*) as total_appointments
    from appointments
    where salon_id = %s
    group by day_of_week
    order by total_appointments desc
    limit 1
"""

