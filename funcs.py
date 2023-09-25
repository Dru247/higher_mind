import logging
import smtplib


def send_email(smtp_server, smtp_port, sender_email, sender_email_password, recipient_email, data):
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_email_password)
        server.sendmail(sender_email, recipient_email, data.as_string())
    except Exception:
        logging.critical("func 'send email' - error", exc_info=True)
    finally:
        server.quit()