import os

from dotenv import load_dotenv


load_dotenv()

telegram_token = os.getenv('TELEGRAM_TOKEN')
telegram_my_id = os.getenv('TELEGRAM_MY_ID')
database = "main.db"
db_search = "people.db"
work_day_start = "07:00"
timezone_my = "Europe/Moscow"

# mail.ru
imap_server_mailru = "imap.mail.ru"
my_email_mailru = os.getenv("EMAIL_MAILRU")
password_my_email_mailru = os.getenv("PASSWOR_EMAIL_MAILRU")

# gmail
imap_server_gmail = "imap.gmail.com"
my_email_gmail = os.getenv("EMAIL_GMAIL")
password_my_email_gmail = os.getenv("PASSWOR_EMAIL_GMAIL")

# yandex
imap_server_yandex = "imap.yandex.ru"
my_email_yandex = os.getenv("EMAIL_YANDEX")
password_my_email_yandex = os.getenv("PASSWORD_EMAIL_YANDEX")

# rambler
smtp_server = "smtp.rambler.ru"
smtp_port = "587"
sender_email = os.getenv("EMAIL_RAMBLER_1")
sender_email_password = os.getenv("EMAIL_SENDER_PASSWORD")
recipient_email = os.getenv("EMAIL_RAMBLER_2")