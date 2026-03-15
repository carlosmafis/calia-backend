from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from core.auth import get_current_user
from core.config import supabase

router = APIRouter()

class TeacherCreate(BaseModel):
    full_name: str
    email: str
    subject_ids: List[str]
    class_ids: List[str]


@router.get("/")
def list_teachers(user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    data = supabase.table("profiles") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .eq("role", "professor") \
        .execute()

    return data.data

@router.get("/my-subjects")
def my_subjects(user=Depends(get_current_user)):

    data = supabase.table("teacher_subjects") \
        .select("subjects(*)") \
        .eq("teacher_id",user["id"]) \
        .execute()

    return [x["subjects"] for x in data.data]

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

    teacher_id = auth.user.id

    supabase.table("profiles").insert({
        "id": teacher_id,
        "school_id": user["school_id"],
        "role": "professor",
        "full_name": data.full_name
    }).execute()

    # disciplinas
    for subject in data.subject_ids:

        supabase.table("teacher_subjects").insert({
            "teacher_id": teacher_id,
            "subject_id": subject
        }).execute()

    # turmas
    for cls in data.class_ids:

        supabase.table("teacher_classes").insert({
            "teacher_id": teacher_id,
            "class_id": cls
        }).execute()

    return {
        "email": data.email,
        "password": password
    }
    
@router.put("/{teacher_id}")
def update_teacher(
    teacher_id:str,
    subject_ids:List[str],
    class_ids:List[str],
    user=Depends(get_current_user)
):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    supabase.table("teacher_subjects") \
        .delete() \
        .eq("teacher_id", teacher_id) \
        .execute()

    for subject in subject_ids:

        supabase.table("teacher_subjects").insert({
            "teacher_id": teacher_id,
            "subject_id": subject
        }).execute()

    supabase.table("teacher_classes") \
        .delete() \
        .eq("teacher_id", teacher_id) \
        .execute()

    for cls in class_ids:

        supabase.table("teacher_classes").insert({
            "teacher_id": teacher_id,
            "class_id": cls
        }).execute()

    return {"message":"Professor atualizado"}