from database import session_local
from models import JWTTable
from fastapi import HTTPException, Body, Header
import re
from dotenv import load_dotenv
import os
from models import Users, Habits
from sqlalchemy.orm import Session
from GeneratingAuthUtils.jwt_token_handling import extract_payload
from fastapi import Header
from sqlalchemy.exc import SQLAlchemyError
from jwt.exceptions import PyJWTError
from schemas import TokenProvidedSchema, HabitIdProvidedSchema
import datetime
from GeneratingAuthUtils.jwt_token_handling import extract_payload
from db_utils import (
    get_token_by_match,
    get_user_by_id,
    get_session,
    get_habit_by_id,
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

load_dotenv()


async def authorize_token(token: str, db: Session) -> None:
    try:
        db_token = await get_token_by_match(db=db, token=token)
        if not db_token:
            raise HTTPException(
                status_code=401, detail="Invalid or expired token")
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500, detail="Error while working with database (token authorization)")


def prepare_authorization_token(token: str) -> str:
    if not token.startswith("Bearer "):
        raise HTTPException(
            status_code=400, detail="Invalid authorization header")

    token = token.replace("Bearer ", "")
    return token


def verify_credentials(username, email):
    if any(
        char in os.getenv("INVALID_USERNAME_CHARACTERS").split(",") for char in username
    ):
        raise HTTPException(
            status_code=400, detail="Username contains invalid characters"
        )
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        raise HTTPException(status_code=400, detail="Invalid Email")


async def get_user_depends(token: Annotated[str, Header(alias="token")]) -> Users:
    db = get_session()
    try:
        # Preparar el token (quitar "Bearer " si existe)
        clean_token = token.replace("Bearer ", "") if token.startswith("Bearer ") else token
        
        # Verificar token en base de datos
        await authorize_token(token=clean_token, db=db)
        
        try:
            payload = extract_payload(clean_token)
        except PyJWTError:
            raise HTTPException(status_code=400, detail="Invalid token")

        user = await get_user_by_id(db=db, user_id=payload["user_id"])
        if not user:
            raise HTTPException(
                status_code=401, detail="User connected to this token does not exists. Please, try again later or contact us")

        return user
    finally:
        await db.close()


async def get_habit_depends(habit_id: HabitIdProvidedSchema = Body(...)):
    db: AsyncSession = get_session()
    try:
        habit = await get_habit_by_id(db=db, habit_id=habit_id.habit_id)

        if not habit:
            raise HTTPException(
                status_code=400, detail="No habit with such ID")

        return habit
    finally:
        await db.close()


async def check_token_expiery_depends(token: Annotated[str, Header(alias="token")]) -> str:
    """
    Dependencia para verificar expiración del token.
    Acepta el token en el header 'token'.
    """
    try:
        db: Session = session_local()
        
        # Preparar el token (quitar "Bearer " si existe)
        clean_token = token.replace("Bearer ", "") if token.startswith("Bearer ") else token
        
        # Verificar token en base de datos
        await authorize_token(token=clean_token, db=db)

        # Extraer payload y obtener tiempo de expiración
        payload = extract_payload(token=clean_token)
        
        # Formatear el tiempo de expiración
        expires_timestamp = int(payload.get("expires", payload.get("exp")))
        expires_time = datetime.datetime.fromtimestamp(expires_timestamp).strftime("%H:%M:%S")
        
        return expires_time
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
    finally:
        if db:
            await db.close()