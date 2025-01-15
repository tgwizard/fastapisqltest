from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
import asyncio
import time

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and upsert buffy on startup
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        statement = select(User).where(User.name == "buffy")
        buffy = session.exec(statement).first()
        
        if not buffy:
            buffy = User(name="buffy")
            session.add(buffy)
        session.commit()
    
    yield
    # Clean up resources on shutdown if needed

app = FastAPI(lifespan=lifespan)

# Database configuration
DATABASE_URL = "postgresql://postgres:mysecretpassword@localhost/postgres"  # Update with your credentials
DATABASE_URL_ASYNC = "postgresql+asyncpg://postgres:mysecretpassword@localhost/postgres"  # Update with your credentials

# Define the User model
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

# Create engine
engine = create_engine(DATABASE_URL, echo=True, echo_pool=True)
async_engine = create_async_engine(DATABASE_URL_ASYNC, echo=True, echo_pool=True)
async_session = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

@app.get("/sync_session_sleep_outside_session")
def root():
    with Session(engine) as session:
        # Get the last user by ordering by id in descending order and taking the first one
        statement = select(User).order_by(User.id.desc()).limit(1)
        res = session.exec(statement)
        user = res.first()
    time.sleep(2)

    if user:
        return {"last_user_name": user.name}
    return {"message": "No users found"}

@app.get("/sync_session_sleep_inside_session")
def root():
    with Session(engine) as session:
        # Get the last user by ordering by id in descending order and taking the first one
        statement = select(User).order_by(User.id.desc()).limit(1)
        res = session.exec(statement)
        user = res.first()
        time.sleep(2)

    if user:
        return {"last_user_name": user.name}
    return {"message": "No users found"}

@app.get("/async_session_sleep_outside_session")
async def root():
    async with async_session() as session:
        # Get the last user by ordering by id in descending order and taking the first one
        statement = select(User).order_by(User.id.desc()).limit(1)
        res = await session.exec(statement)
        user = res.first()
    await asyncio.sleep(2)

    if user:
        return {"last_user_name": user.name}
    return {"message": "No users found"}

@app.get("/async_session_sleep_inside_session")
async def root():
    async with async_session() as session:
        # Get the last user by ordering by id in descending order and taking the first one
        statement = select(User).order_by(User.id.desc()).limit(1)
        res = await session.exec(statement)
        user = res.first()
        await asyncio.sleep(2)

    if user:
        return {"last_user_name": user.name}
    return {"message": "No users found"}
