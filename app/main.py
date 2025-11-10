from fastapi import FastAPI
from app.api import users, chat

app = FastAPI(title="HealthChat API")

app.include_router(users.router)
app.include_router(chat.router)
