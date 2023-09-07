import config
import datetime
import logging
import imaplib
import os
import random
import re
import smtplib
import schedule
import shutil
import sqlite3 as sq
import telebot
import threading
import time

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pytz import timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from telebot import types
from webdriver_manager.chrome import ChromeDriverManager


load_dotenv()

logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a",
                    format="%(asctime)s %(levelname)s %(message)s")

options = webdriver.ChromeOptions()

options.add_argument("--no-sandbox")

# for ChromeDriver version 79.0.3945.16 or over
options.add_argument("--disable-blink-features=AutomationControlled")

# background mode
options.add_argument("--headless")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

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
        cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_user INTEGER,
            task TEXT,
            status INTEGER,
            datetime_creation DEFAULT CURRENT_TIMESTAMP,
            datetime_completion TEXT
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
    key_small = types.InlineKeyboardButton(text='Близко', callback_data='place_small')
    key_middle= types.InlineKeyboardButton(text='Средне', callback_data='place_middle')
    key_big= types.InlineKeyboardButton(text='Далеко', callback_data='place_big')
    keyboard.add(key_small, key_middle, key_big)
    bot.send_message(message.from_user.id, text="Какое расстояние?", reply_markup=keyboard)


@bot.message_handler(commands=['search'])
def task_completed(message):
    bot.send_message(message.chat.id, 'Старт поиска')
    search_people()
    bot.send_message(message.chat.id, 'Поиск закончен')


@bot.message_handler(content_types=['text'])
def send_text(message):
    if message.text.lower() == commands[0].lower():
        if message.chat.id == int(config.telegram_my_id):
            bot.send_message(message.chat.id, 'Введи текст задачи')
            bot.register_next_step_handler(message, set_task)
        else:
            bot.send_message(message.chat.id, 'Сорян, бот для избранных ;)')
    elif message.text.lower() == commands[1].lower():
        bot.send_message(message.chat.id, 'Введи ID задачи')
        bot.register_next_step_handler(message, change_task)
    elif message.text.lower() == commands[2].lower():
        keyboard = types.InlineKeyboardMarkup()
        key_new = types.InlineKeyboardButton(text='Не выполненные', callback_data='tasks_new')
        key_old= types.InlineKeyboardButton(text='Выполненные', callback_data='tasks_old')
        keyboard.add(key_new, key_old)
        bot.send_message(message.from_user.id, text="Какие задания отобразить?", reply_markup=keyboard)
    elif message.text.lower() == commands[3].lower():
        inline_keys = []
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT id, name FROM routine_types")
            for record in cur:
                inline_keys.append(types.InlineKeyboardButton(text=record[1], callback_data=f"routine_type: {record[0]}"))
        keyboard = types.InlineKeyboardMarkup()
        inline_keys.append(types.InlineKeyboardButton(text='Новый тип рутины', callback_data='new_type_routine'))
        for key in inline_keys:
            keyboard.add(key)
        bot.send_message(message.from_user.id, text="Введи тип рутины", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call:True)
def callback_query(call):
    if call.data == "tasks_new":
        list_tasks(call.message, task_status="1")
    elif call.data == "tasks_old":
        list_tasks(call.message, task_status="0")
    elif call.data == "place_small":
        access_check(call.message, place=1)
    elif call.data == "place_middle":
        access_check(call.message, place=2)
    elif call.data == "place_big":
        access_check(call.message, place=3)
    elif call.data == "new_type_routine":
        set_type_routine(call.message)
    elif "routine_type:" in call.data:
        set_routine(call.message, call.data)
    elif "routine_set_status" in call.data:
        set_routine_status(call.message, call.data)


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
        logging.warning("func add_routine - error", exc_info=True)
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
            cur.execute(f"SELECT id, (SELECT name FROM routine_types WHERE routine.id = routine_types.id), date FROM routine WHERE date = '{date_yesterday}' AND success = {1}")
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
        logging.warning("func routine_daily_check - error", exc_info=True)
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
def set_task(message):
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute(f"INSERT INTO tasks (id_user, task, status) VALUES ({message.chat.id}, '{message.text}', {1})")
        bot.send_message(message.chat.id, 'Задача создана')


def list_tasks(message, task_status):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"SELECT * FROM tasks WHERE id_user = {message.chat.id} AND status = {task_status}")
            for record in cur:
                bot.send_message(message.chat.id, f"{record[0]}: {record[2]}")
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
                            logging.warning("Price not valid", exc_info=True)
                            price_new = 0
                        
                        val = (id_new, place, name_new, age_new, hands_new, height_new, weight_new, al, price_new)

                        try:
                            cur.execute("INSERT INTO people VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", val)
                        
                        except Exception as _ex:
                            logging.warning("INSERT INTO people - error", exc_info=True)

            except Exception as _ex:
                logging.critical("func get_source_html - error", exc_info=True)

            # finally:
            #     driver.close()
            #     driver.quit()


    create_db()
    get_source_html(search_url)


def access_check(message, place):
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
                search(message, place)
            else:
                logging.info(f"access_check: access unsuccessful: {status}")
                bot.send_message(message.chat.id, text="Допуск не получен")
    except:
        logging.warning("func access_check - error", exc_info=True)
        bot.send_message('Некорректно')


