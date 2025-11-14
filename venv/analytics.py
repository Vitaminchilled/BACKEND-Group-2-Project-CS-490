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

#FOR SALON OWNERS
# get salon's total appointments 
query = """
    select salons.salon_id, salons.name, count(appointments.appointment_id) as total_appointments
    from appointments
    join salons on salons.salon_id = appointments.salon_id
    where salons.salon_id = %s
"""
