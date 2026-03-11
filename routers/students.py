from fastapi import APIRouter, Depends, HTTPException
from core.auth import get_current_user
from core.config import supabase
from pydantic import BaseModel

router = APIRouter(prefix="/students", tags=["Students"])

class StudentCreate(BaseModel):
    name: str
    class_id: str
    status: str = "CURSANDO"


@router.post("/")
def create_student(data: StudentCreate, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    student = supabase.table("students").insert({
        "school_id": user["school_id"],
        "class_id": data.class_id,
        "name": data.name,
        "status": data.status
    }).execute()

    return student.data


@router.get("/")
def list_students(user=Depends(get_current_user)):

    return supabase.table("students") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute().data
