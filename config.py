import os

from dotenv import load_dotenv


load_dotenv()

telegram_token = os.getenv('TELEGRAM_TOKEN')
telegram_my_id = os.getenv('TELEGRAM_MY_ID')
database = "main.db"
timezone_my = "Europe/Moscow"
coding = "utf-8"

# mail.ru
imap_server_mailru = "imap.mail.ru"
my_email_mailru = os.getenv("EMAIL_MAILRU")
password_my_email_mailru = os.getenv("PASSWOR_EMAIL_MAILRU")
smtp_server_mailru = "smtp.mail.ru"
smtp_port_mailru = "587"

# gmail
imap_server_gmail = "imap.gmail.com"
my_email_gmail = os.getenv("EMAIL_GMAIL")
password_my_email_gmail = os.getenv("PASSWOR_EMAIL_GMAIL")

# yandex
imap_server_yandex = "imap.yandex.ru"
my_email_yandex = os.getenv("EMAIL_YANDEX")
password_my_email_yandex = os.getenv("PASSWORD_EMAIL_YANDEX")

# socket
socket_server = os.getenv("SOCKET_SERVER")
socket_port = int(os.getenv("SOCKET_PORT"))
