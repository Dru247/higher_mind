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
keyboard_main.row(*[types.KeyboardButton(cmd) for cmd in commands])


def check_unseen_msgs(number_task):
    try:
        funcs.preparation_emails()
        max_unseen_msgs = 40
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT sum(unseen_status) FROM emails")
            result = cur.fetchone()[0]
            if result < max_unseen_msgs:
                cur.execute(
                    """
                    UPDATE routine SET success = 1
                    WHERE task_id = ?
                    AND date_id = (SELECT id FROM dates WHERE date = date('now'))
                    """,
                    (number_task,)
                )
    except Exception:
        logging.critical(msg="func check_unseen_msgs - error", exc_info=True)


def routine_check():
    try:
        task_unseen_msg = 117
        check_unseen_msgs(task_unseen_msg)
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT routine.id, tasks.task, tasks.id, tasks.frequency_id
                FROM routine
                JOIN tasks ON routine.task_id = tasks.id
                WHERE date_id = (SELECT id FROM dates WHERE date = date('now','-1 day'))
                AND routine.success = 0
                AND task_id != ?
                """,
                (task_unseen_msg,)
            )
            results = cur.fetchall()
        for result in results:
            keys = []
            keyboard = types.InlineKeyboardMarkup()
            keys.append(types.InlineKeyboardButton(
                text="Выполнено",
                callback_data=f"routine_set_status {result[0]};1"))
            keys.append(types.InlineKeyboardButton(
                text="Не выполнено",
                callback_data=f"routine_set_status {result[0]};0"))
            if result[3] == 5:
                keys.append(types.InlineKeyboardButton(
                    text="Задача выполнена",
                    callback_data=f"change_task_success {result[2]}"))
            keyboard.add(*keys)
            bot.send_message(
                config.telegram_my_id,
                text=f"{result[2]}: {result[1]}",
                reply_markup=keyboard
            )
    except Exception:
        logging.critical(msg="func routine_daily_check_2 - error", exc_info=True)


def set_routine_status(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                f"UPDATE routine SET success = ? WHERE id = ?",
                (data[1], data[0])
            )
            cur.execute(
                "SELECT task_id FROM routine WHERE id = ?",
                (data[0],)
            )
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
def add_task(message):
    try:
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT id, field_name FROM projects")
            for record in cur:
                inline_keys.append(
                    types.InlineKeyboardButton(
                        text=record[1],
                        callback_data=f"add_task_project {record[0]}"))
        # inline_keys.append(types.InlineKeyboardButton(
        #                         text='Новый проект',
        #                         callback_data='new_type_field_task'))
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            message.from_user.id,
            text="Выбери проект",
            reply_markup=keyboard)
    except Exception:
        logging.critical("func add_task - error", exc_info=True)


# def set_type_field_task(message):
#     try:
#         bot.send_message(message.chat.id, text="Введи новый тип задач")
#         bot.register_next_step_handler(message, add_type_field_task)
#     except Exception:
#         logging.critical("func set_user - error", exc_info=True)
#
#
# def add_type_field_task(message):
#     try:
#         with sq.connect(config.database) as con:
#             cur = con.cursor()
#             cur.execute(
#                 "INSERT INTO projects (field_name) VALUES (?)",
#                 (message.text,)
#             )
#             bot.send_message(
#                 message.chat.id,
#                 text=f"Новый тип задач ({message.text}) добавлен",
#                 reply_markup=keyboard_main
#             )
#     except Exception:
#         logging.critical("func add_routine - error", exc_info=True)
#         bot.send_message(message.chat.id, 'Некорректно')


def add_task_frequency(message, call_data):
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
                        callback_data=f"add_task_frequency {id_field};{record[0]}"))
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(*inline_keys)
        bot.send_message(
            message.chat.id,
            text="Введи тип задачи",
            reply_markup=keyboard)
    except Exception:
        logging.critical("func add_task_frequency - error", exc_info=True)


def add_task_text(message, data):
    try:
        bot.send_message(message.chat.id, "Введи текст задачи")
        bot.register_next_step_handler(message, lambda m: add_task_final(m, data))
    except Exception:
        logging.critical("func add_task_text - error", exc_info=True)


def add_task_final(message, data):
    task_set = data.split()[1].split(";")
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                f"""
                INSERT INTO tasks (user_id, project_id, frequency_id, task)
                VALUES (
                    (SELECT id FROM users WHERE telegram_id = ?), ?, ?, ?
                )
                """,
                (message.chat.id, task_set[0], task_set[1], message.text)
            )
            last_id = cur.lastrowid
        bot.send_message(message.chat.id, f"Задача №{last_id}: создана")
    except Exception:
        logging.critical("func add_task_final - error", exc_info=True)


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
            callback_data=f"change_task_project {message.text}")
        key_4 = types.InlineKeyboardButton(
            text="Приоритет",
            callback_data=f"change_task_priority {message.text}")
        key_5 = types.InlineKeyboardButton(
            text="Удалить",
            callback_data=f"change_task_remove {message.text}")
        # key_6 = types.InlineKeyboardButton(
        #     text="Выполнить",
        #     callback_data=f"change_task_success {message.text}")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(key_1, key_2, key_3, key_4, key_5)
        bot.send_message(
            chat_id=message.chat.id,
            text="Что меняем?",
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func change_task_set_field - error", exc_info=True)


def change_task_text(message, call_data):
    try:
        data = call_data.split()[1]
        msg = bot.send_message(chat_id=message.chat.id, text="Введи текст задачи")
        bot.register_next_step_handler(message=msg, callback=change_task_set_text, data=data)
    except Exception:
        logging.critical(msg="func change_task_text - error", exc_info=True)


def change_task_set_text(message, data):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                "UPDATE tasks SET task = ? WHERE id = ?",
                (message.text, data)
            )
            bot.send_message(chat_id=message.chat.id, text="Успех")
    except Exception:
        logging.critical(msg="func change_task_set_text - error", exc_info=True)


def change_task_project(message, call_data):
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
                        callback_data=f"change_task_set_project {data};{record[0]}"))
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(*inline_keys)
        bot.send_message(
            message.chat.id,
            text="Введи проект задачи",
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func change_task_project - error", exc_info=True)


def change_task_set_project(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                "UPDATE tasks SET project_id = ? WHERE id = ?",
                (data[1], data[0])
            )
            bot.send_message(chat_id=message.chat.id, text="Успех")
    except Exception:
        logging.critical(msg="func change_task_set_project - error", exc_info=True)


def change_task_frequency(message, call_data):
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
                        callback_data=f"change_task_set_frequency {data};{record[0]}"))
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(*inline_keys)
        bot.send_message(
            message.chat.id,
            text="Введи периодичность задачи",
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func change_task_frequency - error", exc_info=True)


def change_task_set_frequency(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                "UPDATE tasks SET frequency_id = ? WHERE id = ?",
                (data[1], data[0])
            )
        bot.send_message(chat_id=message.chat.id, text="Успех")
    except Exception:
        logging.critical(msg="func change_task_set_frequency - error", exc_info=True)


def change_task_priority(message, call_data):
    try:
        task_id = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            inline_keys = []
            cur.execute("SELECT id, priority FROM priorities")
            result = cur.fetchall()
        for record in result:
            inline_keys.append(
                types.InlineKeyboardButton(
                    text=record[1],
                    callback_data=f"change_task_set_priority {task_id};{record[0]}"
                )
            )
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            message.chat.id,
            text="Выбери приоритет задачи",
            reply_markup=keyboard
        )
    except Exception:
        logging.critical(msg="func change_task_priority - error", exc_info=True)


def change_task_set_priority(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                "UPDATE tasks SET priority_id = ? WHERE id = ?",
                (data[1], data[0])
            )
        bot.send_message(chat_id=message.chat.id, text="Успех")
    except Exception:
        logging.critical(msg="func change_task_set_priority - error", exc_info=True)


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
            cur.execute(
                "UPDATE tasks SET success = 1, datetime_success = datetime('now') WHERE id = ?",
                (task_id,)
            )
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
            cur.execute(
                "SELECT field_name FROM projects WHERE id = ?",
                (project,)
            )
            project_name = cur.fetchone()[0]
            cur.execute(
                """
                SELECT tasks.id, tasks.task, frequencies.name, priorities.priority
                FROM tasks
                JOIN frequencies ON tasks.frequency_id = frequencies.id
                JOIN priorities ON priorities.id = tasks.priority_id
                WHERE project_id = ?
                AND success = 0
                ORDER BY priorities.grade DESC
                """,
                (project,)
            )
            message = MIMEMultipart()
            message["From"] = config.my_email_mailru
            message["To"] = config.my_email_yandex
            message["Subject"] = f'Список задач проекта "{project_name}"'
            data = f"""
                <!DOCTYPE html><html><body><table><caption>{project_name}</caption>
                <thead><tr><th>ID</th><th>Период</th><th>Приоритет</th><th>Задача</th></tr></thead>
                <tbody>
                """
            for row in cur.fetchall():
                data += f"<tr><td>{row[0]}</td><td>{row[2]}</td><td>{row[3]}</td><td>{row[1]}</td></tr>"
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
            cur.execute("""
                SELECT * FROM
                    (SELECT id, task, project_id, priority_id
                    FROM tasks
                    WHERE project_id = 3
                    AND success = 0
                    AND frequency_id = 5
                    AND id NOT IN (
                        SELECT task_id
                        FROM routine
                        WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                    )
                    ORDER BY priority_id DESC, random()
                    LIMIT 2)
                UNION
                SELECT * FROM 
                    (SELECT id, task, project_id, priority_id
                    FROM tasks
                    WHERE project_id = (SELECT project_id FROM week_project ORDER BY id DESC LIMIT 1)
                    AND success = 0
                    AND frequency_id = 5
                    AND id NOT IN (
                        SELECT task_id
                        FROM routine
                        WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                    )
                    ORDER BY priority_id DESC, random()
                    LIMIT 8)
                ORDER BY project_id, priority_id DESC
            """)
            result = cur.fetchall()
        for line in result:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    text='Завтра?',
                    callback_data=f"routine_tomorrow "
                    f"{line[0]};{date.isoformat()}"
                )
            )
            bot.send_message(
                config.telegram_my_id,
                text=f"{line[0]}: {line[1]}",
                reply_markup=keyboard
            )
    except Exception:
        logging.error("func tasks_tomorrow - error", exc_info=True)


def add_routine_tomorrow(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO routine (date_id, task_id)
                VALUES ((SELECT id FROM dates WHERE date = ?), ?)
                """,
                (data[1], data[0])
            )
            bot.send_message(
                message.chat.id,
                text=f"Задача №{data[0]}: добавлена на исполнение")
    except Exception:
        logging.error(msg="func add_routine_tomorrow - error", exc_info=True)


