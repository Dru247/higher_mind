import config
import datetime
import logging
import imaplib
import schedule
import socket
import sqlite3 as sq
import telebot
import threading
import time

from pytz import timezone
from telebot import types


logging.basicConfig(
    level=logging.INFO,
    filename="logs.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s")

bot = telebot.TeleBot(config.telegram_token)

commands = ["Создать задание",
            "Список заданий"]

keyboard_main = types.ReplyKeyboardMarkup(resize_keyboard=True)

item_1 = types.KeyboardButton(commands[0])
item_2 = types.KeyboardButton(commands[1])
keyboard_main.row(item_1, item_2)


# routine
def routine_check():
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""SELECT routine.id, task
                FROM routine
                JOIN tasks ON routine.task_id = tasks.id
                WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                AND success = {0}
                """)
            results = cur.fetchall()
            if results:
                logging.info(f"func routine_daily_check_2: exist daily routine ({results})")
                for result in results:
                    routine_id = result[0]
                    keyboard = types.InlineKeyboardMarkup()
                    key_1 = types.InlineKeyboardButton(text='Выполнено', callback_data=f"routine_set_status {routine_id}1")
                    key_2 = types.InlineKeyboardButton(text='Не выполнено', callback_data=f"routine_set_status {routine_id}0")
                    keyboard.add(key_1, key_2)
                    bot.send_message(config.telegram_my_id, text=f"Задание: {result[1]}", reply_markup=keyboard)
            else:
                logging.info(f"func routine_daily_check_2: not exist daily routine ({results})")
                bot.send_message(config.telegram_my_id, text=f"Сегодня заданий не было")
    except:
        logging.critical("func routine_daily_check_2 - error", exc_info=True)
        bot.send_message(config.telegram_my_id, text="Некорректно")


def set_routine_status(message, call_data):
    data = call_data.split(" ")
    routine_status = int(data[1][1])
    routine_id = data[1][0]
    if routine_status == 1:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE routine SET success = {routine_status} WHERE id = {routine_id}")
        bot.send_message(message.chat.id, f"Задание выполнено")
    else:
        logging.info(f"routine id={routine_id} unsuccess, status={routine_status}")
        bot.send_message(message.chat.id, 'Очень жаль, что ты не выполнил задание...')


# user
def set_user(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"INSERT INTO users (first_name, telegram_id) VALUES ('{message.text}', {message.chat.id})")
            bot.send_message(message.chat.id, 'Приятно познакомиться', reply_markup  = keyboard_main)
    
    except:
        logging.warning("func set_user - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


# tasks
def set_type_field_task(message):
    bot.send_message(message.chat.id, text="Введи новый тип заданий")
    bot.register_next_step_handler(message, add_type_field_task)


def add_type_field_task(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"INSERT INTO task_field_types(field_name) VALUES('{message.text}')")
            bot.send_message(message.chat.id, text=f"Новый тип заданий ({message.text}) добавлен", reply_markup  = keyboard_main)
        
    except:
        logging.critical("func add_routine - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


#!!!!!!!!!
def set_task(message, call_data):
    try:
        set_type_field = call_data.split()[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("INSERT id, name FROM task_frequency_types")
        bot.send_message(message.chat.id, text="Введи текст задачи")
        bot.register_next_step_handler(message, lambda m: add_task(m, set_type_field))
    except:
        logging.critical("func set_task - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


# need to add question about frequency_type
def add_task(message, set_type_field):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""INSERT INTO tasks (id_user, task_field_type, frequency_type, task)
                        VALUES ((SELECT id FROM users WHERE telegram_id = {message.chat.id}), {set_type_field}, {5}, '{message.text}')
                        """)
            bot.send_message(message.chat.id, 'Задача создана')
    except:
        logging.critical("func add_task - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')

# need to add question about frequency_type
def list_tasks(message, call_data):
    logging.info(f"LIST TASK {call_data}")
    try:
        task_type = call_data.split(" ")[1]
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT id, task FROM tasks WHERE id_user = (SELECT id FROM users WHERE telegram_id = {message.chat.id}) AND status = 1 AND task_field_type = {task_type}")
            for id, text in cur:
                bot.send_message(message.chat.id, f"{id}: {text}")
    except:
        logging.warning("func list_tasks - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


def access_check(message, call_data):
    try:    
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT id FROM routine WHERE date_id BETWEEN (SELECT id FROM dates WHERE date = date('now','-8 day')) AND (SELECT id FROM dates WHERE date = date('now','-1 day')) AND success = {0}")
            result = cur.fetchone()
            if result is None:
                logging.info(f"access_check: access successful: {result}")
                bot.send_message(message.chat.id, text="Допуск получен")
                socket_client(config.socket_server, config.socket_port, config.coding, call_data.split(" ")[1])
            else:
                logging.info(f"access_check: access unsuccessful: {result}")
                bot.send_message(message.chat.id, text="Допуск не получен")

    except:
        logging.warning("func access_check - error", exc_info=True)
        bot.send_message(message.chat.id, text="Некорректно")


def search_add(message, call_data):
    data = call_data.split()
    if data[1] == "people":
        bot.send_message(
            message.chat.id,
            text = "Введи данные в формате (П.И.Д.С.А.М.Т.ВУсСвВЛГрПМКАлААм(12)(8))"
            )
        bot.register_next_step_handler(message, lambda m: socket_client(config.socket_server, config.socket_port, config.coding, f"add_new: {m.text}"))
    elif data[1] == "event":
        bot.send_message(
            message.chat.id,
            text = "Введи данные в формате (Ч.Д.С)"
            )
        bot.register_next_step_handler(message, lambda m: socket_client(config.socket_server, config.socket_port, config.coding, f"add_event: {m.text}"))


# Email unseen messages reminder
def preparation_emails():
    emails = [
        (config.imap_server_mailru, config.my_email_mailru, config.password_my_email_mailru),
        (config.imap_server_yandex, config.my_email_yandex, config.password_my_email_yandex),
        (config.imap_server_gmail, config.my_email_gmail, config.password_my_email_gmail)
    ]

    for imap_server, email_login, email_password in emails:
        check_email(imap_server, email_login, email_password)


def check_email(imap_server, email_login, email_password):
    try:
        mailBox = imaplib.IMAP4_SSL(imap_server)
        mailBox.login(email_login, email_password)
        mailBox.select()
        unseen_msg = mailBox.uid('search', "UNSEEN", "ALL")
        id_unseen_msgs = unseen_msg[1][0].decode("utf-8").split(" ")
        if id_unseen_msgs:
            bot.send_message(
                config.telegram_my_id,
                f"На почте {email_login} есть непрочитанные письма, в кол-ве {len(id_unseen_msgs)} шт."
                )
            logging.info(f"{email_login} has unseen messages")
        else:
            logging.info(f"{email_login} doesn't have unseen messages")

    except Exception:
        logging.error(f"func check email - error", exc_info=True)
        
    finally:
        mailBox.close()
        mailBox.logout()


def add_date():
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute("SELECT id FROM tasks WHERE frequency_type = 1")
        for result in cur.fetchall():
            cur.execute(f"INSERT INTO routine (date_id, task_id) VALUES ((SELECT id FROM dates WHERE date = date('now','+1 day')), {result[0]})")


def tasks_tomorrow():
    try:
        date = datetime.date.today() + datetime.timedelta(days=1)
        with sq.connect(config.database) as con:
            results = []
            cur = con.cursor()
            cur.execute("""SELECT id, task FROM tasks
                WHERE id NOT IN (SELECT task_id FROM routine
                WHERE success = 1 AND task_field_type = 1)
                AND frequency_type = 5
                ORDER BY random()
                LIMIT 5
                """)
            for result in cur.fetchall():
                results.append(result)
            cur.execute("""SELECT id, task FROM tasks
                WHERE id NOT IN (SELECT task_id FROM routine
                WHERE success = 1 AND task_field_type = 2)
                AND frequency_type = 5        
                ORDER BY random()
                LIMIT 3
                """)
            for result in cur.fetchall():
                results.append(result)
            cur.execute("""SELECT id, task FROM tasks
                WHERE id NOT IN (SELECT task_id FROM routine
                WHERE success = 1 AND task_field_type = 3)
                AND frequency_type = 5
                ORDER BY random()
                LIMIT 2
                """)
            for result in cur.fetchall():
                results.append(result)
            cur.execute("""SELECT id, task FROM tasks
                WHERE id NOT IN (SELECT task_id FROM routine
                WHERE success = 1 AND task_field_type = 4)
                AND frequency_type = 5
                ORDER BY random()
                LIMIT 2
                """)
            for result in cur.fetchall():
                results.append(result)

            for result in results:
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton(
                    text='Завтра?',
                    callback_data=f"routine_tomorrow {result[0]};{date.isoformat()}"))
                bot.send_message(
                    config.telegram_my_id,
                    text=result[1],
                    reply_markup=keyboard)

    except Exception:
        logging.error(f"func tasks_tomorrow - error", exc_info=True)    


def add_routine_tommorow(message, call_data):
    try:
        data = call_data.split()[1].split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"INSERT INTO routine (date_id, task_id) VALUES ((SELECT id FROM dates WHERE date = '{data[1]}'), {data[0]})")
            bot.send_message(
                message.chat.id,
                text=f"Задача ID={data[0]} добавлена на исполнение")
    except Exception:
        logging.error(f"func add_routine_tommorow - error", exc_info=True)  


