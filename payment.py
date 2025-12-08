import random
import string
from flask import Blueprint, request, jsonify, current_app, session
from datetime import datetime
from utils.logerror import log_error

payment_bp = Blueprint('payment', __name__)

def validate_card(card_number, exp_month, exp_year, cvv):
    card_number = str(card_number)
    cvv = str(cvv)
    if not card_number.isdigit():
        return False, "Card number must be numeric"
    if not cvv.isdigit():
        return False, "cvv must be numeric"
    
    if card_number.startswith('4'):
        card_type = 'visa'
    elif card_number.startswith(('5', '2')):
        card_type = 'mastercard'
    elif card_number.startswith(('34', '37')):
        card_type = 'amex'
    elif card_number.startswith('6'):
        card_type = 'discover'
    else:
        return False, "Unsupported card type"

    if card_type in ('visa', 'mastercard', 'discover'):
        if len(card_number) != 16:
            return False, "Invalid card length"
    else:
        if len(card_number) != 15:
            return False, "Invalid card length"
        
    if card_type in ('visa', 'mastercard', 'discover'):
        if len(cvv) != 3:
            return False, "Invalid cvv"
    else:
        if len(cvv) != 4:
            return False, "Invalid cvv"        

    if exp_month < 1 or exp_month > 12:
        return False, "Invalid month"
    
    now = datetime.now()
    if (exp_year < now.year) or (exp_year == now.year and exp_month < now.month):
        return False, "Card expired"
    
    return True, card_type

def store_card(mysql, customer_id, card_number, exp_month, exp_year, card_type):
    cursor = mysql.connection.cursor()

    query = """
        select wallet_id
        from wallets
        where customer_id = %s and last_four = %s and exp_month = %s and exp_year = %s and card_type = %s
    """
    cursor.execute(query, (customer_id, card_number[-4:], exp_month, exp_year, card_type))
    existing = cursor.fetchone()

    if not existing:
        query = """
            update wallets
            set is_default = false
            where customer_id = %s
        """
        cursor.execute(query, (customer_id,))

        #new card is default
        query = """
            insert into wallets(customer_id, last_four, exp_year, exp_month, card_type, is_default)
            values(%s, %s, %s, %s, %s, true)
        """
        cursor.execute(query, (customer_id, card_number[-4:], exp_year, exp_month, card_type))
        wallet_id = cursor.lastrowid
    else:
        wallet_id = existing[0]
    cursor.close()
    return wallet_id
    
def voucher_redeemable(mysql, loyalty_program_id, service_id):
    if service_id is None:
        return True
    
    cursor = mysql.connection.cursor()
    query = """
        select tag_id
        from entity_tags
        where entity_type = 'loyalty' and entity_id = %s
    """
    cursor.execute(query, (loyalty_program_id,))
    loyalty_tags = {row[0] for row in cursor.fetchall()}

    query = """
        select tag_id
        from entity_tags
        where entity_type = 'service' and entity_id = %s
    """
    cursor.execute(query, (service_id,))
    service_tags = {row[0] for row in cursor.fetchall()}

    return len(loyalty_tags.intersection(service_tags)) > 0

def award_loyalty_points(mysql, customer_id, salon_id, total_amount, default_points_per_dollar=1.0):
    cursor = mysql.connection.cursor()
    #check if existing customer 
    query = """
        select points_id, points_per_dollar
        from customer_points
        where customer_id = %s and salon_id = %s
    """
    cursor.execute(query, (customer_id, salon_id))
    row = cursor.fetchone()

    if row:
        points_id, points_per_dollar = row
        points_per_dollar = float(points_per_dollar)
        points_earned = int(total_amount * points_per_dollar)

        #add points earned to their existing points
        query = """
            update customer_points
            set points_earned = points_earned + %s,
            available_points = available_points + %s,
            last_modified = current_timestamp
            where points_id = %s
        """
        cursor.execute(query, (points_earned, points_earned, points_id))
    else:
        points_earned = int(total_amount * default_points_per_dollar)
        query = """
            insert into customer_points(customer_id, salon_id, points_earned, available_points, points_per_dollar, created_at, last_modified)
            values(%s, %s, %s, %s, %s, current_timestamp, current_timestamp)
        """
        cursor.execute(query, (customer_id, salon_id, points_earned, points_earned, default_points_per_dollar))

    mysql.connection.commit()
    cursor.close()
    return points_earned

