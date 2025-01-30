from sqlalchemy import create_engine, Column, Integer, String, Boolean, BigInteger, TIMESTAMP, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DB_URL

engine = create_engine(DB_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255))

class WorkerBotDB(Base):  # Переименован для избежания конфликта
    __tablename__ = 'bots'
    bot_id = Column(Integer, primary_key=True)
    owner_id = Column(BigInteger, ForeignKey('users.user_id'))
    token = Column(String(255), unique=True)
    bot_username = Column(String(255))
    is_active = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP)

class SubscriptionDB(Base):
    __tablename__ = 'subscriptions'
    sub_id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey('bots.bot_id'))
    tariff = Column(String(50))
    end_date = Column(TIMESTAMP)
    material_limit = Column(Integer)

class UsageStatsDB(Base):
    __tablename__ = 'usage_stats'
    stat_id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey('bots.bot_id'))
    materials_used = Column(Integer, default=0)
    last_activity = Column(TIMESTAMP)


class UserActivity(Base):
    __tablename__ = 'user_activity'
    activity_id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    chat_id = Column(BigInteger)
    messages_sent = Column(Integer, default=0)
    last_action = Column(TIMESTAMP)


class LinkedGroup(Base):
    __tablename__ = 'linked_groups'
    group_id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey('bots.bot_id'))
    chat_id = Column(BigInteger)
    chat_title = Column(String(255))
    tariff = Column(String(50)) 


class SentMaterial(Base):
    __tablename__ = 'sent_materials'
    material_id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey('bots.bot_id'))
    chat_id = Column(BigInteger)
    sent_at = Column(TIMESTAMP)

Base.metadata.create_all(engine)