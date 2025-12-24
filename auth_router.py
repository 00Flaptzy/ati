from fastapi import HTTPException, Body, Depends, APIRouter, Request, Header
from typing import Annotated
import datetime
import random
from uuid import uuid4

from schemas import (
    TokenSchema,
    UserSchema,
    RegisterSchema,
    LoginSchema,
    TokenProvidedSchema,
)

from GeneratingAuthUtils import jwt_token_handling, password_handling
from models import Users, JWTTable
from sqlalchemy.orm import Session
from jwt.exceptions import PyJWTError, InvalidTokenError

from depends_utils import (
    prepare_authorization_token,
    verify_credentials,
    get_user_depends,
    check_token_expiery_depends,
)

from db_utils import (
    commit,
    get_db,
    get_merged_user,
    get_user_by_username_email_optional,
    delete_existing_token,
    construct_and_add_model_to_database,
    get_token_by_user_id,
)

from user_xp_level_util import get_level_by_xp, get_xp_nedeed_by_level
from rate_limiter import limiter


auth_router = APIRouter()

# =========================
# TEST
# =========================
@auth_router.get("/")
@limiter.limit("20/minute")
async def test(request: Request) -> str:
    return "Hello World: " + str(random.randint(1, 100))


# =========================
# REGISTER
# =========================
@auth_router.post("/register")
@limiter.limit("20/minute")
async def register(
    request: Request,
    user_data: RegisterSchema = Body(...),
    db: Session = Depends(get_db),
) -> TokenSchema:

    username, password, email = (
        user_data.username,
        user_data.password,
        user_data.email,
    )

    verify_credentials(username=username, email=email)

    existing_user = await get_user_by_username_email_optional(
        db=db, username=username, email=email
    )
    if existing_user:
        raise HTTPException(status_code=409, detail="User already exists")

    user_id = str(uuid4())
    joined_at = datetime.datetime.now()

    password_hash = password_handling.hash_password(password).decode("utf-8")
    jwt_token, expires_at = jwt_token_handling.generate_jwt(user_id)

    construct_and_add_model_to_database(
        db=db,
        Model=Users,
        user_id=user_id,
        username=username,
        hashed_password=password_hash,
        joined_at=str(joined_at),
        email=email,
    )

    construct_and_add_model_to_database(
        db=db,
        Model=JWTTable,
        user_id=user_id,
        jwt_token=jwt_token,
        expires_at=expires_at,
    )

    await commit(db)
    return TokenSchema(token=jwt_token, expires_at=expires_at)


# =========================
# LOGIN
# =========================
@auth_router.post("/login")
@limiter.limit("20/minute")
async def login(
    request: Request,
    user_data: LoginSchema = Body(...),
    db: Session = Depends(get_db),
) -> TokenSchema:

    user = await get_user_by_username_email_optional(
        db=db, username=user_data.username
    )
    if not user or not password_handling.check_password(
        user_data.password, user.hashed_password.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    now = round(datetime.datetime.now().timestamp())
    token_in_db = await get_token_by_user_id(db=db, user_id=user.user_id)

    if token_in_db and token_in_db.expires_at > now:
        return TokenSchema(
            token=token_in_db.jwt_token,
            expires_at=token_in_db.expires_at,
        )

    jwt_token, expires_at = jwt_token_handling.generate_jwt(user.user_id)

    construct_and_add_model_to_database(
        db=db,
        Model=JWTTable,
        user_id=user.user_id,
        jwt_token=jwt_token,
        expires_at=expires_at,
    )

    await commit(db)
    return TokenSchema(token=jwt_token, expires_at=expires_at)


# =========================
# LOGOUT
# =========================
@auth_router.post("/logout")
@limiter.limit("20/minute")
async def logout(
    request: Request,
    token_data: TokenProvidedSchema = Body(...),
    db: Session = Depends(get_db),
):
    jwt_token = prepare_authorization_token(token_data.token)
    await delete_existing_token(db=db, jwt=jwt_token)
    await commit(db)


# =========================
# PROFILE
# =========================
@auth_router.get("/get_user_profile")
@limiter.limit("20/minute")
async def get_user_profile(
    request: Request,
    user: Users = Depends(get_user_depends),
    db: Session = Depends(get_db),
) -> UserSchema:

    user = await get_merged_user(user=user, db=db)

    level, remaining = get_level_by_xp(user.xp)
    current_level_xp = get_xp_nedeed_by_level(level - 1)
    next_level_xp = get_xp_nedeed_by_level(level)

    return UserSchema(
        user_id=user.user_id,
        username=user.username,
        joined_at=user.joined_at,
        email=user.email,
        xp=next_level_xp - remaining,
        level=level,
        next_level_xp_remaining=remaining,
        xp_to_next_level=next_level_xp,
        user_xp_total=user.xp - current_level_xp,
    )


# =========================
# CHECK TOKEN ✅ (FIXED)
# =========================
@auth_router.get("/check_token")
@limiter.limit("20/minute")
async def check_token(
    request: Request,
    authorization: str = Header(...),
    expires_at: int = Depends(check_token_expiery_depends),
):
    return {
        "valid": True,
        "expires_at": expires_at,
    }
