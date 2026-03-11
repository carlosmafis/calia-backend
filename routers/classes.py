from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.config import supabase
from core.auth import get_current_user

router = APIRouter(prefix="/classes", tags=["Classes"])

class ClassCreate(BaseModel):
    name: str
    year: str

@router.post("/")
def create_class(data: ClassCreate, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    new_class = supabase.table("classes").insert({
        "school_id": user["school_id"],
        "name": data.name,
        "year": data.year
    }).execute()

    return new_class.data

@router.get("/")
def list_classes(user=Depends(get_current_user)):

    return supabase.table("classes") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute().data