def search(message, place):
    bot.send_message(message.chat.id, 'Старт формирования сообщений')
    search_1 = os.getenv('SEARCH')
    profiles = []
    places_list = []
    

    def send_email(email_data):
        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
        server.starttls()

        email_text = ""
        for text in email_data:
            email_text += f"{text}: {email_data[text]}\n"
        message = MIMEMultipart()
        message["From"] = config.sender_email
        message["To"] = config.recipient_email
        message["Subject"] = email_data['Мт']
        part = MIMEText(email_text)
        message.attach(part)
        script_dir = os.path.dirname(__file__)
        folder = "images"
        abs_file_path = os.path.join(script_dir, folder)
        images = os.listdir(abs_file_path)
        for count, image in enumerate(images):
            message.attach(MIMEText(f'<img src="cid:image{count}">', 'html'))
            with open(f"images/{image}", "rb") as img:
                image_file = MIMEImage(img.read())
                image_file.add_header("Content-ID", f"<image{count}>")
                message.attach(image_file)

        try:
            server.login(config.sender_email, config.sender_email_password)
            server.sendmail(config.sender_email, config.recipient_email, message.as_string())
        except Exception as _ex:
            logging.critical("send email - error", exc_info=True)
        finally:
            server.quit()


    def search_data_profile(result):

        number_profile = result[0]
        url_search = os.getenv("URL_PROFILE")
        new_url = f"{url_search}a{number_profile}.htm"

        try:
            data = {}
            data['Номер'] = result[0]
            data['Мт'] = result[1]
            data['Им'] = result[2]
            data['Вз'] = result[3]
            data['Гр'] = result[4]
            data['Рс'] = result[5]
            data['Вс'] = result[6]
            data['Ан'] = result[7]
            data['Цн'] = result[8]
            driver.get(new_url)
            time.sleep(random.randint(0,3))
            html = driver.page_source
            soup = BeautifulSoup(html, "lxml")
            tel = soup.find("nobr", string=re.compile("Телефон")).find_parent("p", class_="t").find_next().find_next().find("a")
            data['Телефон'] = tel.text
            logging.info("Telephone number valid")
            try:
                time_job = tel.find_next_sibling().text
            except:
                time_job = None
            data['Время работы'] = time_job
            logging.info("Time job valid")
            try:
                text = soup.find("p", id="txt_top").find("i")
                data['Описание'] = text.text
            except:
                pass
            logging.info("Description valid")
            contacts = soup.find("div", string=re.compile("Контактов"))
            if contacts:
                data['Контакты'] = contacts.text
                logging.info("Contacts valid")
                text_1 = contacts.find_parent().find_parent().find_next_sibling().find("div")
            else:
                try:
                    text_1 = soup.find("td", string=re.compile("Выезд")).find_parent().find_next_sibling().find_next_sibling().find("div", class_="ar13")
                except:
                    logging.info(f"{data['Номер']} extra info - error")
            try:
                data['Доп. инфо'] = text_1.text
            except:
                pass
            logging.info("Description_2 valid")
            services = soup.find("table", class_="uslugi_block").find_all("a", class_="menu")
            price = 0
            for service in services:
                result = service.find_next_sibling().find_next_sibling()
                try:
                    result_text = result.text
                    if result_text == "":
                        price = "Есть"
                    else:
                        price = result_text
                except:
                    price = "Есть"          
                data[service.text] = price
            add_services = soup.find_all("div", class_="success_only")
            try:
                for add_service in add_services:
                    try:
                        serv_result = add_service.text.split(":", 1)
                        data[serv_result[0]] = serv_result[1]
                    except:
                        data[add_service.text] = "Есть"
                logging.info("Services valid")
            except:
                logging.warning("Services not valid", exc_info=True)

            
            script_dir = os.path.dirname(__file__)
            folder = "images"
            abs_file_path = os.path.join(script_dir, folder)
            try:
                shutil.rmtree(abs_file_path)
            except:
                pass
            os.mkdir(folder)
            photos = soup.find("div", class_="highslide-gallery").find_all("img")
            for count, photo in enumerate(photos):
                photo_url = f"{url_search[:-1]}{photo['src']}"
                driver.get(photo_url)
                time.sleep(random.randint(0,3))
                driver.save_screenshot(f"images/{count}.png")
            return data

        except Exception:
            logging.critical("func get_source_html - error", exc_info=True)


    def random_output(data):
        try:
            random_variants = random.sample(data, 5)
        except Exception as _ex:
            logging.error(f"random_variants in = {data}", exc_info=True)
        try:
            for result in random_variants:
                send_email(search_data_profile(result))
            bot.send_message(message.chat.id, 'Письма отправлены')
        except:
            bot.send_message(message.chat.id, 'Письма НЕ отправлены')
            logging.error(f"{result[0]} sends email - error", exc_info=True)
        # finally:
        #     driver.close()
        #     driver.quit()


    def places_output(distance):
        with sq.connect(config.db_search) as con:
            cur = con.cursor()
            cur.execute("SELECT place FROM places WHERE (distance BETWEEN 1 AND ?)", (distance,))
            for row in cur:
                places_list.append(row[0])

    
    def filter(search_place, visit_anks):
        with sq.connect(config.db_search) as con:
            cur = con.cursor()
            cur.execute(search_1)
            places_output(search_place)
            for result in cur:
                if (result[1] in places_list) and (result[0] not in visit_anks): 
                    profiles.append(result)
        random_output(profiles)


    def visits():
        visit_anks = []
        with sq.connect(config.db_search) as con:
            cur = con.cursor()
            cur.execute("SELECT number_profile FROM profiles")
            for row in cur:
                visit_anks.append(row[0])
        return visit_anks


    filter(place, visits())


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


def daily_schedule():
    schedule.every().hour.until(datetime.timedelta(hours=13)).do(preparation_emails)
    logging.info(f"Schedule 'every_hour' every hour starts")
    routine_daily_check()


def schedule_bigger():
    schedule.every().day.at(config.work_day_start, timezone(config.timezone_my)).do(daily_schedule)
    logging.info(f"Schedule 'every_day' starts")

    while True:
        schedule.run_pending()
        time.sleep(1)


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
    threading.Thread(target=schedule_bigger).start()
    bot.polling(none_stop=True)