def socket_client(server, port, coding, data_send):
    sock = socket.socket()
    sock.connect((server, port))
    sock.send(data_send.encode(coding))
    sock.close()


def morning_business():
    preparation_emails()
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute("""SELECT routine.id, task FROM routine
                    JOIN tasks ON routine.task_id = tasks.id  
                    WHERE date_id = (SELECT id FROM dates WHERE date = date('now'))
                    """)
        bot.send_message(config.telegram_my_id, text=f"Сегодня у тебя следующие задания:")
        for result in cur:
            bot.send_message(config.telegram_my_id, text=f"{result[1]}")


def planning_day():
    add_date()
    routine_check()
    tasks_tomorrow()


def planning_week():
    try:
        week = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
        date_now = datetime.date.today()
        with sq.connect(config.database) as con:
            cur = con.cursor()
            for day in range(1, 8):
                cur.execute(f"INSERT OR IGNORE INTO dates VALUES (NULL, date('now','+{day} day'))")
            cur.execute("""SELECT id, tasks.task
                FROM tasks
                WHERE frequency_type = 2
                """)        
            for result in cur.fetchall():
                keyboard = types.InlineKeyboardMarkup()
                keys = []
                for number, day in enumerate(week):
                    date = date_now + datetime.timedelta(days = number + 1)
                    key = types.InlineKeyboardButton(
                        text=day,
                        callback_data=f"routine_week {date.isoformat()};{result[0]};{result[1]}")
                    keys.append(key)
                keyboard.row(*keys)
                bot.send_message(
                    config.telegram_my_id,
                    text=f"Запланируй на следую неделю {result[1]}:",
                    reply_markup=keyboard)
    except Exception:
        logging.error(f"func planning_week - error", exc_info=True)


