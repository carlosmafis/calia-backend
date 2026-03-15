from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user
from core.config import supabase

router = APIRouter()


class SubjectCreate(BaseModel):
    name: str


# ==========================
# LISTAR DISCIPLINAS
# ==========================

@router.get("/")
def list_subjects(user=Depends(get_current_user)):

    data = supabase.table("subjects") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute()

    return data.data


# ==========================
# CRIAR DISCIPLINA
# ==========================

@router.post("/")
def create_subject(data: SubjectCreate, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    subject = supabase.table("subjects").insert({
        "school_id": user["school_id"],
        "name": data.name
    }).execute()

    return subject.data


# ==========================
# ATUALIZAR DISCIPLINA
# ==========================

@router.put("/{subject_id}")
def update_subject(
    subject_id: str,
    data: SubjectCreate,
    user=Depends(get_current_user)
):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("subjects") \
        .update({"name": data.name}) \
        .eq("id", subject_id) \
        .execute()

    return {"message": "Disciplina atualizada"}


# ==========================
# DELETAR DISCIPLINA
# ==========================

@router.delete("/{subject_id}")
def delete_subject(subject_id: str, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("subjects") \
        .delete() \
        .eq("id", subject_id) \
        .execute()

    return {"message": "Disciplina removida"}