def morning_business():
    try:
        def send_routine(select, text_msg):
            try:
                msg_text = f'ЗАДАЧИ С ТИПОМ "{text_msg}":'
                for line in select:
                    msg_text += f"\n{line[2]};{line[3][0]}|{line[4][0]}: {line[1]}"
                bot.send_message(config.telegram_my_id, text=msg_text)
            except Exception:
                logging.error(msg="func morning_business,send_routine - error", exc_info=True)

        routine_check()
        funcs.preparation_emails()
        temp = funcs.get_temperature()
        bot.send_message(
            config.telegram_my_id,
            # text=f"Баланс: {funcs.get_balance()}\n{funcs.info_check_email()}")
            text=f"Баланс: {funcs.get_balance()}\nТемпература min: {temp[0]}\nТемпература max: {temp[1]}\n{funcs.info_check_email()}")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT routine.id, tasks.task, tasks.id,
                projects.field_name, priorities.priority, priorities.id
                FROM routine
                JOIN tasks ON routine.task_id = tasks.id
                JOIN priorities ON priorities.id = tasks.priority_id
                JOIN projects ON projects.id = tasks.project_id
                WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                AND priorities.id = 3
                ORDER BY priorities.id DESC
            """)
            send_routine(cur.fetchall(), "ФУНДАМЕНТАЛЬНЫЙ")
            cur.execute("""
                SELECT routine.id, tasks.task, tasks.id,
                projects.field_name, priorities.priority, priorities.id
                FROM routine
                JOIN tasks ON routine.task_id = tasks.id
                JOIN priorities ON priorities.id = tasks.priority_id
                JOIN projects ON projects.id = tasks.project_id
                WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                AND tasks.project_id = 4
                AND routine.id NOT IN (
                    SELECT routine.id
                    FROM routine
                    JOIN tasks ON routine.task_id = tasks.id
                    JOIN priorities ON priorities.id = tasks.priority_id
                    WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                    AND priorities.id = 3
                )
                ORDER BY priorities.id DESC
            """)
            send_routine(cur.fetchall(), "ЗОЖ")
            cur.execute("""
                SELECT routine.id, tasks.task, tasks.id,
                projects.field_name, priorities.priority, priorities.id
                FROM routine
                JOIN tasks ON routine.task_id = tasks.id
                JOIN priorities ON priorities.id = tasks.priority_id
                JOIN projects ON projects.id = tasks.project_id
                WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                AND routine.id NOT IN (
                    SELECT routine.id FROM routine
                    JOIN tasks ON routine.task_id = tasks.id
                    JOIN priorities ON priorities.id = tasks.priority_id
                    WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                    AND priorities.id = 3
                )
                AND routine.id NOT IN (
                    SELECT routine.id FROM routine
                    JOIN tasks ON routine.task_id = tasks.id
                    JOIN projects ON projects.id = tasks.project_id
                    WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                    AND tasks.project_id = 4
                )
                ORDER BY priorities.id DESC
            """)
            send_routine(cur.fetchall(), "ВЫПОЛНИТЬ")
        msg = bot.send_message(chat_id=config.telegram_my_id, text="Сколько весишь?")
        bot.register_next_step_handler(message=msg, callback=add_my_weight)
    except Exception:
        logging.error(msg="func morning_business - error", exc_info=True)


def add_my_weight(message):
    try:
        weight = message.text.strip()
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO my_weight (date_id, weight)
                VALUES ((SELECT id FROM dates WHERE date = date('now')), ?)
                """,
                (weight,)
            )
        bot.send_message(
            chat_id=config.telegram_my_id,
            text="OK"
        )
    except Exception:
        logging.error(msg="func add_my_weight - error", exc_info=True)


