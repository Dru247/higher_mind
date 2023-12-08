import config
import datetime
import logging
import imaplib
import os
import schedule
import socket
import sqlite3 as sq
import telebot
import threading
import time
import yadisk

from pytz import timezone
from telebot import types


ya = yadisk.YaDisk(token=config.ya_disk_token)

logging.basicConfig(
    level=logging.INFO,
    filename="logs.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s")
schedule_logger = logging.getLogger('schedule')
schedule_logger.setLevel(level=logging.DEBUG)

bot = telebot.TeleBot(config.telegram_token)

commands = ["Cоздать задачу",
            "Изменить задачу",
            "Cписок задач"]

keyboard_main = types.ReplyKeyboardMarkup(resize_keyboard=True)
item_1 = types.KeyboardButton(commands[0])
item_2 = types.KeyboardButton(commands[1])
item_3 = types.KeyboardButton(commands[2])
keyboard_main.row(item_1, item_2, item_3)


# routine
def routine_check():
    try:
        preparation_emails()
        with sq.connect(config.database) as con:
            cur = con.cursor()
            max_unseen_msgs = 40
            cur.execute("SELECT sum(unseen_status) FROM emails")
            result = cur.fetchone()[0]
            logging.info(f"Unseen msg = {result}")
            if int(result) < max_unseen_msgs:
                cur.execute("""
                    UPDATE routine SET success = 1
                    WHERE task_id = 121
                    AND date_id = (SELECT id FROM dates WHERE date = date('now'))
                    """)
            cur.execute(f"""
                SELECT routine.id, tasks.task, tasks.id
                FROM routine
                JOIN tasks ON routine.task_id = tasks.id
                WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                AND success = {0}
                AND task_id != 121
                """)
            results = cur.fetchall()
            if results:
                logging.info(f"func routine_daily_check_2: exist daily routine ({results})")
                for result in results:
                    routine_id = result[0]
                    keyboard = types.InlineKeyboardMarkup()
                    key_1 = types.InlineKeyboardButton(
                        text='Выполнено',
                        callback_data=f"routine_set_status {routine_id};1")
                    key_2 = types.InlineKeyboardButton(
                        text='Не выполнено',
                        callback_data=f"routine_set_status {routine_id};0")
                    keyboard.add(key_1, key_2)
                    bot.send_message(
                        config.telegram_my_id,
                        text=f"{result[2]}: {result[1]}",
                        reply_markup=keyboard)
            else:
                logging.info(f"func routine_daily_check_2: not exist daily routine ({results})")
                bot.send_message(config.telegram_my_id, text=f"Сегодня задач не было")
    except:
        logging.critical(msg="func routine_daily_check_2 - error", exc_info=True)
        bot.send_message(chat_id=config.telegram_my_id, text="Некорректно")