def add_routine_week(message, call_data):
    try:
        data = call_data.split()[1]
        data = data.split(";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""INSERT INTO routine (date_id, task_id)
                VALUES ((SELECT id FROM dates WHERE date = {data[0]}), {data[1]})""")
        bot.send_message(
            message.chat.id,
            text=f"{data[2]} запланировано на {data[0]}")
    except Exception:
        logging.error(f"func add_routine_week - error", exc_info=True)


def schedule_main():
    schedule.every().day.at(
        "07:00",
        timezone(config.timezone_my)
        ).do(morning_business)
    schedule.every().day.at("21:30", timezone(config.timezone_my)).do(planning_day)
    schedule.every().sunday.at("18:00", timezone(config.timezone_my)).do(planning_week)
    logging.info("Schedule 'every_day' starts")

    while True:
        schedule.run_pending()
        time.sleep(1)


def reminder_message(message):
    pass
    # @bot.message_handler(commands=['reminder'])
    # def reminder_message(message):
    #     bot.send_message(message.chat.id, 'Введите текст напоминания')
    #     bot.register_next_step_handler(message, set_reminder_name)


    # def set_reminder_name(message):
    #     user_data = {}
    #     user_data[message.chat.id] = {'reminder_name': message.text}
    #     bot.send_message(message.chat.id, 'Введите дату и время, когда хотите получить напоминание в формате ГГГГ-ММ-ДД чч:мм:сс')
    #     bot.register_next_step_handler(message, reminder_set, user_data)

    # def reminder_set(message, user_data):
    #     try:
    #         reminder_time = datetime.datetime.strptime(message.text, '%Y-%m-%d %H:%M:%S')
    #         now = datetime.datetime.now()
    #         delta = reminder_time - now
    #         if delta.total_seconds() <= 0:
    #             bot.send_message(message.chat.id, 'Вы ввели прошедшую дату, попробуйте ещё раз')
    #         else:
    #             reminder_name = user_data[message.chat.id]['reminder_name']
    #             bot.send_message(message.chat.id, 'Напоминание {} установлено на {}.'.format(reminder_name, reminder_time))
    #             reminder_time = threading.Timer(delta.total_seconds(), send_reminder, [message.chat.id, reminder_name])
    #             reminder_time.start()
    #     except ValueError:
    #         bot.send_message(message.chat.id, 'Вы ввели неверный формат даты и времени, попробуйте ещё раз')

    # def send_reminder(chat_id, reminder_name):
    #     bot.send_message(chat_id,
    #           'Время получить ваше напоминание "{}"!'.format(reminder_name))


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


@bot.message_handler(commands=['search'])
def task_completed(message):
    keyboard = types.InlineKeyboardMarkup()
    key_1 = types.InlineKeyboardButton(
        text="Start search",
        callback_data='search search')
    key_2 = types.InlineKeyboardButton(
        text="Email",
        callback_data='search email')
    key_3 = types.InlineKeyboardButton(
        text="Add people",
        callback_data='emailer_add people')
    key_4 = types.InlineKeyboardButton(
        text="Add event",
        callback_data='emailer_add event')
    
    keyboard.add(key_1, key_2, key_3, key_4)
    bot.send_message(
        message.from_user.id,
        text="What we will do?",
        reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if "task_field_type" in call.data:
        set_task(call.message, call.data)
    elif "list_task_type" in call.data:
        list_tasks(call.message, call.data)
    elif "routine_set_status" in call.data:
        set_routine_status(call.message, call.data)
    elif "search" in call.data:
        access_check(call.message, call.data)
    elif "new_type_field_task" in call.data:
        set_type_field_task(call.message)
    elif "emailer_add" in call.data:
        search_add(call.message, call.data)
    elif "routine_tomorrow" in call.data:
        add_routine_tommorow(call.message, call.data)
    elif "routine_week" in call.data:
        add_routine_week(call.message, call.data)


@bot.message_handler(content_types=['text'])
def take_text(message):
    if message.text.lower() == commands[0].lower():
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT id, field_name FROM task_field_types")
            for record in cur:
                inline_keys.append(
                    types.InlineKeyboardButton(
                        text=record[1],
                        callback_data=f"task_field_type {record[0]}"))
        inline_keys.append(types.InlineKeyboardButton(
                                text='Новый тип заданий',
                                callback_data='new_type_field_task'))
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(*inline_keys)
        bot.send_message(
            message.from_user.id,
            text="Введи тип задания",
            reply_markup=keyboard)
    elif message.text.lower() == commands[1].lower():
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute("SELECT id, field_name FROM task_field_types")
            for record in cur:
                inline_keys.append(
                    types.InlineKeyboardButton(
                        text=record[1],
                        callback_data=f"list_task_type {record[0]}"))
        keyboard = types.InlineKeyboardMarkup()
        for key in inline_keys:
            keyboard.add(key)
        bot.send_message(
            message.from_user.id,
            text="Какой тип заданий отобразить?",
            reply_markup=keyboard)
    else:
        logging.warning(
            f"func take_text: not understend question: {message.text}")
        bot.send_message(message.chat.id, 'Я не понимаю, к сожалению')


if __name__ == '__main__':
    threading.Thread(target=schedule_main).start()
    bot.polling(none_stop=True)
