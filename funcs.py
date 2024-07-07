import config
import datetime
import imaplib
import logging
import main
import smtplib
import socket
import sqlite3 as sq
import os
import requests
import yadisk


ya = yadisk.YaDisk(token=config.ya_disk_token)


def send_email(smtp_server, smtp_port, sender_email, sender_email_password, recipient_email, data):
    server = smtplib.SMTP(smtp_server, smtp_port)
    try:
        server.starttls()
        server.login(sender_email, sender_email_password)
        server.sendmail(sender_email, recipient_email, data.as_string())
    except Exception:
        logging.critical("func 'send email' - error", exc_info=True)
    finally:
        server.quit()


def preparation_emails():
    emails = [
        (config.imap_server_mailru, config.my_email_mailru, config.password_my_email_mailru),
        (config.imap_server_yandex, config.my_email_yandex, config.password_my_email_yandex),
        (config.imap_server_gmail, config.my_email_gmail, config.password_my_email_gmail),
        (config.imap_server_yandex, config.my_email_yandex_2, config.password_my_email_yandex_2)
    ]

    for imap_server, email_login, email_password in emails:
        check_email(imap_server, email_login, email_password)


def check_email(imap_server, email_login, email_password):
    try:
        mailbox = imaplib.IMAP4_SSL(imap_server)
        mailbox.login(email_login, email_password)
        mailbox.select()
        unseen_msg = mailbox.uid('search', "UNSEEN", "ALL")
        id_unseen_msgs = unseen_msg[1][0].decode("utf-8").split()
        logging.info(msg=f"{email_login}: {id_unseen_msgs}")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE emails SET unseen_status = {len(id_unseen_msgs)} WHERE email = '{email_login}'")
    except Exception:
        logging.error("func check_email - error", exc_info=True)


def info_check_email():
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT email, unseen_status FROM emails")
            results = cur.fetchall()
        msg_text = "Письма на почтах:"
        for result in results:
            if result[1] > 0:
                msg_text += f"\n{result[0]}: {result[1]} шт."
        return msg_text
    except Exception:
        logging.error("func info_check_email - error", exc_info=True)


def save_logs():
    try:
        ya.upload(
            "logs.log",
            f"Logs/higher_mind/"
            f"{datetime.datetime.today().year}-"
            f"{datetime.datetime.today().isocalendar()[1]}.logs")
        if os.path.exists("logs.log"):
            os.remove("logs.log")
            with open("logs.log", 'w') as fp:
                pass
    except Exception:
        logging.warning("func save_logs - error", exc_info=True)


def send_logs(message):
    try:
        ya.upload(
            "logs.log",
            f"Logs/higher_mind/"
            f"{datetime.datetime.now()}.txt")
        main.bot.send_message(
            message.chat.id,
            text="Логи отправлены")
    except Exception:
        logging.warning("func send_logs - error", exc_info=True)


def socket_client(data_send, server=config.socket_server, port=config.socket_port, coding=config.coding):
    sock = socket.socket()
    sock.connect((server, port))
    sock.send(data_send.encode(coding))
    sock.close()


def get_balance():
    try:
        plan_task = 5
        plan_routine = 0.2
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT count() FROM events")
            count_events = cur.fetchone()[0]
            cur.execute("SELECT count() FROM tasks WHERE success = 1")
            count_success_tasks = cur.fetchone()[0]
            cur.execute("SELECT count() FROM routine WHERE task_id IN (495, 496) AND success = 0")
            bad_doing = cur.fetchone()[0]
            cur.execute("SELECT count() FROM routine WHERE success = 1")
            success_routines = cur.fetchone()[0]
        result = count_success_tasks + (success_routines * plan_routine) - ((bad_doing + count_events) * plan_task)
        logging.info(f"func count_access; balance = {result}")
        return result
    except Exception:
        logging.warning("func get_balance - error", exc_info=True)


def get_temperature():
    try:
        lat = 55.7522
        lon = 37.6156
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid=79d1ca96933b0328e1c7e3e7a26cb347&units=metric"
        weather_data = requests.get(url).json()
        temps = list()
        date_now = datetime.datetime.now().date()
        logging.info(f"func get_temperature - {weather_data}")
        for weather in weather_data["list"]:
            weather_date = datetime.datetime.fromisoformat(weather["dt_txt"]).date()
            if date_now == weather_date:
                temps.append(float(weather["main"]["temp_max"]))

        return min(temps), max(temps)
    except Exception:
        logging.warning("func get_temperature - error", exc_info=True)
