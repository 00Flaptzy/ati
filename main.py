import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import engine
from models import Base
from auth_router import auth_router
from habit_router import habit_router
from utils_router import utils_router

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from rate_limiter import limiter

# =========================
# ENV
# =========================
load_dotenv()

# =========================
# APP
# =========================
app = FastAPI(
    title="Habit Tracker API",
    version="1.0.0"
)

# =========================
# RATE LIMITER
# =========================
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# =========================
# CORS (PRODUCCIÓN)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambia por tu frontend en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ROUTERS
# =========================
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(habit_router, prefix="/habits", tags=["Habits"])
app.include_router(utils_router, prefix="/utils", tags=["Utils"])

# =========================
# SCHEDULER
# =========================
scheduler = AsyncIOScheduler()


async def periodic_task():
    from periodic_tasks import update_jwts, reset_potential_habit
    await update_jwts()
    await reset_potential_habit()


async def daily_habit_reset():
    from periodic_tasks import reset_all_habits
    await reset_all_habits()


scheduler.add_job(
    periodic_task,
    trigger="interval",
    seconds=int(os.getenv("PERIODIC_TASK_INTERVAL_SECONDS", "300")),
)

scheduler.add_job(
    daily_habit_reset,
    trigger="cron",
    hour=int(os.getenv("HABIT_RESETTING_HOURS", "0")),
    minute=0,
)

# =========================
# STARTUP / SHUTDOWN
# =========================
@app.on_event("startup")
async def on_startup():
    # DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Scheduler (IMPORTANTE: aquí, no arriba)
    scheduler.start()


@app.on_event("shutdown")
async def on_shutdown():
    scheduler.shutdown()


# =========================
# ROOT
# =========================
@app.get("/")
async def root():
    return {"status": "ok"}
