from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime
from database import Session, SentMaterial, WorkerBotDB  # Импортируем необходимые классы
from config import MASTER_BOT_TOKEN  # Импортируем токен мастер-бота

class WorkerBotInstance:
    def __init__(self, token):
        self.token = token  # Сохраняем токен рабочего бота
        self.bot = Bot(token=token)  # Инициализируем рабочего бота
        self.master_bot = Bot(token=MASTER_BOT_TOKEN)  # Инициализируем мастер-бота
        self.dp = Dispatcher(self.bot, storage=MemoryStorage())
        self._register_handlers()

    def _register_handlers(self):
        @self.dp.message_handler(commands=['start'])
        async def start(message: types.Message):
            await message.answer("Я рабочий бот! Моя функция — продажа материалов.")

        @self.dp.message_handler(commands=['send_material'])
        async def send_material(message: types.Message):
            chat_id = message.chat.id
            bot_id = self._get_bot_id()  # Получаем ID бота из БД

            # Сохраняем информацию о отправленном материале
            with Session() as session:
                material = SentMaterial(
                    bot_id=bot_id,
                    chat_id=chat_id,
                    sent_at=datetime.now()
                )
                session.add(material)
                session.commit()

                # Получаем владельца бота
                bot = session.query(WorkerBotDB).filter(WorkerBotDB.bot_id == bot_id).first()
                if not bot:
                    await message.answer("❌ Ошибка: бот не найден в базе данных.")
                    return

                owner_id = bot.owner_id  # ID владельца бота в Telegram

            # Уведомляем мастер-бота
            await self.master_bot.send_message(
                chat_id=owner_id,  # Отправляем уведомление владельцу
                text=f"📦 Материал отправлен в чат {chat_id}."
            )

            await message.answer("✅ Материал успешно отправлен!")

    def _get_bot_id(self):
        # Получаем ID бота из БД по токену
        with Session() as session:
            bot = session.query(WorkerBotDB).filter(WorkerBotDB.token == self.token).first()
            return bot.bot_id if bot else None

    async def start(self):
        try:
            await self.dp.start_polling()
        finally:
            await self.dp.storage.close()

    async def stop(self):
        await self.dp.storage.close()
        await self.bot.close()
        await self.master_bot.close()
        