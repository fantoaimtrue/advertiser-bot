import os

from dotenv import load_dotenv

load_dotenv()

# Токен мастер-бота (создайте его через BotFather)
MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN")

# Данные для подключения к PostgreSQL
DB_URL = os.getenv("DB_URL", "postgresql://user:password@localhost/db_name")