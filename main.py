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


logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a",
                    format="%(asctime)s %(levelname)s %(message)s")

bot = telebot.TeleBot(config.telegram_token)

commands = ["Создать задание",
            "Выполнить задание",
            "Список заданий",
            "Добавить рутину"
        ]

keyboard_main = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)

item_1=types.KeyboardButton(commands[0])
item_2=types.KeyboardButton(commands[1])
item_3=types.KeyboardButton(commands[2])
item_4=types.KeyboardButton(commands[3])
keyboard_main.row(item_1, item_2, item_3, item_4)


def create_db():
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            telegram_id INTEGER UNIQUE,
            datetime_creation DEFAULT CURRENT_TIMESTAMP
            )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS task_field_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_name TEXT
            )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_user INTEGER,
            task_field_type INTEGER DEFAULT NULL,
            task TEXT,
            status INTEGER DEFAULT 1,
            datetime_creation DEFAULT CURRENT_TIMESTAMP,
            datetime_completion TEXT,
            FOREIGN KEY (task_field_type) REFERENCES task_field_types (field_name)
            )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user INTEGER,
            email TEXT UNIQUE,
            unseen_status INTEGER,
            FOREIGN KEY (user) REFERENCES users (id)
            )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS routine_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT
            )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS routine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user INTEGER,
            routine_type INTEGER,
            date TEXT,
            success INTEGER DEFAULT 1,
            FOREIGN KEY (user) REFERENCES users (id),
            FOREIGN KEY (routine_type) REFERENCES routine_types (id)
            )""")
        

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, f'Привет! Напиши имя')
    bot.register_next_step_handler(message, set_user)


@bot.message_handler(commands=['help', 'commands'])
def start_message(message):
    bot.send_message(message.chat.id, f'Привет! Задать таймер: /reminder', reply_markup  = keyboard_main)


@bot.message_handler(commands=['email'])
def task_completed(message):
    keyboard = types.InlineKeyboardMarkup()
    key_1 = types.InlineKeyboardButton(text="Start search", callback_data='search search')
    key_2= types.InlineKeyboardButton(text="Email", callback_data='search email')
    keyboard.add(key_1, key_2)
    bot.send_message(message.from_user.id, text="What we will do?", reply_markup=keyboard)


@bot.message_handler(content_types=['text'])
def take_text(message):
    if message.text.lower() == commands[0].lower():
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT id, field_name FROM task_field_types")
            for record in cur:
                inline_keys.append(types.InlineKeyboardButton(text=record[1], callback_data=f"task_field_type {record[0]}"))
        inline_keys.append(types.InlineKeyboardButton(text='Новый тип заданий', callback_data='new_type_field_task'))
        keyboard = types.InlineKeyboardMarkup()
        for key in inline_keys:
            keyboard.add(key)
        bot.send_message(message.from_user.id, text="Введи тип задания", reply_markup=keyboard)
    elif message.text.lower() == commands[1].lower():
        bot.send_message(message.chat.id, 'Введи ID задачи')
        bot.register_next_step_handler(message, change_task)
    elif message.text.lower() == commands[2].lower():
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT id, field_name FROM task_field_types")
            for record in cur:
                inline_keys.append(types.InlineKeyboardButton(text=record[1], callback_data=f"list_task_type {record[0]}"))
        keyboard = types.InlineKeyboardMarkup()
        for key in inline_keys:
            keyboard.add(key)
        bot.send_message(message.from_user.id, text="Какой тип заданий отобразить?", reply_markup=keyboard)
    elif message.text.lower() == commands[3].lower():
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT id, name FROM routine_types")
            for record in cur:
                inline_keys.append(types.InlineKeyboardButton(text=record[1], callback_data=f"routine_type {record[0]}"))
        keyboard = types.InlineKeyboardMarkup()
        inline_keys.append(types.InlineKeyboardButton(text='Новый тип рутины', callback_data='new_type_routine'))
        for key in inline_keys:
            keyboard.add(key)
        bot.send_message(message.from_user.id, text="Введи тип рутины", reply_markup=keyboard)
    else:
        logging.warning(f"func take_text: not understend question: {message.text}")
        bot.send_message(message.chat.id, 'Я не понимаю, что вы говорите')


@bot.callback_query_handler(func=lambda call:True)
def callback_query(call):
    if "task_field_type" in call.data:
        set_task(call.message, call.data)
    elif "list_task_type" in call.data:
        list_tasks(call.message, call.data)
    elif call.data == "new_type_routine":
        set_type_routine(call.message)
    elif "routine_type" in call.data:
        set_routine(call.message, call.data)
    elif "routine_set_status" in call.data:
        set_routine_status(call.message, call.data)
    elif "search" in call.data:
        access_check(call.message, call.data)
    elif "new_type_field_task" in call.data:
        set_type_field_task(call.message)


# routine
def set_type_routine(message):
    bot.send_message(message.chat.id, text="Введи новый тип рутины")
    bot.register_next_step_handler(message, add_routine_type)


def add_routine_type(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"INSERT INTO routine_types(name) VALUES('{message.text}')")
            bot.send_message(message.chat.id, text=f"Новый тип рутины ({message.text}) добавлен", reply_markup  = keyboard_main)
        
    except:
        logging.critical("func add_routine - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


def set_routine(message, call_data):
    routine_type = call_data.split(" ")[1] 
    bot.send_message(message.chat.id, text="Введи дату (ГГГГ-ММ-ДД)")
    bot.register_next_step_handler(message, lambda m: add_routine(m, routine_type))
    

def add_routine(message, routine_type):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"INSERT INTO routine(user, routine_type, date) VALUES((SELECT id FROM users WHERE telegram_id = {message.chat.id}), {routine_type}, '{message.text}')")
            bot.send_message(message.chat.id, text=f"Новая рутина ({message.text}) добавлена", reply_markup  = keyboard_main)
        
    except:
        logging.warning("func set_routine - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


def routine_daily_check():
    try:
        date_yesterday = datetime.date.today() - datetime.timedelta(days=1)
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT id, (SELECT name FROM routine_types WHERE routine.routine_type = routine_types.id), date FROM routine WHERE date = '{date_yesterday}' AND success = {1}")
            results = cur.fetchall()
            if results:
                logging.info(f"func routine_daily_check: exist daily routine ({results})")
                for result in results:
                    routine_id = result[0]
                    keyboard = types.InlineKeyboardMarkup()
                    key_1 = types.InlineKeyboardButton(text='Выполнена', callback_data=f"routine_set_status {routine_id}0")
                    key_2= types.InlineKeyboardButton(text='Не выполнена', callback_data=f"routine_set_status {routine_id}1")
                    keyboard.add(key_1, key_2)
                    bot.send_message(config.telegram_my_id, text=f"Рутина {result[1]} {result[2]}", reply_markup=keyboard)
            else:
                logging.info(f"func routine_daily_check: not exist daily routine ({results})")
                bot.send_message(config.telegram_my_id, text=f"Вчера рутин не было")
    except:
        logging.critical("func routine_daily_check - error", exc_info=True)
        bot.send_message(config.telegram_my_id, text="Некорректно")


def set_routine_status(message, call_data):
    data = call_data.split(" ")
    routine_status = int(data[1][1])
    routine_id = data[1][0]
    if routine_status == 0:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE routine SET success = {routine_status} WHERE id = {routine_id}")
        bot.send_message(message.chat.id, f"Рутина выполнена")
    else:
        logging.info(f"routine id={routine_id} unsuccess, status={routine_status}")
        bot.send_message(message.chat.id, 'Очень жаль, что ты не выполнил рутину...')


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


def set_task(message, call_data):
    try:
        set_type_field = call_data.split(" ")[1] 
        bot.send_message(message.chat.id, text="Введи текст задачи")
        bot.register_next_step_handler(message, lambda m: add_task(m, set_type_field))
    except:
        logging.critical("func set_task - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


def add_task(message, set_type_field):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"""INSERT INTO tasks (id_user, task_field_type, task)
                        VALUES ((SELECT id FROM users WHERE telegram_id = {message.chat.id}), {set_type_field}, '{message.text}')
                        """)
            bot.send_message(message.chat.id, 'Задача создана')
    except:
        logging.critical("func add_task - error", exc_info=True)
        bot.send_message(message.chat.id, 'Некорректно')


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


def change_task(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            time_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(f"UPDATE tasks SET status = {0}, datetime_completion = '{time_now}' WHERE id = {int(message.text)}")
        bot.send_message(message.chat.id, f"Задача с ID {message.text} выполнена")
    except:
        logging.warning("func change_task - error", exc_info=True)
        bot.send_message(message.chat.id, 'ID не верен')


def access_check(message, call_data):
    try:
        date_now = datetime.date.today()
        date_week = date_now - datetime.timedelta(days=7)
    
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT EXISTS(SELECT success FROM routine WHERE (date BETWEEN '{date_week}' AND '{date_now}') AND success = {1})")
            status = int(cur.fetchall()[0][0])
            if status == 0:
                logging.info(f"access_check: access successful: {status}")
                bot.send_message(message.chat.id, text="Допуск получен")
                socket_client(config.socket_server, config.socket_port, config.coding, call_data.split(" ")[1])
            else:
                logging.info(f"access_check: access unsuccessful: {status}")
                bot.send_message(message.chat.id, text="Допуск не получен")
    except:
        logging.warning("func access_check - error", exc_info=True)
        bot.send_message('Некорректно')


@bot.message_handler(commands=['reminder'])
def task_completed(message):
    bot.send_message(message.chat.id, 'Введи дату и время первого напоминания (ЧЧ:ММ)')
    bot.register_next_step_handler(message, make_reminder)


def make_reminder(message):
    def print_tasks():
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT * FROM tasks WHERE id_user = {message.chat.id} AND status = {1}")
            for record in cur:
                bot.send_message(message.chat.id, f"{record[0]}: {record[2]}")

    def timer(message,):
        schedule.every().days.at(message.text, timezone(config.timezone_my)).do(print_tasks)
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    threading.Thread(target=timer, args=(message,)).start()

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


def socket_client(server, port, coding, data_send):
    sock = socket.socket()
    sock.connect((server, port))
    sock.send(data_send.encode(coding))
    # data = sock.recv(1024)
    # print(data.decode(coding))
    sock.close()


def daily_schedule():
    # schedule.every().hour.until(datetime.timedelta(hours=13)).do(preparation_emails)
    preparation_emails()
    routine_daily_check()


def schedule_bigger():
    schedule.every().day.at(config.work_day_start, timezone(config.timezone_my)).do(daily_schedule)
    logging.info(f"Schedule 'every_day' starts")

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
    #     bot.send_message(chat_id, 'Время получить ваше напоминание "{}"!'.format(reminder_name))


if __name__ == '__main__':
    create_db()
    threading.Thread(target=schedule_bigger).start()
    bot.polling(none_stop=True)
