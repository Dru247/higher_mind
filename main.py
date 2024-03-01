import random

import config
import datetime
import funcs
import logging
import schedule
import sqlite3 as sq
import telebot
import threading
import time

from pytz import timezone
from telebot import types
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


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
        funcs.preparation_emails()
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
            cur.execute("""
                SELECT routine.id, tasks.task, tasks.id
                FROM routine
                JOIN tasks ON routine.task_id = tasks.id
                WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                AND routine.success = 0
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
    except Exception:
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
            cur.execute(
                "INSERT INTO users (first_name, telegram_id) VALUES (?, ?)",
                (message.text, message.chat.id)
            )
            bot.send_message(
                chat_id=message.chat.id,
                text="Приятно познакомиться",
                reply_markup=keyboard_main)
    except Exception:
        logging.warning("func set_user - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


# tasks
def choice_field_type(message):
    try:
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT id, field_name FROM projects")
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
    except Exception:
        logging.critical("func choice_field_type - error", exc_info=True)


def set_type_field_task(message):
    try:
        bot.send_message(message.chat.id, text="Введи новый тип задач")
        bot.register_next_step_handler(message, add_type_field_task)
    except Exception:
        logging.critical("func set_user - error", exc_info=True)


def add_type_field_task(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO projects (field_name) VALUES (?)",
                (message.text,)
            )
            bot.send_message(
                message.chat.id,
                text=f"Новый тип задач ({message.text}) добавлен",
                reply_markup = keyboard_main
            )
        
    except Exception:
        logging.critical("func add_routine - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


def set_task(message, call_data):
    try:
        id_field = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            inline_keys = []
            cur.execute("SELECT id, name FROM frequencies")
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
    try:
        bot.send_message(message.chat.id, "Введи текст задачи")
        bot.register_next_step_handler(message, lambda m: add_task_2(m, data))
    except Exception:
        logging.critical("func add_task - error", exc_info=True)


def add_task_2(message, data):
    task_set = data.split()[1].split(";")
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""
                INSERT INTO tasks (user_id, project_id, frequency_id, task)
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
    try:
        msg = bot.send_message(chat_id=message.chat.id, text="Введи № задачи")
        bot.register_next_step_handler(message=msg, callback=change_task_set_field)
    except Exception:
        logging.critical(msg="func change_task_set_number - error", exc_info=True)


def change_task_set_field(message):
    try:
        key_1 = types.InlineKeyboardButton(
            text="Текст",
            callback_data=f"change_task_text {message.text}")
        key_2 = types.InlineKeyboardButton(
            text="Периодичность",
            callback_data=f"change_task_frequency {message.text}")
        key_3 = types.InlineKeyboardButton(
            text="Проект",
            callback_data=f"change_task_type {message.text}")
        key_4 = types.InlineKeyboardButton(
            text="Удалить",
            callback_data=f"change_task_remove {message.text}")
        key_5 = types.InlineKeyboardButton(
            text="Выполнить",
            callback_data=f"change_task_success {message.text}")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(key_1, key_2, key_3, key_4, key_5)
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
            cur.execute("SELECT id, field_name FROM projects")
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
            cur.execute(f"UPDATE tasks SET project_id = '{data[1]}' WHERE id = '{data[0]}'")
            bot.send_message(chat_id=message.chat.id, text="Успех")
    except Exception:
        logging.critical(msg="func change_task_type - error", exc_info=True)


def change_task_set_frequency(message, call_data):
    try:
        data = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            inline_keys = []
            cur.execute("SELECT id, name FROM frequencies")
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
            cur.execute(f"UPDATE tasks SET frequency_id = '{data[1]}' WHERE id = '{data[0]}'")
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


def change_task_success(message, call_data):
    try:
        task_id = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("UPDATE tasks SET success = 1 WHERE id = ?", (task_id,))
        bot.send_message(
            chat_id=message.chat.id,
            text=f"Задача №{task_id} выполнена")
    except Exception:
        logging.critical(msg="func change_task_success - error", exc_info=True)


def list_tasks(message):
    try:
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT id, field_name FROM projects")
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


def list_tasks_view(message1, call_data):
    try:
        project = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT field_name FROM projects WHERE id = {project}")
            project_name = cur.fetchone()[0]
            cur.execute(f"""
                SELECT tasks.id, tasks.task, frequencies.name
                FROM tasks
                JOIN frequencies ON tasks.frequency_id = frequencies.id
                WHERE project_id = {project}
                AND success = 0
            """)
            message = MIMEMultipart()
            message["From"] = config.my_email_mailru
            message["To"] = config.my_email_yandex
            message["Subject"] = f'Список задач проекта "{project_name}"'
            data = f"""
                <!DOCTYPE html><html><body><table><caption>{project_name}</caption>
                <thead><tr><th>ID</th><th>Период.</th><th>Задача</th></tr></thead>
                <tbody>
                """
            for row in cur.fetchall():
                data += f"<tr><td>{row[0]}</td><td>{row[2]}</td><td>{row[1]}</td></tr>"
            data += "</tbody></table></body></html>"
            part = MIMEText(data, _subtype="html")
            message.attach(part)
            funcs.send_email(
                config.smtp_server_mailru,
                config.smtp_port_mailru,
                config.my_email_mailru,
                config.password_my_email_mailru,
                config.my_email_yandex,
                message)
            bot.send_message(
                chat_id=message1.chat.id,
                text=f"Письмо отправлено")
    except Exception:
        logging.critical("func 'list_tasks' - error", exc_info=True)


def tasks_tomorrow():
    try:
        date = datetime.date.today() + datetime.timedelta(days=1)
        bot.send_message(
            config.telegram_my_id,
            text=f"Баланс: {funcs.get_balance()}")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""
                SELECT id, task FROM tasks
                WHERE project_id = (SELECT project_id FROM week_project ORDER BY id DESC LIMIT 1)
                AND success = 0
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


def morning_business():
    try:
        funcs.preparation_emails()
        funcs.info_check_email()
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT routine.id, tasks.task, tasks.id
                FROM routine
                JOIN tasks ON routine.task_id = tasks.id
                WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
            """)
            result = cur.fetchall()
        bot.send_message(
            config.telegram_my_id,
            text=f"Баланс: {funcs.get_balance()}\nТемпература: {funcs.get_temperature()}\nСегодня у тебя следующие задачи:")
        for line in result:
            bot.send_message(config.telegram_my_id, text=f"{line[2]}: {line[1]}")
        msg = bot.send_message(chat_id=config.telegram_my_id, text="Сколько весишь?")
        bot.register_next_step_handler(message=msg, callback=add_my_weight)
    except Exception:
        logging.error(msg="func morning_business - error", exc_info=True)


