# import datetime
import os
import schedule
import sqlite3 as sq
import telebot
import threading
import time

from dotenv import load_dotenv
from pytz import timezone


load_dotenv()

TOKEN = os.getenv('TELEGRAM_TOKEN')
my_id = os.getenv('TELEGRAM_MY_ID')
bot = telebot.TeleBot(TOKEN)
database = "main.db"


def create_db():
    with sq.connect(database) as con:
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_user INTEGER,
            task TEXT,
            status INTEGER
            )""")


@bot.message_handler(commands=['start', 'help', 'commands'])
def start_message(message):
    bot.send_message(message.chat.id, 'Привет! Вводи:\nДля создания задачи: /create_task.\nДля отображения задач: /list_tasks\nЕсли задача выполнена: /task_completed\nЗадать таймер: /reminder')


@bot.message_handler(commands=['create_task'])
def reminder_message(message):
    if message.chat.id == int(my_id):
        bot.send_message(message.chat.id, 'Введи текст задачи')
        bot.register_next_step_handler(message, set_task)
    else:
        bot.send_message(message.chat.id, 'Сорян, бот для избранных ;)')


def set_task(message):
    with sq.connect(database) as con:
        cur = con.cursor()
        cur.execute(f"INSERT INTO tasks (id_user, task, status) VALUES ({message.chat.id}, '{message.text}', {1})")
        bot.send_message(message.chat.id, 'Задача создана')


@bot.message_handler(commands=['list_tasks'])
def list_task_request(message):
        bot.send_message(message.chat.id, 'Введи New или Old')
        bot.register_next_step_handler(message, list_tasks)


def list_tasks(message):
    data_records = {
        "Old": 0,
        "New": 1
    }
    try:
        with sq.connect(database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT * FROM tasks WHERE id_user = {message.chat.id} AND status = {data_records[message.text]}")
            for record in cur:
                bot.send_message(message.chat.id, f"{record[0]}: {record[2]}")
    except:
        bot.send_message(message.chat.id, 'Некорректно')


@bot.message_handler(commands=['task_completed'])
def task_completed(message):
    bot.send_message(message.chat.id, 'Введи ID задачи')
    bot.register_next_step_handler(message, change_task)


def change_task(message):
    try:
        with sq.connect(database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE tasks SET status = {0} WHERE id = {int(message.text)}")
        bot.send_message(message.chat.id, f"Задача с ID {message.text} выполнена")
    except:
        bot.send_message(message.chat.id, 'ID не верен')


@bot.message_handler(commands=['reminder'])
def task_completed(message):
    bot.send_message(message.chat.id, 'Введи дату и время первого напоминания (ЧЧ:ММ)')
    bot.register_next_step_handler(message, make_reminder)


def make_reminder(message):
    def print_tasks():
        with sq.connect(database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT * FROM tasks WHERE id_user = {message.chat.id} AND status = {1}")
            for record in cur:
                bot.send_message(message.chat.id, f"{record[0]}: {record[2]}")

    def timer(message,):
        schedule.every().days.at(message.text, timezone('Europe/Moscow')).do(print_tasks)
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    threading.Thread(target=timer, args=(message,)).start()

    # time_reminder = datetime.datetime.strptime(message.text, '%Y-%m-%d %H:%M:%S')
    #     t_delta = t_reminder - datetime.datetime.now()
    #     time.sleep(t_delta.total_seconds())
    #     reminder_delta = datetime.timedelta(days=1).total_seconds()
    #     while True:
    #         print_tasks()
    #         time.sleep(reminder_delta)

    # threading.Thread(target=timer, args=(time_reminder,)).start()


# @bot.message_handler(commands=['/list_completed'])
# def list_task(message):
#     with sq.connect(database) as con:
#         cur = con.cursor()
#         cur.execute(f"SELECT * FROM tasks WHERE id_user = {message.chat.id} AND status = {1}")
#         for record in cur:
#             bot.send_message(message.chat.id, f"{record[0]}: {record[2]}")



# def list_completed_tasks(message):
#     print(0)
#     with sq.connect(database) as con:
#         cur = con.cursor()
#         print(1)
#         cur.execute(f"SELECT * FROM tasks WHERE status = {0}")
#         print(2)
#         for record in cur:
#             bot.send_message(message.chat.id, f"{record[0]}: {record[2]}")


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


@bot.message_handler(func=lambda message: True)
def handler_all_message(message):
    bot.send_message(message.chat.id, 'Я не понимаю, что вы говорите')


if __name__ == '__main__':
    create_db()
    bot.polling(none_stop=True)