def get_week_project(date_now):
    try:
        tomorrow = date_now + datetime.timedelta(days=1)
        projects = [1, 2, 4, 5, 6, 8, 10, 11]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT count() FROM week_project")
            count_projects = int(cur.fetchone()[0])
            result = projects[count_projects % len(projects)]
            cur.execute("SELECT id, field_name FROM projects WHERE id = ?", (result,))
            result_project = cur.fetchone()
            cur.execute(
                "INSERT INTO week_project (week, project_id) VALUES (?, ?)",
                (f"{tomorrow.isocalendar()[0]}-{tomorrow.isocalendar()[1]}", result_project[0])
            )
        return result_project[1]
    except Exception:
        logging.error(msg="func get_week_project - error", exc_info=True)


def planning_week():
    try:
        date_now = datetime.date.today()
        bot.send_message(
            config.telegram_my_id,
            text=f"{get_week_project(date_now)} - проект следующей недели"
        )
        week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            for day in range(1, 8):
                cur.execute(f"""
                    INSERT OR IGNORE INTO dates (date)
                    VALUES (date('now','+{day} day'))
                """)
            con.commit()
            cur.execute("SELECT id, tasks.task FROM tasks WHERE frequency_id = 2")
            result = cur.fetchall()
        for line in result:
            keyboard = types.InlineKeyboardMarkup()
            keys = []
            for number, day in enumerate(week):
                date = date_now + datetime.timedelta(days=number + 1)
                key = types.InlineKeyboardButton(
                    text=day,
                    callback_data=f"routine_week {date.isoformat()};{line[0]}")
                keys.append(key)
            keyboard.row(*keys)
            bot.send_message(
                config.telegram_my_id,
                text=f"Запланируй задачу №{line[0]}: {line[1]}",
                reply_markup=keyboard
            )
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
            # funcs.save_logs()
    except Exception:
        logging.error("func add_date - error", exc_info=True)


