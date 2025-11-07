import random
import string
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

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

    now = datetime.now()
    if (exp_year < now.year) or (exp_year == now.year and exp_month < now.month):
        return False, "Card expired"
    
    return True, card_type
    
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
    data = request.json
    appointment_id = data.get('appointment_id')
    customer_id = data.get('customer_id')
    service_id = data.get('service_id')
    wallet_id = data.get('wallet_id') #optional
    subtotal = data.get('subtotal')
    tax = data.get('tax', 0.0)
    card_number = data.get('card_number')
    exp_month = data.get('exp_month')
    exp_year = data.get('exp_year')
    cvv = data.get('cvv')
    save_card = data.get('save_card', False)
    total = round(float(subtotal) + float(tax), 2) 

    if not all([appointment_id, customer_id, service_id]):
        return jsonify({'error': 'Missing required fields'}), 400
    if not card_number and not wallet_id:
        return jsonify({'error': 'Card or wallet required'}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    #make sure appointment exists
    query = """
        select status
        from appointments
        where appointment_id = %s
    """
    cursor.execute(query, (appointment_id,))
    appointment = cursor.fetchone()
    if not appointment:
        cursor.close()
        return jsonify({'error': 'Appointment not found'}), 404
    if appointment[0].lower() in ('paid', 'completed'):
        cursor.close()
        return jsonify({'error': 'This appointment has already been paid for'}), 400
    
    #check if the customer is using a wallet or card 
    if card_number:
        valid, card_type = validate_card(card_number, int(exp_month), int(exp_year), cvv)
        if not valid:
            return jsonify({'error': card_type}), 400
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

        #save card if requested
        if save_card and card_number:
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

        mysql.connection.commit()
        cursor.close()

        return jsonify({
            'message': 'Payment successful',
            'invoice_id': invoice_id,
            'appointment_id': appointment_id,
            'total': total,
            'card_type': card_type,
            'transaction_id': invoice['transaction_id'],
            'auth_code': invoice['auth_code'],
            'timestamp': invoice['timestamp']
        }), 201
    except Exception as e:
        return jsonify({'error': 'Payment was not processed'}), 500
    
@payment_bp.route('/cart/payment', methods=['POST'])
def pay_cart():
    data = request.json
    customer_id = data.get('customer_id')
    salon_id = data.get('salon_id')
    wallet_id = data.get('wallet_id') #optional
    card_number = data.get('card_number')  
    exp_month = data.get('exp_month')
    exp_year = data.get('exp_year')
    cvv = data.get('cvv')
    save_card = data.get('save_card', False)

    if not all([customer_id, salon_id, wallet_id]) or (not card_number and not wallet_id):
        return jsonify({'error': 'Missing required fields'}), 400
    
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    query = """
        select card_id
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
    
    subtotal = sum(row[1] * float(row[2]) for row in items)
    tax = round(subtotal * 0.08875, 2)
    total = round(subtotal + tax, 2) 

    if card_number:
        valid, card_type = validate_card(card_number, int(exp_month), int(exp_year), cvv)
        if not valid:
            return jsonify({'error': card_type}), 400
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

    try:
        query = """
            insert into invoices(appointment_id, customer_id, wallet_id, issued_date, subtotal_amount, tax_amount, total_amount, status)
            values(null, %s, %s, curdate(), %s, %s, %s, 'paid')
        """
        cursor.execute(customer_id, wallet_id, subtotal, tax, total)
        invoice_id = cursor.lastrowid

        for product_id, quantity, price, name, stock in items:
            if stock < quantity:
                cursor.close()
                return jsonify({'error': f'Insufficient stock for {name}'}), 400
        
        query = """
            insert into invoice_line_items(invoice_id, item_type, service_id, quantity, unit_price, description)
            values(%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (invoice_id, 'product', product_id, quantity, price, name))

        query = """
            update products
            set stock_quantity = stock_quantity - %s
            where product_id = %s
        """
        cursor.execute(query, (quantity, product_id))

        cursor.execute("update carts set status='completed' where cart_id=%s", (cart_id,))

        if save_card and card_number:
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

        mysql.connection.commit()
        cursor.close()

        return jsonify({
            'message': 'Cart payment successful',
            'invoice_id': invoice_id,
            'total': total,
            'card_type': card_type,
            'transaction_id': invoice['transaction_id'],
            'auth_code': invoice['auth_code'],
            'timestamp': invoice['timestamp']
        }), 201
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': f'Payment failure: {str(e)}'}), 500
    
@payment_bp.route('/payments/history/<int:customer_id>', methods=['GET'])
def payment_history(customer_id):
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
        return jsonify({'error': f'Error fetching payment history: {str(e)}'}), 500
    
@payment_bp.route('/payments/refund/<int:invoice_id>', methods=['POST'])
def refund_payment(invoice_id):
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
        
        if invoice[1] == 'cancelled':
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
        mysql.connection.rollback()
        return jsonify({'error': f'Refund failed: {str(e)}'}), 500