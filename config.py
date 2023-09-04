import os

from dotenv import load_dotenv


load_dotenv()

telegram_token = os.getenv('TELEGRAM_TOKEN')
telegram_my_id = os.getenv('TELEGRAM_MY_ID')
database = "main.db"
work_day_start = "07:00"
timezone_my = "Europe/Moscow"

# mail.ru
my_email_mailru = os.getenv("EMAIL_MAILRU")
password_my_email_mailru = os.getenv("PASSWOR_EMAIL_MAILRU")
imap_server_mailru = "imap.mail.ru"