@payment_bp.route('/wallets/<int:customer_id>', methods=['GET'])
def list_wallets(customer_id):
    """
    Get saved payment wallets for a customer  
    ---
    tags:
      - Payments
    parameters:
      - name: customer_id
        in: path
        required: true
        description: ID of the customer
        schema:
          type: integer
        responses:
          200:
            description: List of saved wallets returned successfully
          401:
            description: Unauthorized access
          500:
            description: Internal server error
    """
    user_id = session.get('user_id')
    if user_id != customer_id:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()
        
        query = """
            select wallet_id, last_four, exp_month, exp_year, card_type, is_default
            from wallets
            where customer_id = %s
            order by is_default desc, exp_year desc, exp_month desc
        """
        cursor.execute(query, (customer_id,))
        wallets = cursor.fetchall()
        cursor.close()

        if not wallets:
            return jsonify({'message': 'No saved wallets found', 'wallets': []}), 200
        
        result = []
        for wallet in wallets:
            wallet_id, last_four, exp_month, exp_year, card_type, is_default = wallet
            result.append({
                'wallet_id': wallet_id,
                'last_four': last_four,
                'exp_month': exp_month,
                'exp_year': exp_year,
                'card_type': card_type,
                'is_default': bool(is_default)
            })
        return jsonify({'customer_id': customer_id, 'wallets': result}), 200

    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': f'Failed to fetch wallets: {str(e)}'}), 500
    
def apply_discount(mysql, customer_id, salon_id, service_id, subtotal, loyalty_voucher_id=None, promo_code=None):
    cursor = mysql.connection.cursor()
    discount_amount = 0
    if loyalty_voucher_id:
        query = """
            select loyalty_programs.loyalty_program_id, loyalty_programs.discount_value, loyalty_programs.is_percentage
            from customer_vouchers
            join loyalty_programs on loyalty_programs.loyalty_program_id = customer_vouchers.loyalty_program_id
            where customer_vouchers.voucher_id = %s and customer_vouchers.customer_id = %s and customer_vouchers.salon_id = %s and customer_vouchers.redeemed = 0
        """
        cursor.execute(query, (loyalty_voucher_id, customer_id, salon_id))
        voucher = cursor.fetchone()
        
        if not voucher:
            cursor.close()
            return None, "Invalid or already redeemed loyalty voucher"

        loyalty_program_id, discount_value, is_percentage = voucher

        if not voucher_redeemable(mysql, loyalty_program_id, service_id):
            cursor.close()
            return None, "Voucher does not apply to this service"
        
        discount_amount += (subtotal * (discount_value / 100)) if is_percentage else discount_value
        
    if promo_code:
        query = """
            select promo_id, discount_value, is_percentage, start_date, end_date, is_active
            from promotions
            where promo_code = %s and salon_id = %s
        """
        cursor.execute(query, (promo_code, salon_id))
        promo = cursor.fetchone()

        if not promo:
            cursor.close()
            return None, "Invalid promo code"
        
        promo_id, discount_value, is_percentage, start_date, end_date, is_active = promo
        curr_date = datetime.now().date()
        if not is_active or not(start_date <= curr_date <= end_date):
            cursor.close()
            return None, "Promo code expired or inactive"
        
        discount_amount += (subtotal * (discount_value / 100)) if is_percentage else discount_value
    
    cursor.close()
    return max(round(discount_amount, 2), 0), None

def payment_process(card_type, total_amount):
    transaction_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    auth_code = ''.join(random.choices(string.digits, k=6))
    return {
            'status': 'approved',
            'transaction_id': transaction_id,
            'auth_code': auth_code,
            'timestamp': datetime.now().isoformat(),
        }

