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
        logging.error("func check email - error", exc_info=True)


def info_check_email():
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute("SELECT email, unseen_status FROM emails")
        results = cur.fetchall()
        for result in results:
            if result[1] > 0:
                main.bot.send_message(
                    config.telegram_my_id,
                    text=f"На почте {result[0]} есть непрочитанные письма, "
                    f"в кол-ве {result[1]} шт.")


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
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT count() FROM events")
            count_events = cur.fetchone()[0]
            cur.execute("SELECT count() FROM dates WHERE date < date('now')")
            count_dates = cur.fetchone()[0]
            cur.execute("SELECT count() FROM tasks WHERE success = 1")
            count_success_tasks = cur.fetchone()[0]
            cur.execute("SELECT count() FROM routine WHERE task_id = 494 AND success = 0")
            bad_thoughts = cur.fetchone()[0]
            cur.execute("SELECT count() FROM routine WHERE task_id = 495 AND success = 0")
            bad_eyes = cur.fetchone()[0]
            cur.execute("SELECT count() FROM routine WHERE task_id = 496 AND success = 0")
            bad_hand = cur.fetchone()[0]
        bad_doing = bad_thoughts + bad_eyes + bad_hand
        result = count_success_tasks - count_dates / 2 - bad_doing - count_events
        return result
    except Exception:
        logging.warning("func count_access - error", exc_info=True)


def access_weight():
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT sum(priorities.grade)
                FROM routine
                JOIN tasks ON tasks.id = routine.task_id
                JOIN priorities ON priorities.id = tasks.priority_id
                WHERE routine.success = 1
                AND date_id IN
                (SELECT id FROM dates
                WHERE date >= date('now', '-7 day')
                AND date < date('now'))
            """)
            sum_routine = cur.fetchone()[0]
            cur.execute("SELECT weight FROM my_weight ORDER BY id DESC LIMIT 1")
            my_weight = cur.fetchone()[0]
        return (90 - my_weight) * 10 + sum_routine
    except Exception:
        logging.warning("func access_weight - error", exc_info=True)


def get_temperature():
    try:
        city = "Москва"
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&lang=ru&appid=79d1ca96933b0328e1c7e3e7a26cb347"
        weather_data = requests.get(url).json()
        temperature = weather_data["main"]["temp_max"]
        return temperature
    except Exception:
        logging.warning("func get_temperature - error", exc_info=True)
