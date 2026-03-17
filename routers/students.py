from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from pydantic import BaseModel
from typing import Optional
import secrets
import string

from core.config import supabase
from core.auth import get_current_user

import pandas as pd

router = APIRouter(tags=["Students"])


class StudentCreate(BaseModel):
    name: str
    class_id: str
    status: str = "CURSANDO"
    registration_number: Optional[str] = None


def generate_temp_password(length: int = 12) -> str:
    """Gera uma senha temporária aleatória."""
    characters = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(characters) for _ in range(length))


def create_supabase_user(email: str, password: str) -> dict:
    """Cria um usuário no Supabase Auth."""
    try:
        user = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True
        })
        return {"success": True, "user_id": user.user.id, "email": email, "temp_password": password}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_school_domain(school_id: str) -> str:
    """Obtém o domínio da escola para gerar o email do aluno."""
    try:
        school = supabase.table("schools").select("slug").eq("id", school_id).execute()
        if school.data:
            return school.data[0].get("slug", "escola")
    except:
        pass
    return "escola"

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

    school_domain = get_school_domain(user["school_id"])
    registration = data.registration_number or data.name.lower().replace(" ", "_")
    email = f"{registration}@{school_domain}.com.br"
    
    temp_password = generate_temp_password()
    
    auth_result = create_supabase_user(email, temp_password)
    
    if not auth_result["success"]:
        raise HTTPException(status_code=400, detail=f"Erro ao criar usuario: {auth_result['error']}")
    
    student = supabase.table("students").insert({
        "school_id": user["school_id"],
        "class_id": data.class_id,
        "name": data.name,
        "status": data.status,
        "email": email,
        "registration_number": registration
    }).execute()
    
    if not student.data:
        raise HTTPException(status_code=400, detail="Erro ao criar aluno")
    
    return {
        "student": student.data[0],
        "credentials": {
            "email": email,
            "temp_password": temp_password,
            "message": "Credenciais temporarias. O aluno deve trocar a senha no primeiro login."
        }
    }


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
    credentials_list = []
    school_domain = get_school_domain(user["school_id"])

    for idx, row in df.iterrows():
        try:
            name = row.get("Nome") or row.get("name")
            registration = row.get("Matricula") or row.get("registration_number")
            
            if not name:
                errors.append(f"Erro na linha {idx + 2}: Nome eh obrigatorio")
                continue
            
            if not registration:
                registration = name.lower().replace(" ", "_")
            
            email = f"{registration}@{school_domain}.com.br"
            temp_password = generate_temp_password()
            
            # Criar usuario no Supabase Auth
            auth = supabase.auth.admin.create_user({
                "email": email,
                "password": temp_password,
                "email_confirm": True
            })
            
            if not auth.user:
                errors.append(f"Erro na linha {idx + 2}: Falha ao criar usuario no Supabase")
                continue
            
            # Criar registro de aluno
            supabase.table("students").insert({
                "school_id": user["school_id"],
                "class_id": class_id,
                "name": name,
                "status": row.get("Turma") or row.get("status") or "CURSANDO",
                "email": email,
                "registration_number": registration
            }).execute()
            
            credentials_list.append({
                "name": name,
                "email": email,
                "temp_password": temp_password
            })
            
            count += 1
        except Exception as e:
            errors.append(f"Erro na linha {idx + 2}: {str(e)}")

    return {
        "message": f"{count} alunos importados",
        "errors": errors,
        "credentials": credentials_list
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
