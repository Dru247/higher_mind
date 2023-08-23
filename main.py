import os
import random
import re
import smtplib
import schedule
import sqlite3 as sq
import telebot
import threading
import time

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from email.mime.text import MIMEText
from pytz import timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


load_dotenv()

options = webdriver.ChromeOptions()

options.add_argument("--no-sandbox")

# for ChromeDriver version 79.0.3945.16 or over
options.add_argument("--disable-blink-features=AutomationControlled")

# background mode
options.add_argument("--headless")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

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


@bot.message_handler(commands=['search'])
def task_completed(message):
    bot.send_message(message.chat.id, 'Старт поиска')
    search_people()
    bot.send_message(message.chat.id, 'Поиск закончен')


def search_people():
    search_db = "people.db"
    search_url = os.getenv('SEARCH_URL')

    def create_db():
        with sq.connect(search_db) as con:
            cur = con.cursor()
            cur.execute("DROP TABLE IF EXISTS people")
            cur.execute("""CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY,
                place TEXT,
                name TEXT,
                age INTEGER,
                hands INTEGER,
                height INTEGER,
                weight INTEGER,
                al TEXT,
                price INTEGER
                )""")


    def get_source_html(url):

        with sq.connect(search_db) as con:
            cur = con.cursor()

            try:
                driver.get(url)
                time.sleep(random.randint(0,3))
                html = driver.page_source
                soup = BeautifulSoup(html, "lxml")
                count_lists = soup.find("div", class_="pagingList").find_all("a")
                count = int(count_lists[-2].text)

                for i in range(count+1):
                    url_new = re.split('index=', url, maxsplit=0)
                    url_new_2 = f'{url_new[0]}index={i}{url_new[1][1:]}'
                    driver.get(url_new_2)
                    time.sleep(random.randint(0,10))
                    html = driver.page_source
                    soup = BeautifulSoup(html, "lxml")        
                    cards = soup.find_all("div", class_="adp_edin_ank")
                    
                    for card in cards:
                        id = card.find("a", class_="metro_title_link").get("href")
                        id_new = int(re.sub(r'\D', '', id))
                        place = card.find("a", class_="metro_title").text
                        name = card.find("a", class_="metro_title_link").text
                        name_new = re.sub(r'\W', '', name)
                        age = card.find("div", class_="txtparam").find("span")
                        age_new = int(re.sub(r'\D', '', str(age)))
                        hands = card.find("div", class_="txtparam").find("span").find_next_sibling().find_next_sibling()
                        hands_new = int(re.sub(r'\D', '', str(hands)))
                        height = card.find("div", class_="txtparam").find_next_sibling().find("span")
                        height_new = int(re.sub(r'\D', '', str(height)))
                        weight = card.find("div", class_="txtparam").find_next_sibling().find("span").find_next_sibling().find_next_sibling()
                        weight_new = int(re.sub(r'\D', '', str(weight)))
                        al = card.find("span", class_="stAuthor").text
                        price = card.find("span", class_="txtpricehour").find_next_sibling().text

                        try:
                            price_new = "".join(price[:6].split())
                            if price_new[-1] != '0':
                                price_new = price_new[:-1]
                            price_new = int(price_new)
                        except Exception as _ex:
                            print(_ex)
                            price_new = 0
                        
                        val = (id_new, place, name_new, age_new, hands_new, height_new, weight_new, al, price_new)

                        try:
                            cur.execute("INSERT INTO people VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", val)
                        
                        except Exception as _ex:
                            print(_ex)

            except Exception as _ex:
                print(_ex)

            finally:
                driver.close()
                driver.quit()


    create_db()
    get_source_html(search_url)


@bot.message_handler(commands=['email'])
def task_completed(message):
    bot.send_message(message.chat.id, 'Введите small, middle или big ')
    bot.register_next_step_handler(message, search)


def search(message):
    db_1 = "people.db"
    search_1 = os.getenv('SEARCH')
    profiles = []
    places_list = []
    

    def send_email(email_data):
        sender = os.getenv("EMAIL_SENDER")
        password = os.getenv("EMAIL_PASSWORD")
        recipient = os.getenv("EMAIL_RECIPIENT")
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = os.getenv("SMTP_PORT")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        msg = MIMEText(str(email_data))
        msg["Subject"] = "Test"

        try:
            # time.sleep(random.randint(0,3))
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        except Exception as _ex:
            print(f"{_ex}")

    def random_output(data):
        for result in random.sample(data, 5):
            send_email(result)


    def places_output(distance):
        with sq.connect(db_1) as con:
            cur = con.cursor()
            cur.execute("SELECT place FROM places WHERE (distance BETWEEN 1 AND ?)", (distance,))
            for row in cur:
                places_list.append(row[0])

    
    def filter(search_data, visit_anks):
        with sq.connect(db_1) as con:
            cur = con.cursor()
            cur.execute(search_1)
            if search_data == 'small':
                places_output(1)
            if search_data == 'middle':
                places_output(2)
            if search_data == 'big':
                places_output(3)
            for result in cur:
                if (result[1] in places_list) and (result[0] not in visit_anks): 
                    profiles.append(result)
        random_output(profiles)


    def visits():
        visit_anks = []
        with sq.connect(db_1) as con:
            cur = con.cursor()
            cur.execute("SELECT number_profile FROM profiles")
            for row in cur:
                visit_anks.append(row[0])
        return visit_anks


    filter(message.text, visits())


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
