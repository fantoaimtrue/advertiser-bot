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


active_worker_bots = {}  # Добавить в начале файла

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


@dp.message_handler(commands=['add_bot'])
async def add_bot(message: types.Message):
    args = message.get_args()
    if not args:
        await message.answer("Укажите токен бота: /add_bot <токен>")
        return

    token = args.strip()
    user_id = message.from_user.id

    # Проверка формата токена (упрощенная версия)
    if len(token.split(':')) != 2:
        await message.answer("Неверный токен! Создайте бота через @BotFather и повторите.")
        return

    with Session() as session:
        # Проверяем, не зарегистрирован ли бот ранее
        existing_bot = session.query(WorkerBotDB).filter(WorkerBotDB.token == token).first()
        if existing_bot:
            await message.answer("Этот бот уже зарегистрирован!")
            return

        # Создаем запись о боте
        new_bot = WorkerBotDB(
            owner_id=user_id,
            token=token,
            bot_username=token.split(':')[0],
            is_active=False
        )
        session.add(new_bot)
        session.commit()

        # Создаем пробную подписку
        trial_sub = SubscriptionDB(
            bot_id=new_bot.bot_id,
            tariff="trial",
            end_date=datetime.now() + timedelta(days=7),
            material_limit=100
        )
        session.add(trial_sub)
        session.commit()

    await message.answer("✅ Бот успешно зарегистрирован! Вам доступна пробная подписка на 7 дней.")


@dp.message_handler(commands=['start_bot'])  # Исправлено имя команды
async def start_bot(message: types.Message):
    user_id = message.from_user.id
    with Session() as session:
        bot = session.query(WorkerBotDB).filter(WorkerBotDB.owner_id == user_id).first()
        if not bot:
            await message.answer("Сначала зарегистрируйте бота через /add_bot.")
            return

        if bot.token in active_worker_bots:
            await message.answer("ℹ️ Бот уже запущен. Перезапускаю...")
            old_worker = active_worker_bots.pop(bot.token)
            await old_worker.stop()

        try:
            worker = WorkerBotInstance(token=bot.token)
            active_worker_bots[bot.token] = worker
            bot.is_active = True
            session.commit()
            
            async def worker_wrapper(worker):
                try:
                    await worker.start()
                except Exception as e:
                    print(f"Бот {worker.token} упал с ошибкой: {str(e)}")
                finally:
                    if worker.token in active_worker_bots:
                        del active_worker_bots[worker.token]
            
            # Запускаем в отдельной задаче
            asyncio.create_task(worker_wrapper(worker))
            
            await message.answer("🤖 Бот успешно запущен!")
        except Exception as e:
            await message.answer(f"❌ Ошибка запуска: {str(e)}")

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


@dp.message_handler(commands=['stop_bot'])
async def stop_worker_bot(message: types.Message):
    user_id = message.from_user.id
    
    try:
        with Session() as session:
            # 1. Ищем ВСЕХ ботов пользователя
            bots = session.query(WorkerBotDB).filter(WorkerBotDB.owner_id == user_id).all()
            if not bots:
                await message.answer("У вас нет зарегистрированных ботов.")
                return

            stopped_count = 0
            for bot in bots:
                # 2. Проверяем наличие бота в активных
                if bot.token in active_worker_bots:
                    # 3. Получаем объект воркера
                    worker = active_worker_bots.pop(bot.token)
                    
                    # 4. Останавливаем асинхронно
                    try:
                        await worker.stop()
                    except Exception as stop_error:
                        print(f"Ошибка остановки бота {bot.token}: {stop_error}")
                        continue
                    
                    # 5. Обновляем статус в БД
                    bot.is_active = False
                    stopped_count += 1

            # 6. Фиксируем изменения для всех ботов
            session.commit()
            
            # 7. Формируем ответ
            if stopped_count > 0:
                await message.answer(f"✅ Остановлено ботов: {stopped_count}")
            else:
                await message.answer("ℹ️ Нет активных ботов для остановки")

    except Exception as e:
        print(f"Критическая ошибка в stop_bot: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при остановке ботов")

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

async def restore_active_bots():
    with Session() as session:
        active_bots = session.query(WorkerBotDB).filter(WorkerBotDB.is_active == True).all()
        for bot in active_bots:
            worker = WorkerBotInstance(token=bot.token)
            active_worker_bots[bot.token] = worker
            asyncio.create_task(worker.start())

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(restore_active_bots())  # Восстановление ботов
    loop.create_task(check_limits(bot))
    asyncio.run(dp.start_polling())