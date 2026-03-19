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

    try:
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

        return classes.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar turmas: {str(e)}")


# ==========================
# CRIAR TURMA
# ==========================

@router.post("/")
def create_class(data: ClassCreate, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem criar turmas")

    # Validar dados
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Nome da turma é obrigatório")
    if not data.year or not data.year.strip():
        raise HTTPException(status_code=400, detail="Ano/série é obrigatório")

    try:
        new_class = supabase.table("classes").insert({
            "school_id": user["school_id"],
            "name": data.name.strip(),
            "year": data.year.strip()
        }).execute()

        if not new_class.data:
            raise HTTPException(status_code=500, detail="Erro ao criar turma no banco de dados")

        return new_class.data[0] if isinstance(new_class.data, list) else new_class.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar turma: {str(e)}")


# ==========================
# VINCULAR PROFESSOR À TURMA
# ==========================

@router.post("/assign-teacher")
def assign_teacher(teacher_id: str = None, class_id: str = None, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem vincular professores")

    if not teacher_id or not class_id:
        raise HTTPException(status_code=400, detail="teacher_id e class_id são obrigatórios")

    try:
        supabase.table("teacher_classes").insert({
            "teacher_id": teacher_id,
            "class_id": class_id
        }).execute()
        return {"message": "Professor vinculado à turma com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao vincular professor: {str(e)}")


# ==========================
# ATUALIZAR TURMA
# ==========================

@router.put("/{class_id}")
def update_class(class_id: str = None, data: ClassCreate = None, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem atualizar turmas")

    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Nome da turma é obrigatório")
    if not data.year or not data.year.strip():
        raise HTTPException(status_code=400, detail="Ano/série é obrigatório")

    try:
        result = supabase.table("classes") \
            .update({
                "name": data.name.strip(),
                "year": data.year.strip()
            }) \
            .eq("id", class_id) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Turma não encontrada")
        
        return {"message": "Turma atualizada com sucesso", "data": result.data[0] if isinstance(result.data, list) else result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar turma: {str(e)}")


# ==========================
# DELETAR TURMA
# ==========================

@router.delete("/{class_id}")
def delete_class(class_id: str = None, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem deletar turmas")

    try:
        result = supabase.table("classes") \
            .delete() \
            .eq("id", class_id) \
            .execute()
        
        return {"message": "Turma removida com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao deletar turma: {str(e)}")


# ==========================
# ALUNOS DE UMA TURMA
# ==========================

@router.get("/{class_id}/students")
@router.get("/{class_id}/students/")
def get_class_students(class_id: str = None, user=Depends(get_current_user)):

    try:
        students = supabase.table("students") \
            .select("*") \
            .eq("class_id", class_id) \
            .execute()

        return students.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar alunos: {str(e)}")