def add_my_weight(message):
    try:
        weight = message.text.strip()
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("INSERT INTO my_weight (weight) VALUES (?)", (weight,))
        bot.send_message(chat_id=config.telegram_my_id, text=f"goal:{funcs.access_weight()}")
    except Exception:
        logging.error(msg="func add_my_weight - error", exc_info=True)


def planning_week():
    try:
        date_now = datetime.date.today()
        tomorrow = date_now + datetime.timedelta(days=1)
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT id, field_name
                FROM projects
                ORDER BY random()
                LIMIT 1
                """)
            cur.execute("SELECT id, field_name FROM projects ORDER BY random() LIMIT 1")
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
                WHERE frequency_id = 2
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


def add_date():
    try:
        week_day = datetime.datetime.today().weekday()
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("""INSERT OR IGNORE INTO dates (date)
                VALUES (date('now','+1 day'))""")
            if week_day not in (4, 5):
                cur.execute("SELECT id FROM tasks WHERE frequency_id IN (1, 6)")
            else:
                cur.execute("SELECT id FROM tasks WHERE frequency_id = 1")
            for result in cur.fetchall():
                cur.execute(f"""INSERT INTO routine (date_id, task_id)
                    VALUES (
                    (SELECT id FROM dates WHERE date = date('now','+1 day')),
                    {result[0]}
                    )
                    """)
        if week_day == 6:
            planning_week()
            funcs.save_logs()
            with sq.connect(config.database) as con:
                cur = con.cursor()
                cur.execute(
                    """INSERT INTO tasks (user_id, project_id, frequency_id, task)
                    VALUES (1, 1, 5, 'Прочитать логи')""")
                cur.execute(
                    f"""INSERT INTO routine (date_id, task_id)
                    VALUES (
                        (SELECT id FROM dates WHERE date = date('now','+1 day')),
                        {cur.lastrowid})
                    """)
    except Exception:
        logging.error("func add_date - error", exc_info=True)


def planning_day():
    try:
        add_date()
        routine_check()
        tasks_tomorrow()
    except Exception:
        logging.error("func planning_day - error", exc_info=True)


def schedule_main():
    try:
        schedule.every().day.at(
            "05:30",
            timezone(config.timezone_my)
            ).do(morning_business)
        schedule.every().day.at(
            "21:00",
            timezone(config.timezone_my)
            ).do(planning_day)

        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception:
        logging.error("func schedule_main - error", exc_info=True)


def access_check(message, call_data):
    try:
        balance = funcs.get_balance()
        if balance >= 1:
            with sq.connect(config.database) as con:
                cur = con.cursor()
                cur.execute("INSERT INTO events (event) VALUES (1)")
                temp = funcs.get_temperature()
                all_weight = funcs.access_weight()
                funcs.socket_client(data_send=f"{call_data.split()[1]};{temp};{int(all_weight)}")
            bot.send_message(
                message.chat.id,
                text=f"Допуск получен:\nбаланс: {balance}\nWeight: {round(all_weight, 2)}")
        else:
            bot.send_message(
                message.chat.id,
                text=f"Допуск НЕ получен:\nбаланс: {balance}")
    except Exception:
        logging.warning(msg="func access_check - error", exc_info=True)


def search_add(message, call_data):
    try:
        data = call_data.split()[1]
        if data == "event":
            def check_event(message):
                data_msg = message.text.strip()
                if len(data_msg.split(";")) == 5:
                    funcs.socket_client(data_send=f"{data}: {data_msg}")
                else:
                    bot.send_message(chat_id=message.chat.id, text="Error")

            funcs.socket_client(data_send="view_people_prof")
            msg = bot.send_message(
                chat_id=message.chat.id,
                text="Введи данные в формате (5) ID_Peo;Dat;Count;Temp;Dist(0/1)"
            )
            bot.register_next_step_handler(message=msg, callback=check_event)

        elif data == "peo_prof":
            def check_peo_prof(message):
                data_msg = message.text.strip()
                data_check = data_msg.split(";")
                if len(data_check) == 2 and len(data_check[1]) == 6:
                    funcs.socket_client(data_send=f"{data}: {data_msg}")
                else:
                    bot.send_message(chat_id=message.chat.id, text="Error")

            funcs.socket_client(data_send="view_people_prof")
            msg = bot.send_message(chat_id=message.chat.id, text="Введи данные в формате ID_Peo;Number")
            bot.register_next_step_handler(message=msg, callback=check_peo_prof)

        elif data == "prof_later":
            def check_prof_later(message):
                data_msg = message.text.strip()
                prof, months = data_msg.split(";")
                if len(prof) == 6 and months.isdigit() and prof.isdigit():
                    funcs.socket_client(data_send=f"{data}: {data_msg}")
                else:
                    bot.send_message(chat_id=message.chat.id, text="Error")

            msg = bot.send_message(chat_id=message.chat.id, text="Введи number_prof;months")
            bot.register_next_step_handler(message=msg, callback=check_prof_later)

    except Exception:
        logging.critical("func 'search_add' - error", exc_info=True)


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
def send_log(message):
    funcs.send_logs(message)


@bot.message_handler(commands=['search'])
def task_completed(message):
    keyboard = types.InlineKeyboardMarkup()
    key_1 = types.InlineKeyboardButton(
        text="Search",
        callback_data='search search;0')
    key_2 = types.InlineKeyboardButton(
        text="Search_a",
        callback_data='search search;1')
    key_3 = types.InlineKeyboardButton(
        text="Search_m",
        callback_data='search mass')
    key_4 = types.InlineKeyboardButton(
        text="Email",
        callback_data='search email')
    key_5 = types.InlineKeyboardButton(
        text="Add ev",
        callback_data='emailer_add event')
    key_6 = types.InlineKeyboardButton(
        text="Add p_pr",
        callback_data='emailer_add peo_prof')
    key_7 = types.InlineKeyboardButton(
        text="Pr later",
        callback_data='emailer_add prof_later')

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
    elif "change_task_success" in call.data:
        change_task_success(call.message, call.data)
    elif "list_tasks" in call.data:
        list_tasks_view(call.message, call.data)
    elif "new_type_field_task" in call.data:
        set_type_field_task(call.message)
    elif "routine_tomorrow" in call.data:
        add_routine_tomorrow(call.message, call.data)
    elif "routine_week" in call.data:
        add_routine_week(call.message, call.data)
    elif "search" in call.data:
        access_check(call.message, call.data)
    elif "emailer_add" in call.data:
        search_add(call.message, call.data)


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
