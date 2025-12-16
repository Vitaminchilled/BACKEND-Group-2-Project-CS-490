from flask_mail import Message
from flask import current_app

'''def send_email(to, subject, body, html=None):
    mail = current_app.extensions.get('mail')
    if not mail:
        raise RuntimeError("Flask-Mail is not initialized. Make sure you called mail.init_app(app).")
    
    msg = Message(
        subject=subject,
        recipients=[to],
        sender=current_app.config.get("MAIL_USERNAME")
    )
    msg.body = body
    
    if html:
        msg.html = html

    mail.send(msg)'''

def send_email(to, subject, body, html=None):
    try:
        mail = current_app.extensions.get('mail')
        if not mail:
            log_error("Flask-Mail is not initialized.", session.get("user_id"))
            return False

        msg = Message(
            subject=subject,
            recipients=[to],
            sender=current_app.config.get("MAIL_USERNAME")
        )
        msg.body = body

        if html:
            msg.html = html

        mail.send(msg)
        return True

    except Exception as e:
        log_error(f"Failed to send email: {str(e)}", session.get("user_id"))
        return False
