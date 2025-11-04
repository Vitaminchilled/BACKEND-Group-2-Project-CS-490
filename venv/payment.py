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
    
def payment_process():
    pass

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
    
    valid, result = validate_card(card_number, int(exp_month), int(exp_year), cvv)
    if not valid:
        return jsonify({'error': result}), 400

    card_type = result

    #payment processing 

    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor()

    try:
        query = """
            insert into invoices(appointment_id, customer_id, wallet_id, issued_date, subtotal_amount, tax_amount, total_amount)
            values(%s, %s, %s, curdate(), %s, %s, %s)
        """
        cursor.execute(query, (appointment_id, customer_id, wallet_id, subtotal, tax, total))
        invoice_id = cursor.lastrowid
        
        query = """
            update appointments
            set status = 'booked' 
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
            'card_type': card_type
        }), 201
    except Exception as e:
        return jsonify({'error': 'Payment was not processed'}), 500