def set_routine_status(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE routine SET success = {data[1]} WHERE id = {data[0]}")
            cur.execute(f"SELECT task_id FROM routine WHERE id = {data[0]}")
            task_id = cur.fetchone()[0]
        if data[1] == "1":
            bot.send_message(chat_id=message.chat.id, text=f"Задача №{task_id} выполнена")
        else:
            bot.send_message(chat_id=message.chat.id, text=f"Задача №{task_id} не выполнена")
    except Exception:
        logging.warning(msg="func set_routine_status - error", exc_info=True)


# user
def set_user(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"INSERT INTO users (first_name, telegram_id) VALUES ('{message.text}', {message.chat.id})")
            bot.send_message(
                chat_id=message.chat.id,
                text="Приятно познакомиться",
                reply_markup=keyboard_main)
    except Exception:
        logging.warning("func set_user - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


# tasks
def choice_field_type(message):
    inline_keys = []
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute("SELECT id, field_name FROM task_field_types")
        for record in cur:
            inline_keys.append(
                types.InlineKeyboardButton(
                    text=record[1],
                    callback_data=f"task_select_field {record[0]}"))
    inline_keys.append(types.InlineKeyboardButton(
                            text='Новый проект',
                            callback_data='new_type_field_task'))
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(*inline_keys)
    bot.send_message(
        message.from_user.id,
        text="Выбери проект",
        reply_markup=keyboard)


def set_type_field_task(message):
    bot.send_message(message.chat.id, text="Введи новый тип задач")
    bot.register_next_step_handler(message, add_type_field_task)


def add_type_field_task(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"INSERT INTO task_field_types(field_name) VALUES('{message.text}')")
            bot.send_message(message.chat.id, text=f"Новый тип задач ({message.text}) добавлен", reply_markup  = keyboard_main)
        
    except Exception:
        logging.critical("func add_routine - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


def set_task(message, call_data):
    try:
        id_field = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            inline_keys = []
            cur.execute("SELECT id, name FROM task_frequency_types")
            for record in cur:
                inline_keys.append(
                    types.InlineKeyboardButton(
                        text=record[1],
                        callback_data=f"task_select_frequency {id_field};{record[0]}"))
            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(*inline_keys)
        bot.send_message(
            message.chat.id,
            text="Введи тип задачи",
            reply_markup=keyboard)
    except Exception:
        logging.critical("func set_task - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


def add_task(message, data):
    bot.send_message(message.chat.id, "Введи текст задачи")
    bot.register_next_step_handler(message, lambda m: add_task_2(m, data))


def add_task_2(message, data):
    task_set = data.split()[1].split(";")
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""INSERT INTO tasks (id_user, task_field_type, frequency_type, task)
                        VALUES ((SELECT id FROM users WHERE telegram_id = {message.chat.id}), {task_set[0]}, {task_set[1]}, '{message.text}')
                        """)
            bot.send_message(message.chat.id, f"Задача №{cur.lastrowid}: создана")
            if message.text[0] == "!":
                cur.execute(f"""
                    INSERT INTO routine (date_id, task_id)
                    VALUES (
                        (SELECT id FROM dates
                        WHERE date = date('now')),
                        {cur.lastrowid})
                    """)
    except Exception:
        logging.critical("func add_task - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


def change_task_set_number(message):
    msg = bot.send_message(chat_id=message.chat.id, text="Введи № задачи")
    bot.register_next_step_handler(message=msg, callback=change_task_set_field)


def change_task_set_field(message):
    try:
        key_1 = types.InlineKeyboardButton(
            text="Текст",
            callback_data=f"change_task_text {message.text}")
        key_2 = types.InlineKeyboardButton(
            text="Периодичность",
            callback_data=f"change_task_frequency {message.text}")
        key_3 = types.InlineKeyboardButton(
            text="Тип",
            callback_data=f"change_task_type {message.text}")
        key_4 = types.InlineKeyboardButton(
            text="Удалить",
            callback_data=f"change_task_remove {message.text}")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(key_1, key_2, key_3, key_4)
        bot.send_message(
            chat_id=message.chat.id,
            text="Что меняем?",
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func change_task_set_field - error", exc_info=True)


def change_task_set_text(message, call_data):
    try:
        data = call_data.split()[1]
        msg = bot.send_message(chat_id=message.chat.id, text="Введи текст задачи")
        bot.register_next_step_handler(message=msg, callback=change_task_text, data=data)
    except Exception:
        logging.critical(msg="func change_task_set_text - error", exc_info=True)


def change_task_text(message, data):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE tasks SET task = '{message.text}' WHERE id = '{data}'")
            bot.send_message(chat_id=message.chat.id, text="Успех")
    except Exception:
        logging.critical(msg="func change_task_text - error", exc_info=True)


def change_task_set_type(message, call_data):
    try:
        data = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            inline_keys = []
            cur.execute("SELECT id, field_name FROM task_field_types")
            for record in cur:
                inline_keys.append(
                    types.InlineKeyboardButton(
                        text=record[1],
                        callback_data=f"change_task_choice_type {data};{record[0]}"))
            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(*inline_keys)
        bot.send_message(
            message.chat.id,
            text="Введи тип задачи",
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func change_task_set_type - error", exc_info=True)


def change_task_type(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE tasks SET task_field_type = '{data[1]}' WHERE id = '{data[0]}'")
            bot.send_message(chat_id=message.chat.id, text="Успех")
    except Exception:
        logging.critical(msg="func change_task_type - error", exc_info=True)


def change_task_set_frequency(message, call_data):
    try:
        data = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            inline_keys = []
            cur.execute("SELECT id, name FROM task_frequency_types")
            for record in cur:
                inline_keys.append(
                    types.InlineKeyboardButton(
                        text=record[1],
                        callback_data=f"change_task_choice_frequency {data};{record[0]}"))
            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(*inline_keys)
        bot.send_message(
            message.chat.id,
            text="Введи периодичность задачи",
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func change_task_set_frequency - error", exc_info=True)


def change_task_frequency(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE tasks SET frequency_type = '{data[1]}' WHERE id = '{data[0]}'")
            bot.send_message(chat_id=message.chat.id, text="Успех")
    except Exception:
        logging.critical(msg="func change_task_frequency - error", exc_info=True)


def change_task_remove(message, call_data):
    try:
        data = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"DELETE FROM tasks WHERE id = '{data}'")
            bot.send_message(
                chat_id=message.chat.id,
                text=f"Задача №{data} удалена")
    except Exception:
        logging.critical(msg="func change_task_remove - error", exc_info=True)


def list_tasks(message):
    try:
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT id, field_name FROM task_field_types")
            for record in cur:
                inline_keys.append(
                    types.InlineKeyboardButton(
                        text=record[1],
                        callback_data=f"list_tasks {record[0]}"))
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            message.from_user.id,
            text="Выбери проект",
            reply_markup=keyboard)

    except Exception:
        logging.critical("func 'list_tasks' - error", exc_info=True)


def list_tasks_view(message, call_data):
    try:
        project = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""
                SELECT tasks.id, tasks.task, task_frequency_types.name
                FROM tasks
                JOIN  task_frequency_types ON tasks.frequency_type = task_frequency_types.id
                WHERE task_field_type = {project}
                AND (tasks.id NOT IN (SELECT task_id FROM routine WHERE success = 1)
                OR frequency_type != 5)
            """)
            for row in cur.fetchall():
                bot.send_message(
                    chat_id=message.chat.id,
                    text=f"{row[0]}/{row[2]}: {row[1]}")

    except Exception:
        logging.critical("func 'list_tasks' - error", exc_info=True)


def search_add(message, call_data):
    try:
        data = call_data.split()
        if data[1] == "people":
            bot.send_message(
                message.chat.id,
                text="Введи данные в формате Nam;Add;Met;Pho"
                )
            bot.register_next_step_handler(
                message,
                lambda m: socket_client(
                    config.socket_server,
                    config.socket_port,
                    config.coding,
                    data_send=f"add_new: {m.text}"
                )
            )
        elif data[1] == "event":
            socket_client(
                config.socket_server,
                config.socket_port,
                config.coding,
                data_send="view_people_prof")
            bot.send_message(
                message.chat.id,
                text="Введи данные в формате ID_Peo;Dat;Coun"
                )
            bot.register_next_step_handler(
                message,
                lambda m: socket_client(
                    config.socket_server,
                    config.socket_port,
                    config.coding,
                    data_send=f"add_event: {m.text}"
                    )
                )
        elif data[1] == "peo_prof":
            socket_client(
                config.socket_server,
                config.socket_port,
                config.coding,
                data_send="view_people_prof")
            bot.send_message(
                message.chat.id,
                text="Введи данные в формате ID_Peo;Number"
                )
            bot.register_next_step_handler(
                message,
                lambda m: socket_client(
                    config.socket_server,
                    config.socket_port,
                    config.coding,
                    data_send=f"add_people_prof: {m.text}"
                    )
                )
        elif data[1] == "grades":
            socket_client(
                config.socket_server,
                config.socket_port,
                config.coding,
                data_send="view_people_prof")
            bot.send_message(
                message.chat.id,
                text="Введи данные в формате ID_Peo;12char"
                )
            bot.register_next_step_handler(
                message,
                lambda m: socket_client(
                    config.socket_server,
                    config.socket_port,
                    config.coding,
                    data_send=f"add_grades: {m.text}"
                    )
                )
    except Exception:
        logging.critical("func 'search_add' - error", exc_info=True)


# Email unseen messages reminder
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
        mailBox = imaplib.IMAP4_SSL(imap_server)
        mailBox.login(email_login, email_password)
        mailBox.select()
        unseen_msg = mailBox.uid('search', "UNSEEN", "ALL")
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
                bot.send_message(
                    config.telegram_my_id,
                    text=f"На почте {result[0]} есть непрочитанные письма, "
                    f"в кол-ве {result[1]} шт.")


def tasks_tomorrow():
    try:
        date = datetime.date.today() + datetime.timedelta(days=1)
        with sq.connect(config.database) as con:
            cur = con.cursor()
            try:
                cur.execute("""
                    SELECT count() FROM routine
                    WHERE date_id = (SELECT id FROM dates WHERE date = date('now', '+1 day'))
                    """)
                bot.send_message(
                    config.telegram_my_id,
                    text=f"Баланс {get_balance()}")
            except Exception:
                logging.error("func tasks_tomorrow:count_routine - error", exc_info=True)
            cur.execute(f"""
                SELECT id, task FROM tasks
                WHERE task_field_type = (SELECT project_id FROM week_project ORDER BY id DESC LIMIT 1)
                AND (id NOT IN (SELECT task_id FROM routine WHERE success = 1)
                OR frequency_type != 5)
                ORDER BY random()
                LIMIT 8
                """)
            for result in cur.fetchall():
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(
                    types.InlineKeyboardButton(
                        text='Завтра?',
                        callback_data=f"routine_tomorrow "
                        f"{result[0]};{date.isoformat()}"
                    )
                )
                bot.send_message(
                    config.telegram_my_id,
                    text=f"{result[0]}: {result[1]}",
                    reply_markup=keyboard)

    except Exception:
        logging.error("func tasks_tomorrow - error", exc_info=True)


def add_routine_tomorrow(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                f"""INSERT INTO routine (date_id, task_id)
                VALUES (
                    (SELECT id FROM dates WHERE date = '{data[1]}'),
                    {data[0]}
                )""")
            bot.send_message(
                message.chat.id,
                text=f"Задача №{data[0]}: добавлена на исполнение")
    except Exception:
        logging.error(msg="func add_routine_tomorrow - error", exc_info=True)


def get_balance():
    try:
        day_routines = 8
        week_days = 7
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT count(event) FROM events")
            count_events = int(cur.fetchone()[0])
            cur.execute("SELECT count(success) FROM routine WHERE success = 1")
            count_routine = int(cur.fetchone()[0])
            cur.execute("SELECT count(date) FROM dates WHERE date < date('now')")
            count_dates = int(cur.fetchone()[0])
            routine_balance = (count_routine - count_dates * day_routines) / day_routines
            event_balance = count_dates - count_events * week_days
            balance = event_balance + routine_balance
            logging.info(f"Balance {balance}")
            return balance
    except Exception:
        logging.warning("func count_access - error", exc_info=True)


def access_check(message, call_data):
    try:
        balance = get_balance()
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT EXISTS(
                SELECT * FROM routine
                WHERE task_id = 91
                AND success = 0
                AND date_id IN
                (SELECT id FROM dates
                WHERE date BETWEEN date('now', '-15 day') AND date('now', '-1 day')))
                """)
            bad_hand = cur.fetchone()
        if balance > 0 and not bad_hand:
            with sq.connect(config.database) as con:
                cur = con.cursor()
                cur.execute("INSERT INTO events (event) VALUES(1)")
            bot.send_message(
                message.chat.id,
                text=f"Допуск получен:\nбаланс: {balance}\n"
                     f"3НЕ: {bad_hand[0]}"
            )
            socket_client(
                config.socket_server,
                config.socket_port,
                config.coding,
                call_data.split()[1])
        else:
            bot.send_message(
                message.chat.id,
                text=f"Допуск НЕ получен:\nбаланс: {balance}\n"
                     f"3НЕ: {bad_hand[0]}"
            )
    except Exception:
        logging.warning(msg="func access_check - error", exc_info=True)


def socket_client(server, port, coding, data_send):
    sock = socket.socket()
    sock.connect((server, port))
    sock.send(data_send.encode(coding))
    sock.close()


def morning_business():
    preparation_emails()
    info_check_email()
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute(
            """SELECT routine.id, tasks.task, tasks.id
            FROM routine
            JOIN tasks ON routine.task_id = tasks.id
            WHERE
            date_id = (SELECT id FROM dates WHERE date = date('now'))
            """)
        bot.send_message(
            config.telegram_my_id,
            text=f"Баланс {get_balance()}\nСегодня у тебя следующие задачи:")
        for result in cur:
            bot.send_message(
                config.telegram_my_id,
                text=f"{result[2]}: {result[1]}")


def planning_week():
    try:
        date_now = datetime.date.today()
        tomorrow = date_now + datetime.timedelta(days=1)
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT id, field_name
                FROM task_field_types
                ORDER BY random()
                LIMIT 1
                """)
            cur.execute("SELECT id, field_name FROM task_field_types ORDER BY random() LIMIT 1")
            result_project = cur.fetchone()
            bot.send_message(
                config.telegram_my_id,
                text=f"{result_project[1]} - проект следующей недели")
            cur.execute(f"""
                INSERT INTO week_project (week, project_id)
                VALUES (
                    '{tomorrow.isocalendar()[0]}-{tomorrow.isocalendar()[1]}',
                    {result_project[0]}
                    )
                """)
            week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            for day in range(1, 8):
                cur.execute(f"""
                    INSERT OR IGNORE INTO dates (date)
                    VALUES (date('now','+{day} day'))
                """)
            con.commit()
            cur.execute("""SELECT id, tasks.task
                FROM tasks
                WHERE frequency_type = 2
                """)
            for result in cur:
                keyboard = types.InlineKeyboardMarkup()
                keys = []
                for number, day in enumerate(week):
                    date = date_now + datetime.timedelta(days=number + 1)
                    key = types.InlineKeyboardButton(
                        text=day,
                        callback_data=f"routine_week {date.isoformat()};{result[0]}")
                    keys.append(key)
                keyboard.row(*keys)
                bot.send_message(
                    config.telegram_my_id,
                    text=f"Запланируй задачу №{result[0]}: {result[1]}",
                    reply_markup=keyboard)
    except Exception:
        logging.error("func planning_week - error", exc_info=True)


def add_routine_week(message, call_data):
    try:
        data = call_data.split()[1]
        data = data.split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""INSERT INTO routine (date_id, task_id)
                VALUES (
                    (SELECT id FROM dates WHERE date = '{data[0]}'),
                    {data[1]}
                    )
                """)
        bot.send_message(
            message.chat.id,
            text=f"Задача №{data[1]} запланирована на {data[0]}")
    except Exception:
        logging.error("func add_routine_week - error", exc_info=True)


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


def add_date():
    week_day = datetime.datetime.today().weekday()
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute("""INSERT OR IGNORE INTO dates (date)
            VALUES (date('now','+1 day'))""")
        if week_day not in (4, 5):
            cur.execute("SELECT id FROM tasks WHERE frequency_type IN (1, 6)")
        else:
            cur.execute("SELECT id FROM tasks WHERE frequency_type = 1")
        for result in cur.fetchall():
            cur.execute(f"""INSERT INTO routine (date_id, task_id)
                VALUES (
                (SELECT id FROM dates WHERE date = date('now','+1 day')),
                {result[0]}
                )
                """)
    if week_day == 6:
        planning_week()
        save_logs()
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """INSERT INTO tasks(id_user, task_field_type, frequency_type, task)
                VALUES (1, 1, 5, 'Прочитать логи')""")
            cur.execute(
                f"""INSERT INTO routine (date_id, task_id)
                VALUES (
                    (SELECT id FROM dates WHERE date = date('now','+1 day')),
                    {cur.lastrowid})
                """)


def planning_day():
    add_date()
    routine_check()
    tasks_tomorrow()


def schedule_main():
    schedule.every().day.at(
        "07:00",
        timezone(config.timezone_my)
        ).do(morning_business)
    schedule.every().day.at(
        "21:30",
        timezone(config.timezone_my)
        ).do(planning_day)

    while True:
        schedule.run_pending()
        time.sleep(1)


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, text="Привет! Напиши имя")
    bot.register_next_step_handler(message, set_user)


@bot.message_handler(commands=['help', 'commands'])
def help_message(message):
    bot.send_message(
        message.chat.id,
        text="Привет! Лови клавиатуру",
        reply_markup=keyboard_main)


@bot.message_handler(commands=['logs'])
def send_logs(message):
    try:
        ya.upload(
            "logs.log",
            f"Logs/higher_mind/"
            f"{datetime.datetime.now()}.txt")
        bot.send_message(
            message.chat.id,
            text="Логи отправлены",
            reply_markup=keyboard_main)
    except Exception:
        logging.warning("func send_logs - error", exc_info=True)


@bot.message_handler(commands=['search'])
def task_completed(message):
    keyboard = types.InlineKeyboardMarkup()
    key_1 = types.InlineKeyboardButton(
        text="Start search",
        callback_data='search search')
    key_2 = types.InlineKeyboardButton(
        text="Start search all",
        callback_data='search search_all')
    key_3 = types.InlineKeyboardButton(
        text="Email",
        callback_data='search email')
    key_4 = types.InlineKeyboardButton(
        text="Add people",
        callback_data='emailer_add people')
    key_5 = types.InlineKeyboardButton(
        text="Add event",
        callback_data='emailer_add event')
    key_6 = types.InlineKeyboardButton(
        text="Add people_prof",
        callback_data='emailer_add peo_prof')
    key_7 = types.InlineKeyboardButton(
        text="Add grades",
        callback_data='emailer_add grades')

    keyboard.add(key_1, key_2, key_3, key_4, key_5, key_6, key_7)
    bot.send_message(
        message.from_user.id,
        text="What we will do?",
        reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if "task_select_field" in call.data:
        set_task(call.message, call.data)
    elif "task_select_frequency" in call.data:
        add_task(call.message, call.data)
    elif "routine_set_status" in call.data:
        set_routine_status(call.message, call.data)
    elif "change_task_text" in call.data:
        change_task_set_text(call.message, call.data)
    elif "change_task_type" in call.data:
        change_task_set_type(call.message, call.data)
    elif "change_task_choice_type" in call.data:
        change_task_type(call.message, call.data)
    elif "change_task_frequency" in call.data:
        change_task_set_frequency(call.message, call.data)
    elif "change_task_choice_frequency" in call.data:
        change_task_frequency(call.message, call.data)
    elif "change_task_remove" in call.data:
        change_task_remove(call.message, call.data)
    elif "list_tasks" in call.data:
        list_tasks_view(call.message, call.data)
    elif "search" in call.data:
        access_check(call.message, call.data)
    elif "new_type_field_task" in call.data:
        set_type_field_task(call.message)
    elif "emailer_add" in call.data:
        search_add(call.message, call.data)
    elif "routine_tomorrow" in call.data:
        add_routine_tomorrow(call.message, call.data)
    elif "routine_week" in call.data:
        add_routine_week(call.message, call.data)


@bot.message_handler(content_types=['text'])
def take_text(message):
    if message.text.lower() == commands[0].lower():
        choice_field_type(message)
    elif message.text.lower() == commands[1].lower():
        change_task_set_number(message)
    elif message.text.lower() == commands[2].lower():
        list_tasks(message)
    else:
        logging.warning(
            f"func take_text: not understend question: {message.text}")
        bot.send_message(message.chat.id, 'Я не понимаю, к сожалению')


if __name__ == "__main__":
    threading.Thread(target=schedule_main).start()
    bot.infinity_polling()
