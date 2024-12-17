from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import databases
from sqlalchemy import Column, Integer, String, Float

# URL для подключения к базе данных
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./products.db"

# Создаем экземпляр базы данных
database = databases.Database(SQLALCHEMY_DATABASE_URL)

# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,  # Включение вывода логов
    future=True  # Использование асинхронных функций
)

# Создаем фабрику сессий для асинхронных сессий
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,  # Используем асинхронную версию Session
    expire_on_commit=False,  # Отключение автоматического сохранения изменений при коммите
    future=True  # Использование асинхронных функций
)

# Определяем базовый класс модели
Base = declarative_base()

# Инициализация базы данных (создание таблиц)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database tables created successfully.")

# Close database connection
async def close_db():
    # Закрываем соединение с базой данных
    await engine.dispose()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)

    def __init__(self, name, price):
        self.name = name
        self.price = price