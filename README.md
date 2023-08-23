# higher_mind

Обновляем пакеты:<br>
**sudo apt update && sudo apt upgrade**<br>
---
Установка необходимых для корректной работы google-chroma пакетов:<br>
**sudo apt install -y libxss1 libappindicator1 libindicator7**<br>
---
Скачиваем Chrome:<br>
**sudo wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb**<br>
Устанавливаем Chrome:<br>
sudo dpkg -i google-chrome*.deb<br>
---
Фиксим/подтягиваем зависимости:<br>
**sudo apt install -y -f**<br>
---
Устанавливаем виртуальное окружение:<br>
**python3 -m venv .venv**<br>
Запускаем виртуальное окружение:<br>
**source .venv/bin/activate**<br>
Обновляем pip:<br>
**pip install -U pip**<br>
Устанавливаем библиотеки:<br>
**pip install -r requirements.txt**<br>
---
Создаём файл **.env**<br>
Заносим переменные:<br>
**TELEGRAM_TOKEN**<br>
**TELEGRAM_MY_ID**<br>
**EMAIL_SENDER**<br>
**EMAIL_SENDER_PASSWORD**<br>
**EMAIL_RECIPIENT**<br>
**SEARCH_URL**<br>
**SEARCH**<br>
**SMTP_SERVER**<br>
**SMTP_PORT**<br>