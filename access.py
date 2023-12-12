import config
import logging
import main
import socket
import sqlite3 as sq


def socket_client(server, port, coding, data_send):
    sock = socket.socket()
    sock.connect((server, port))
    sock.send(data_send.encode(coding))
    sock.close()


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
            balance = (event_balance + routine_balance) / week_days
            logging.info(f"Balance {balance}")
            return round(balance, 3)
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
        if balance >= 1 and not bad_hand:
            with sq.connect(config.database) as con:
                cur = con.cursor()
                cur.execute("INSERT INTO events (event) VALUES(1)")
            main.bot.send_message(
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
            main.bot.send_message(
                message.chat.id,
                text=f"Допуск НЕ получен:\nбаланс: {balance}\n"
                     f"3НЕ: {bad_hand[0]}"
            )
    except Exception:
        logging.warning(msg="func access_check - error", exc_info=True)


def search_add(message, call_data):
    try:
        data = call_data.split()
        if data[1] == "people":
            main.bot.send_message(
                message.chat.id,
                text="Введи данные в формате Nam;Add;Met;Pho"
                )
            main.bot.register_next_step_handler(
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
            main.bot.send_message(
                message.chat.id,
                text="Введи данные в формате ID_Peo;Dat;Coun"
                )
            main.bot.register_next_step_handler(
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
            main.bot.send_message(
                message.chat.id,
                text="Введи данные в формате ID_Peo;Number"
                )
            main.bot.register_next_step_handler(
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
            main.bot.send_message(
                message.chat.id,
                text="Введи данные в формате ID_Peo;12char"
                )
            main.bot.register_next_step_handler(
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
