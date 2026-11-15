"""
auth.py — FastAPI Router for /auth endpoints.
All JWT / password logic is delegated to auth_service.py.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from backend.core.database import supabase
from backend.core.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,  # re-exported so admin modules can still do: from backend.core.auth import get_current_user
    pwd_context,       # re-exported so officer_mgmt.py can do: from backend.core.auth import pwd_context
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ─── Pydantic Schemas ─────────────────────────────────────────
class AdminSetupRequest(BaseModel):
    email: str
    password: str
    admin_secret: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str


# ─── Admin Bootstrap (one-time setup) ────────────────────────
@router.post("/register-admin-secure")
def register_admin_secure(data: AdminSetupRequest):
    if data.admin_secret != "BHOPAL_PTU_SETUP_2026":
        raise HTTPException(status_code=403, detail="Invalid Admin Secret")

    hashed = hash_password(data.password)
    user_res = supabase.table("users").insert({
        "email": data.email,
        "password": hashed
    }).execute()

    if not user_res.data:
        raise HTTPException(status_code=500, detail="Admin creation failed")

    user_id = user_res.data[0]["id"]
    supabase.table("user_roles").insert({"user_id": user_id, "role": "admin"}).execute()
    return {"message": "Admin account initialized successfully"}


# ─── Officer / Citizen Registration ──────────────────────────
@router.post("/register")
def register(data: RegisterRequest):
    if data.role.lower() == "admin":
        raise HTTPException(status_code=403, detail="Standard admin registration blocked")

    existing = supabase.table("users").select("id").eq("email", data.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed = hash_password(data.password)
    user_res = supabase.table("users").insert({
        "email": data.email,
        "password": hashed
    }).execute()

    if not user_res.data:
        raise HTTPException(status_code=500, detail="User creation failed")

    user_id = user_res.data[0]["id"]
    supabase.table("user_roles").insert({"user_id": user_id, "role": data.role.lower()}).execute()
    return {"message": "User created successfully"}


# ─── Login ────────────────────────────────────────────────────
@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    email    = form_data.username
    password = form_data.password

    user_res = supabase.table("users").select("*").eq("email", email).execute()
    if not user_res.data:
        raise HTTPException(status_code=400, detail="User not found")

    user = user_res.data[0]
    if not verify_password(password, user["password"]):
        raise HTTPException(status_code=400, detail="Invalid password")

    role_res = supabase.table("user_roles").select("role").eq("user_id", user["id"]).execute()
    if not role_res.data:
        raise HTTPException(status_code=400, detail="Role not assigned")

    role  = role_res.data[0]["role"]
    token = create_access_token({"sub": user["id"], "role": role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
    }

