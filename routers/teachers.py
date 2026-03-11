from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.config import supabase
from core.auth import get_current_user

router = APIRouter(prefix="/teachers", tags=["Teachers"])

class TeacherCreate(BaseModel):
    email: str
    full_name: str


@router.post("/")
def create_teacher(data: TeacherCreate, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    password = "12345678"

    auth = supabase.auth.admin.create_user({
        "email": data.email,
        "password": password,
        "email_confirm": True
    })

    supabase.table("profiles").insert({
        "id": auth.user.id,
        "school_id": user["school_id"],
        "role": "professor",
        "full_name": data.full_name
    }).execute()

    return {
        "email": data.email,
        "temporary_password": password
    }


@router.get("/")
def list_teachers(user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    return supabase.table("profiles") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .eq("role", "professor") \
        .execute().data
