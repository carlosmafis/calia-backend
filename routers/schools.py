from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.config import supabase
from core.auth import get_current_user

router = APIRouter(prefix="/schools", tags=["Schools"])

class SchoolCreate(BaseModel):
    name: str
    slug: str
    plan: str = "free"


@router.post("/")
def create_school(data: SchoolCreate, user=Depends(get_current_user)):

    if user["role"] != "super_admin":
        raise HTTPException(status_code=403)

    school = supabase.table("schools").insert({
        "name": data.name,
        "slug": data.slug,
        "plan": data.plan
    }).execute().data[0]

    return school


@router.get("/")
def list_schools(user=Depends(get_current_user)):

    if user["role"] == "super_admin":
        return supabase.table("schools").select("*").execute().data

    return supabase.table("schools") \
        .select("*") \
        .eq("id", user["school_id"]) \
        .execute().data
