from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
import re
from sqlalchemy.future import select
import jwt
import os
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv

load_dotenv()

# Base for SQLAlchemy models
Base = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# SQLAlchemy User Model
class User(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)

# Pydantic models for FastAPI
class UserCreate(BaseModel):
    name: str
    password: str
    email: EmailStr

class UserLogin(BaseModel):
    email: EmailStr
    password: str

DATABASE_URL = "sqlite+aiosqlite:///./users.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Database operations
async def create_user(user_name: str, raw_password: str, email: str):
    async with async_session() as session:
        hashed_password = pwd_context.hash(raw_password)
        new_user = User(user_name=user_name, password=hashed_password, email=email)
        session.add(new_user)
        await session.commit()
        return new_user

async def get_user_by_email(email: str):
    async with async_session() as session:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

async def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)



def validate_password_strength(password: str) -> bool:
    """
    Validates the strength of a password.
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one digit
    - At least one special character
    """
    pattern = r"^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*])[A-Za-z\d!@#$%^&*]{8,}$"
    return bool(re.match(pattern, password))

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')  # Replace with an environment variable
ALGORITHM = "HS256"

def generate_jwt_token(user_id: str, email: str) -> str:
    """
    Generates a JWT token for authenticated users.
    - Payload includes `user_id` and `email`.
    - Token expires after 24 hours.
    """
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)