@payment_bp.route('/appointments/payment', methods=['POST'])
def pay_appointment():
    """
    Process payment for an appointment  
    ---
    tags:
      - Payments
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              appointment_id:
                type: integer
              customer_id:
                type: integer
              service_id:
                type: integer
              wallet_id:
                type: integer
              card_number:
                type: string
              exp_month:
                type: integer
              exp_year:
                type: integer
              cvv:
                type: string
              save_card:
                type: boolean
              promo_code:
                type: string
              loyalty_voucher_id:
                type: integer
            required:
              - appointment_id
              - customer_id
              - service_id
    responses:
      201:
        description: Payment successful
      400:
        description: Invalid request or payment error
      401:
        description: Unauthorized access
      404:
        description: Appointment not found
      500:
        description: Internal server error
    """
    data = request.json
    customer_id = data.get('customer_id')
    user_id = session.get('user_id')
    if user_id != customer_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    appointment_id = data.get('appointment_id')
    service_id = data.get('service_id')
    wallet_id = data.get('wallet_id') #optional
    card_number = data.get('card_number')
    exp_month = data.get('exp_month')
    exp_year = data.get('exp_year')
    cvv = data.get('cvv')
    save_card = data.get('save_card', False)
    promo_code = data.get('promo_code') #optional
    loyalty_voucher_id = data.get('loyalty_voucher_id') #optional 

    if not all([appointment_id, customer_id, service_id]):
        return jsonify({'error': 'Missing required fields'}), 400
    if not card_number and not wallet_id:
        return jsonify({'error': 'Card or wallet required'}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    #make sure appointment exists
    query = """
        select appointments.salon_id, appointments.service_id, services.price, appointments.status
        from appointments
        join services on services.service_id = appointments.service_id
        where appointments.appointment_id = %s
    """
    cursor.execute(query, (appointment_id,))
    appointment = cursor.fetchone()
    if not appointment:
        cursor.close()
        return jsonify({'error': 'Appointment not found'}), 404
    
    salon_id, service_id, subtotal, status = appointment
    if status.lower() in ('paid', 'completed'):
        cursor.close()
        return jsonify({'error': 'This appointment has already been paid for'}), 400
    
    discount_amount, error = apply_discount(mysql, customer_id, salon_id, service_id, subtotal, loyalty_voucher_id, promo_code)
    if error:
        return jsonify({'error': error}), 400

    subtotal = max(round(subtotal - discount_amount, 2), 0)
    subtotal = float(subtotal)
    tax = round(subtotal * 0.08875, 2)
    total = round(subtotal + tax, 2)

    #check if the customer is using a wallet or card 
    if card_number:
        valid, card_type = validate_card(card_number, int(exp_month), int(exp_year), cvv)
        if not valid:
            return jsonify({'error': card_type}), 400
        
        #save card if requested
        if save_card and card_number:
            wallet_id = store_card(mysql, customer_id, card_number, exp_month, exp_year, card_type)
    else:
        query = """
            select last_four, exp_month, exp_year, card_type
            from wallets
            where wallet_id = %s and customer_id = %s
        """
        cursor.execute(query, (wallet_id, customer_id))
        wallet = cursor.fetchone()
        if not wallet:
            cursor.close()
            return jsonify({'error': 'Wallet not found'}), 404
        card_type = wallet[3]
 
    invoice = payment_process(card_type, total)

    if loyalty_voucher_id:
        cursor.execute("update customer_vouchers set redeemed = 1 where voucher_id=%s", (loyalty_voucher_id,))

    try:
        #create the invoice and invoice line items
        query = """
            insert into invoices(appointment_id, customer_id, wallet_id, issued_date, subtotal_amount, tax_amount, total_amount, status)
            values(%s, %s, %s, curdate(), %s, %s, %s, 'paid')
        """
        cursor.execute(query, (appointment_id, customer_id, wallet_id, subtotal, tax, total))
        invoice_id = cursor.lastrowid
        
        query = """
            insert into invoice_line_items(invoice_id, item_type, service_id, quantity, unit_price, description)
            values(%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (invoice_id, 'service', service_id, 1, subtotal, 'Appointment service charge'))

        query = """
            update appointments
            set status = 'paid' 
            where appointment_id = %s
        """
        cursor.execute(query, (appointment_id,))

        points_earned = award_loyalty_points(mysql, customer_id, salon_id, total)

        mysql.connection.commit()
        cursor.close()

        return jsonify({
            'message': 'Payment successful',
            'invoice_id': invoice_id,
            'appointment_id': appointment_id,
            'subtotal': subtotal,
            'tax': tax,
            'total': total,
            'card_type': card_type,
            'points_earned': points_earned,
            'promo_applied': promo_code if discount_amount > 0 else None,
            "voucher_applied": loyalty_voucher_id if loyalty_voucher_id else None,
            'transaction_id': invoice['transaction_id'],
            'auth_code': invoice['auth_code'],
            'timestamp': invoice['timestamp']
        }), 201
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': f'Payment was not processed: {str(e)}'}), 500
    
@payment_bp.route('/cart/payment', methods=['POST'])
def pay_cart():
    """
    Process payment for a customer's cart  
    ---
    tags:
      - Payments
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              customer_id:
                type: integer
              salon_id:
                type: integer
              wallet_id:
                type: integer
              card_number:
                type: string
              exp_month:
                type: integer
              exp_year:
                type: integer
              cvv:
                type: string
              save_card:
                type: boolean
              promo_code:
                type: string
              loyalty_voucher_id:
                type: integer
            required:
              - customer_id
              - salon_id
    responses:
      201:
        description: Cart payment completed
      400:
        description: Payment or validation error
      401:
        description: Unauthorized access
      404:
        description: Cart not found
      500:
        description: Internal server error
    """
    data = request.json
    customer_id = data.get('customer_id')
    user_id = session.get('user_id')
    if user_id != customer_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    salon_id = data.get('salon_id')
    wallet_id = data.get('wallet_id') #optional
    card_number = data.get('card_number')  
    exp_month = data.get('exp_month')
    exp_year = data.get('exp_year')
    cvv = data.get('cvv')
    save_card = data.get('save_card', False)
    promo_code = data.get('promo_code') #optional
    loyalty_voucher_id = data.get('loyalty_voucher_id') #optional

    if not customer_id or not salon_id:
        return jsonify({'error': 'Missing required fields'}), 400
    if not card_number and not wallet_id:
        return jsonify({'error': 'Card or wallet required'}), 400

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    query = """
        select cart_id
        from carts
        where customer_id = %s and salon_id = %s and status = 'active'
    """
    cursor.execute(query, (customer_id, salon_id))
    cart = cursor.fetchone()
    if not cart:
        cursor.close()
        return jsonify({'error': 'No active cart found'}), 404
    cart_id = cart[0]

    query = """
        select cart_items.product_id, cart_items.quantity, products.price, products.name, products.stock_quantity
        from cart_items
        join products on products.product_id = cart_items.product_id
        where cart_items.cart_id = %s
    """
    cursor.execute(query, (cart_id,))
    items = cursor.fetchall()
    if not items:
        cursor.close()
        return jsonify({'error': 'Cart is empty'}), 400

    if card_number:
        valid, card_type = validate_card(card_number, int(exp_month), int(exp_year), cvv)
        if not valid:
            return jsonify({'error': card_type}), 400
        
        if save_card and card_number:
            wallet_id = store_card(mysql, customer_id, card_number, exp_month, exp_year, card_type)
    else:
        query = """
            select distinct last_four, exp_month, exp_year, card_type
            from wallets
            where wallet_id = %s and customer_id = %s
        """
        cursor.execute(query, (wallet_id, customer_id))
        wallet = cursor.fetchone()
        if not wallet:
            cursor.close()
            return jsonify({'error': 'Wallet not found'}), 404
        card_type = wallet[3]

    subtotal = 0
    for product_id, quantity, price, name, stock in items:
        subtotal += price * quantity

    discount_amount, error = apply_discount(
        mysql,
        customer_id=customer_id,
        salon_id=salon_id,
        service_id=None,
        subtotal=subtotal,
        loyalty_voucher_id=loyalty_voucher_id,
        promo_code=promo_code
    )
    if error:
        return jsonify({'error': error}), 400
        
    subtotal = max(round(subtotal - discount_amount, 2), 0)
    subtotal = float(subtotal)
    tax = round(subtotal * 0.08875, 2)
    total = round(subtotal + tax, 2)

    invoice = payment_process(card_type, total)

    if loyalty_voucher_id:
        cursor.execute("update customer_vouchers set redeemed = 1 where voucher_id = %s", (loyalty_voucher_id,))

    try:
        query = """
            insert into invoices(appointment_id, customer_id, wallet_id, issued_date, subtotal_amount, tax_amount, total_amount, status)
            values(null, %s, %s, curdate(), %s, %s, %s, 'paid')
        """
        cursor.execute(query, (customer_id, wallet_id, subtotal, tax, total))
        invoice_id = cursor.lastrowid

        for product_id, quantity, price, name, stock in items:
            if stock < quantity:
                cursor.close()
                return jsonify({'error': f'Insufficient stock for {name}'}), 400
            query = """
                insert into invoice_line_items(invoice_id, item_type, product_id, service_id, quantity, unit_price, description)
                values (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (invoice_id, 'product', product_id, None, quantity, price, name))

            query = """
                update products
                set stock_quantity = stock_quantity - %s
                where product_id = %s
            """
            cursor.execute(query, (quantity, product_id))

        cursor.execute("update carts set status='completed' where cart_id = %s", (cart_id,))

        points_earned = award_loyalty_points(mysql, customer_id, salon_id, total)

        mysql.connection.commit()
        cursor.close()

        return jsonify({
            'message': 'Cart payment successful',
            'invoice_id': invoice_id,
            'subtotal': subtotal,
            'tax': tax,
            'total': total,
            'card_type': card_type,
            'points_earned': points_earned,
            'promo_applied': promo_code if discount_amount > 0 else None,
            "voucher_applied": loyalty_voucher_id if loyalty_voucher_id else None,
            'transaction_id': invoice['transaction_id'],
            'auth_code': invoice['auth_code'],
            'timestamp': invoice['timestamp']
        }), 201
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': f'Payment was not processed: {str(e)}'}), 500
    
@payment_bp.route('/payments/history/<int:customer_id>', methods=['GET'])
def payment_history(customer_id):
    """
    Fetch full payment history for a customer  
    ---
    tags:
      - Payments
    parameters:
      - name: customer_id
        in: path
        required: true
        description: Customer ID
        schema:
          type: integer
    responses:
      200:
        description: Payment history returned
      401:
        description: Unauthorized access
      404:
        description: No payments found
      500:
        description: Internal server error
    """
    user_id = session.get('user_id')
    if user_id != customer_id:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select invoice_id, appointment_id, issued_date, subtotal_amount, tax_amount, total_amount, status
            from invoices
            where customer_id = %s
            order by issued_date desc
        """
        cursor.execute(query, (customer_id,))
        payments = cursor.fetchall()
        cursor.close()

        if not payments:
            return jsonify({'message': 'No payment history found'}), 404

        result = []
        for payment in payments:
            result.append({
                'invoice_id': payment[0],
                'appointment_id': payment[1],
                'issued_date': payment[2].strftime('%Y-%m-%d'),
                'subtotal': float(payment[3]),
                'tax': float(payment[4]),
                'total': float(payment[5]),
                'status': payment[6]
            })
        return jsonify({'customer_id': customer_id, 'payments': result}), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        return jsonify({'error': f'Error fetching payment history: {str(e)}'}), 500
    
@payment_bp.route('/payments/refund/<int:invoice_id>', methods=['POST'])
def refund_payment(invoice_id):
    """
    Refund a previously paid invoice  
    ---
    tags:
      - Payments
    parameters:
      - name: invoice_id
        in: path
        required: true
        description: Invoice ID to refund
        schema:
          type: integer
    responses:
      200:
        description: Refund successful
      400:
        description: Refund not allowed or already processed
      404:
        description: Invoice not found
      500:
        description: Refund failed
    """
    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        query = """
            select appointment_id, total_amount, status
            from invoices 
            where invoice_id = %s
        """
        cursor.execute(query, (invoice_id,))
        invoice = cursor.fetchone()
        if not invoice:
            cursor.close()
            return jsonify({'error': 'Invoice not found'}), 404
        
        if invoice[2] == 'cancelled':
            cursor.close()
            return jsonify({'error': 'This invoice has already been refunded'}), 400
        
        appointment_id = invoice[0]
        total_amount = float(invoice[1])
        status = invoice[2]

        if status == 'cancelled':
            cursor.close()
            return jsonify({'error': 'This invoice has already been refunded'}), 400

        refund_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        timestamp = datetime.now().isoformat()

        query = """
            update invoices
            set status = 'cancelled', last_modified = %s
            where invoice_id = %s
        """
        cursor.execute(query, (timestamp, invoice_id))

        query = """
            update appointments
            set status = 'cancelled'
            where appointment_id = %s
        """
        cursor.execute(query, (appointment_id,))
        mysql.connection.commit()
        cursor.close()

        return jsonify({
            'message': 'Refund successful',
            'refund_id': refund_id,
            'invoice_id': invoice_id,
            'amount_refunded': total_amount,
            'timestamp': timestamp
        }), 200
    except Exception as e:
        log_error(str(e), session.get("user_id"))
        mysql.connection.rollback()
        return jsonify({'error': f'Refund failed: {str(e)}'}), 500
