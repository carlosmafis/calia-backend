from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import supabase
from core.auth import get_current_user

router = APIRouter(tags=["Classes"])


class ClassCreate(BaseModel):
    name: str
    year: str


# ==========================
# LISTAR TURMAS
# ==========================

@router.get("/")
def list_classes(user=Depends(get_current_user)):

    if user["role"] == "professor":
        # Professor vê apenas suas turmas vinculadas
        teacher_classes = supabase.table("teacher_classes") \
            .select("classes(*)") \
            .eq("teacher_id", user["id"]) \
            .execute()

        if not teacher_classes.data:
            return []

        return [tc["classes"] for tc in teacher_classes.data if tc["classes"]]

    # Admin e super_admin veem todas da escola
    classes = supabase.table("classes") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute()

    return classes.data


# ==========================
# CRIAR TURMA
# ==========================

@router.post("/")
def create_class(data: ClassCreate, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    new_class = supabase.table("classes").insert({
        "school_id": user["school_id"],
        "name": data.name,
        "year": data.year
    }).execute()

    return new_class.data


# ==========================
# VINCULAR PROFESSOR À TURMA
# ==========================

@router.post("/assign-teacher")
def assign_teacher(teacher_id: str, class_id: str, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("teacher_classes").insert({
        "teacher_id": teacher_id,
        "class_id": class_id
    }).execute()

    return {"message": "Professor vinculado à turma"}


# ==========================
# ATUALIZAR TURMA
# ==========================

@router.put("/{class_id}")
def update_class(class_id: str, data: ClassCreate, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("classes") \
        .update({
            "name": data.name,
            "year": data.year
        }) \
        .eq("id", class_id) \
        .execute()

    return {"message": "Turma atualizada"}


# ==========================
# DELETAR TURMA
# ==========================

@router.delete("/{class_id}")
def delete_class(class_id: str, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("classes") \
        .delete() \
        .eq("id", class_id) \
        .execute()

    return {"message": "Turma removida"}


# ==========================
# ALUNOS DE UMA TURMA
# ==========================

@router.get("/{class_id}/students")
def get_class_students(class_id: str, user=Depends(get_current_user)):

    students = supabase.table("students") \
        .select("*") \
        .eq("class_id", class_id) \
        .execute()

    return students.data or []
