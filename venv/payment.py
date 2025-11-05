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

@payment_bp.route('/appointment/payment', methods=['POST'])
def pay_appointment():
    data = request.json
    appointment_id = data.get('appointment_id')
    customer_id = data.get('customer_id')
    wallet_id = data.get('wallet_id')
    subtotal = data.get('subtotal')
    tax = data.get('tax', 0.0)
    card_number = data.get('card_number')
    exp_month = data.get('exp_month')
    exp_year = data.get('exp_year')
    cvv = data.get('cvv')
    total = round(float(subtotal) + float(tax), 2) 

    if not all([appointment_id, customer_id, wallet_id, subtotal, card_number, exp_month, exp_year, cvv]):
        return jsonify({'error': 'Missing required fields'}), 400

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

    valid, result = validate_card(card_number, int(exp_month), int(exp_year), cvv)
    if not valid:
        return jsonify({'error': result}), 400

    card_type = result
    invoice = payment_process(card_type, total)

    try:
        query = """
            insert into invoices(appointment_id, customer_id, wallet_id, issued_date, subtotal_amount, tax_amount, total_amount)
            values(%s, %s, %s, curdate(), %s, %s, %s)
        """
        cursor.execute(query, (appointment_id, customer_id, wallet_id, subtotal, tax, total))
        invoice_id = cursor.lastrowid
        
        query = """
            update appointments
            set status = 'paid' 
            where appointment_id = %s
        """
        cursor.execute(query, (appointment_id,))
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
            select total_amount, status
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
        
        total_amount = float(invoice[0])
        refund_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        timestamp = datetime.now().isoformat()

        query = """
            update invoices
            set status = 'cancelled', last_modified = %s
            where invoice_id = %s
        """
        cursor.execute(query, (timestamp, invoice_id))

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

