from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, Organization
from app.schemas import UserCreate, UserLogin, UserResponse, Token
from app.core.security import verify_password, get_password_hash, create_access_token
from uuid import uuid4

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed = get_password_hash(user_data.password)
    new_user = User(
        id=str(uuid4()),
        email=user_data.email,
        hashed_password=hashed,
        full_name=user_data.full_name,
        role="member"
    )
    db.add(new_user)
    # Flush to get the user ID without committing
    await db.flush()
    
    # Create organization
    org = Organization(
        id=str(uuid4()),
        name=f"{user_data.full_name}'s Org",
        owner_id=new_user.id
    )
    db.add(org)
    
    # Commit both
    await db.commit()
    
    # Refresh the user to get all fields
    await db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}