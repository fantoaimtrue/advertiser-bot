from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import MASTER_BOT_TOKEN
from database import Session, User, WorkerBotDB, SubscriptionDB, UsageStatsDB, SentMaterial
from worker_bot import WorkerBotInstance
from aiogram.utils.exceptions import Unauthorized
import asyncio
from datetime import datetime, timedelta
import asyncio
from worker_bot import WorkerBotInstance

# Инициализация бота
bot = Bot(token=MASTER_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user = message.from_user
    with Session() as session:
        db_user = session.query(User).filter(User.user_id == user.id).first()
        if not db_user:
            db_user = User(user_id=user.id, username=user.username)
            session.add(db_user)
            session.commit()
    await message.answer("Привет! Я мастер-бот. Используй /add_bot чтобы добавить рабочего бота.")

@dp.message_handler(commands=['start_bot'])
async def start_worker_bot(message: types.Message):
    user_id = message.from_user.id
    with Session() as session:
        bot = session.query(WorkerBotDB).filter(WorkerBotDB.owner_id == user_id).first()
        if not bot:
            await message.answer("Сначала зарегистрируйте бота через /add_bot.")
            return

        if bot.token not in active_worker_bots:
            try:
                worker = WorkerBotInstance(token=bot.token)  # Передаем токен рабочего бота
                task = asyncio.create_task(worker.start())
                active_worker_bots[bot.token] = task
                bot.is_active = True
                session.commit()
                await message.answer("🤖 Бот успешно запущен!")
            except Exception as e:
                await message.answer(f"❌ Ошибка запуска: {str(e)}")
        else:
            await message.answer("ℹ️ Бот уже запущен.")

@dp.message_handler(commands=['my_bots'])
async def list_bots(message: types.Message):
    user_id = message.from_user.id
    with Session() as session:
        bots = session.query(WorkerBotDB).filter(WorkerBotDB.owner_id == user_id).all()  # Исправленный запрос
        if not bots:
            await message.answer("У вас нет зарегистрированных ботов.")
            return
        response = "Ваши боты:\n" + "\n".join([f"ID: {bot.bot_id}, Токен: {bot.token[:5]}..." for bot in bots])
        await message.answer(response)


active_worker_bots = {}  # Словарь для хранения активных ботов: {token: task}

@dp.message_handler(commands=['start_bot'])
async def start_worker_bot(message: types.Message):
    user_id = message.from_user.id
    with Session() as session:
        # Получаем бота пользователя
        bot = session.query(WorkerBotDB).filter(WorkerBotDB.owner_id == user_id).first()
        if not bot:
            await message.answer("Сначала зарегистрируйте бота через /add_bot.")
            return

        # Проверяем подписку
        subscription = session.query(SubscriptionDB).filter(SubscriptionDB.bot_id == bot.bot_id).first()
        if not subscription or subscription.end_date < datetime.now():
            await message.answer("Подписка истекла! Продлите её через /buy_subscription.")
            return

        # Если бот уже запущен
        if bot.token in active_worker_bots:
            await message.answer("Бот уже активен!")
            return

        # Запускаем рабочего бота в отдельной асинхронной задаче
        try:
            worker = WorkerBotInstance(token=bot.token)
            task = asyncio.create_task(worker.start())
            active_worker_bots[bot.token] = task
            bot.is_active = True
            session.commit()
            await message.answer("Рабочий бот запущен!")
        except Unauthorized:
            await message.answer("Неверный токен! Удалите бота и зарегистрируйте заново.")


@dp.message_handler(commands=['stop_bot'])
async def stop_worker_bot(message: types.Message):
    user_id = message.from_user.id
    with Session() as session:
        bot = session.query(WorkerBotDB).filter(WorkerBotDB.owner_id == user_id).first()
        if not bot:
            await message.answer("У вас нет активных ботов.")
            return

        if bot.token in active_worker_bots:
            task = active_worker_bots.pop(bot.token)
            task.cancel()
            bot.is_active = False
            session.commit()
            await message.answer("Бот остановлен.")
        else:
            await message.answer("Бот не активен.")

@dp.message_handler(commands=['buy_subscription'])
async def buy_subscription(message: types.Message):
    # Пример реализации с инлайн-кнопками
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Все включено (30 дней) - $10", callback_data="tariff_all"))
    markup.add(types.InlineKeyboardButton("Урезанный (30 дней) - $5", callback_data="tariff_limited"))
    await message.answer("Выберите тариф:", reply_markup=markup)


async def check_limits(master_bot: Bot):
    while True:
        await asyncio.sleep(3600)  # Проверка каждый час
        with Session() as session:
            bots = session.query(WorkerBotDB).all()
            for bot in bots:
                # Получаем количество отправленных материалов
                materials_sent = session.query(SentMaterial)\
                    .filter(SentMaterial.bot_id == bot.bot_id)\
                    .count()

                # Получаем подписку бота
                subscription = session.query(SubscriptionDB)\
                    .filter(SubscriptionDB.bot_id == bot.bot_id)\
                    .first()

                if subscription and materials_sent >= subscription.material_limit:
                    # Останавливаем рабочего бота
                    if bot.token in active_worker_bots:
                        task = active_worker_bots.pop(bot.token)
                        task.cancel()
                        bot.is_active = False
                        session.commit()

                        # Уведомляем владельца
                        await master_bot.send_message(
                            chat_id=bot.owner_id,
                            text=f"🚫 Бот {bot.bot_username} остановлен: лимит материалов исчерпан!"
                        )

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(check_limits(bot))  # Запускаем проверку лимитов
    asyncio.run(dp.start_polling())