def planning_day():
    try:
        add_date()
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
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT date FROM vpn WHERE date <= date('now', '-30 day')")
            vpn_check = cur.fetchone()
        if vpn_check is not None:
            bot.send_message(
                message.chat.id,
                text=f"vpn")
        else:
            week_now = datetime.datetime.now().isocalendar()[1]
            with sq.connect(config.database) as con:
                cur = con.cursor()
                cur.execute("SELECT datetime FROM events ORDER BY id DESC LIMIT 1")
                last_date = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT * FROM (
                        SELECT dates.date FROM routine
                        JOIN dates ON routine.date_id = dates.id
                        WHERE routine.task_id = 495
                        AND dates.date != date('now')
                        AND routine.success = 0
                        ORDER BY routine.id DESC
                        LIMIT 1
                    )
                    UNION
                    SELECT * FROM (
                        SELECT dates.date FROM routine
                        JOIN dates ON routine.date_id = dates.id
                        WHERE routine.task_id = 496
                        AND dates.date != date('now')
                        AND routine.success = 0
                        ORDER BY routine.id DESC
                        LIMIT 1
                    )
                    """
                    )
                result = cur.fetchall()
            bad_weeks = [datetime.datetime.fromisoformat(date[0]).isocalendar()[1] for date in result]
            last_week = datetime.datetime.fromisoformat(last_date).isocalendar()[1]
            logging.info(
                f"access_check(): week_now: {week_now}, event_week: {last_week}, bad_week: {bad_weeks}"
            )
            if (week_now != last_week) and (week_now not in bad_weeks) and (week_now-1 not in bad_weeks):
                with sq.connect(config.database) as con:
                    cur = con.cursor()
                    cur.execute("INSERT INTO events (event) VALUES (1)")
                funcs.socket_client(data_send=call_data.split()[1])
                bot.send_message(
                    message.chat.id,
                    text=f"Допуск получен")
            else:
                bot.send_message(
                    message.chat.id,
                    text=f"Допуск НЕ получен")
    except Exception:
        logging.warning(msg="func access_check - error", exc_info=True)


def search_add(message, call_data):
    try:
        data = call_data.split()[1]

        if data == "peo_prof":
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

            def choice_prof_later(message):
                try:
                    number_pr = message.text
                    keyboard = types.InlineKeyboardMarkup()
                    keys = [
                        ("1m", f"emailer_add choice_prof_later {number_pr} 1"),
                        ("3m", f"emailer_add choice_prof_later {number_pr} 2")
                    ]
                    keyboard.add(*[types.InlineKeyboardButton(text=key[0], callback_data=key[1]) for key in keys])
                    bot.send_message(
                        message.chat.id,
                        text="Time",
                        reply_markup=keyboard
                    )
                except Exception:
                    logging.critical(msg="func choice_prof_later - error", exc_info=True)

            msg = bot.send_message(chat_id=message.chat.id, text="Введи number_prof")
            bot.register_next_step_handler(message=msg, callback=choice_prof_later)

        elif data == "choice_prof_later":
            prof, time_msg = call_data.split()[2:]
            funcs.socket_client(data_send=f"prof_later: {prof};{time_msg}")

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
        callback_data='search search')
    key_2 = types.InlineKeyboardButton(
        text="p_pr",
        callback_data='emailer_add peo_prof')
    key_3 = types.InlineKeyboardButton(
        text="pr_later",
        callback_data='emailer_add prof_later')
    keyboard.add(key_1, key_2, key_3)
    bot.send_message(
        message.from_user.id,
        text="What we will do?",
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if "add_task_project" in call.data:
        add_task_frequency(call.message, call.data)
    elif "add_task_frequency" in call.data:
        add_task_text(call.message, call.data)
    elif "routine_set_status" in call.data:
        set_routine_status(call.message, call.data)
    elif "change_task_text" in call.data:
        change_task_text(call.message, call.data)
    elif "change_task_project" in call.data:
        change_task_project(call.message, call.data)
    elif "change_task_set_project" in call.data:
        change_task_set_project(call.message, call.data)
    elif "change_task_frequency" in call.data:
        change_task_frequency(call.message, call.data)
    elif "change_task_set_frequency" in call.data:
        change_task_set_frequency(call.message, call.data)
    elif "change_task_priority" in call.data:
        change_task_priority(call.message, call.data)
    elif "change_task_set_priority" in call.data:
        change_task_set_priority(call.message, call.data)
    elif "change_task_remove" in call.data:
        change_task_remove(call.message, call.data)
    elif "change_task_success" in call.data:
        change_task_success(call.message, call.data)
    elif "list_tasks" in call.data:
        list_tasks_view(call.message, call.data)
    # elif "new_type_field_task" in call.data:
    #     set_type_field_task(call.message)
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
        add_task(message)
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
