from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional

from core.config import supabase
from core.auth import get_current_user

import pandas as pd

router = APIRouter(tags=["Students"])


class StudentCreate(BaseModel):
    name: str
    class_id: str
    status: str = "CURSANDO"


# ==========================
# LISTAR ALUNOS
# ==========================

@router.get("/")
def list_students(
    class_id: Optional[str] = Query(None),
    user=Depends(get_current_user)
):

    query = supabase.table("students") \
        .select("*") \
        .eq("school_id", user["school_id"])

    if class_id:
        query = query.eq("class_id", class_id)

    students = query.execute()

    return students.data


# ==========================
# CRIAR ALUNO
# ==========================

@router.post("/")
def create_student(data: StudentCreate, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    student = supabase.table("students").insert({
        "school_id": user["school_id"],
        "class_id": data.class_id,
        "name": data.name,
        "status": data.status
    }).execute()

    return student.data


# ==========================
# IMPORTAR ALUNOS VIA CSV
# ==========================

@router.post("/upload")
async def upload_students(
    class_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    try:
        df = pd.read_csv(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler CSV: {str(e)}")

    count = 0
    errors = []

    for _, row in df.iterrows():
        try:
            supabase.table("students").insert({
                "school_id": user["school_id"],
                "class_id": class_id,
                "name": row["name"],
                "status": row.get("status", "CURSANDO")
            }).execute()
            count += 1
        except Exception as e:
            errors.append(f"Erro na linha {_ + 1}: {str(e)}")

    return {
        "message": f"{count} alunos importados",
        "errors": errors
    }


# ==========================
# ATUALIZAR ALUNO
# ==========================

@router.put("/{student_id}")
def update_student(
    student_id: str,
    data: StudentCreate,
    user=Depends(get_current_user)
):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("students") \
        .update({
            "name": data.name,
            "status": data.status,
            "class_id": data.class_id
        }) \
        .eq("id", student_id) \
        .execute()

    return {"message": "Aluno atualizado"}


# ==========================
# MOVER ALUNO DE TURMA
# ==========================

@router.put("/move/{student_id}")
def move_student(student_id: str, class_id: str, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("students").update({
        "class_id": class_id
    }).eq("id", student_id).execute()

    return {"message": "Aluno movido de turma"}


# ==========================
# DELETAR ALUNO
# ==========================

@router.delete("/{student_id}")
def delete_student(student_id: str, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("students") \
        .delete() \
        .eq("id", student_id) \
        .execute()

    return {"message": "Aluno removido"}


# ==========================
# NOTAS DE UM ALUNO
# ==========================

@router.get("/{student_id}/grades")
def get_student_grades(student_id: str, user=Depends(get_current_user)):

    submissions = supabase.table("student_submissions") \
        .select("*, assessments(title, subject_id)") \
        .eq("student_id", student_id) \
        .execute()

    return submissions.data or []
