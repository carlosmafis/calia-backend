from fastapi import UploadFile, File
import shutil
import uuid
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

load_dotenv()

app = FastAPI()

# ----------------------------------------------------
# CORS
# ----------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://calia-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# SUPABASE
# ----------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
security = HTTPBearer()

# ----------------------------------------------------
# MODELOS
# ----------------------------------------------------

class SchoolCreate(BaseModel):
    name: str
    slug: str
    plan: Optional[str] = "free"

class StudentCreate(BaseModel):
    name: str
    class_id: str
    status: str = "CURSANDO"

class TeacherCreate(BaseModel):
    email: str
    full_name: str

class ClassCreate(BaseModel):
    name: str
    year: str

class AssessmentCreate(BaseModel):
    class_id: str
    title: str
    total_questions: int

class QuestionCreate(BaseModel):
    assessment_id: str
    question_number: int
    correct_answer: str
    weight: float
# ----------------------------------------------------
# AUTENTICAÇÃO
# ----------------------------------------------------

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user
    except:
        raise HTTPException(status_code=401, detail="Token inválido")

    if not user_data:
        raise HTTPException(status_code=401, detail="Token inválido")

    user_profile = supabase.table("profiles") \
        .select("*") \
        .eq("id", user_data.id) \
        .execute()

    if not user_profile.data:
        raise HTTPException(status_code=403, detail="Perfil não encontrado")

    return user_profile.data[0]

# ----------------------------------------------------
# LOG
# ----------------------------------------------------

def log_activity(user, action, entity):
    supabase.table("activity_logs").insert({
        "school_id": user.get("school_id"),
        "user_id": user.get("id"),
        "action": action,
        "entity": entity,
        "created_at": datetime.utcnow().isoformat()
    }).execute()

# ----------------------------------------------------
# NOVAS
# ----------------------------------------------------
def calculate_score(student_answers, correct_answers):

    score = 0

    for q in correct_answers:

        number = q["question_number"]
        correct = q["correct_answer"]
        weight = q["weight"]

        if student_answers.get(str(number)) == correct:
            score += weight

    return score

@app.post("/submit-answers")
def submit_answers(assessment_id:str, student_id:str, answers:dict, user=Depends(get_current_user)):

    correct = supabase.table("assessment_questions") \
        .select("*") \
        .eq("assessment_id", assessment_id) \
        .execute().data

    score = calculate_score(answers, correct)

    supabase.table("student_submissions").insert({
        "school_id": user["school_id"],
        "assessment_id": assessment_id,
        "student_id": student_id,
        "uploaded_by": user["id"],
        "extracted_answers": answers,
        "score": score
    }).execute()

    return {"score":score}

@app.get("/student-progress/{student_id}")
def student_progress(student_id:str,user=Depends(get_current_user)):

    data = supabase.table("student_submissions") \
        .select("score,created_at") \
        .eq("student_id", student_id) \
        .order("created_at") \
        .execute()

    return data.data

import pandas as pd

@app.post("/students-upload")
async def upload_students(class_id:str,file:UploadFile = File(...),user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    df = pd.read_csv(file.file)

    for _,row in df.iterrows():

        supabase.table("students").insert({

            "school_id":user["school_id"],
            "class_id":class_id,
            "name":row["name"],
            "status":row.get("status","CURSANDO")

        }).execute()

    return {"message":"Alunos importados"}

@app.put("/students/{student_id}")
def update_student(student_id:str,name:str,status:str,user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    supabase.table("students").update({

        "name":name,
        "status":status

    }).eq("id",student_id).execute()

    return {"message":"Atualizado"}

@app.delete("/students/{student_id}")
def delete_student(student_id:str,user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    supabase.table("students").delete().eq("id",student_id).execute()

    return {"message":"Aluno removido"}
# ----------------------------------------------------
# ROTAS BÁSICAS
# ----------------------------------------------------

@app.get("/")
def root():
    return {"status": "CALIA 2.0 Backend Online 🚀"}

@app.get("/me")
def get_me(user=Depends(get_current_user)):
    return user

# ----------------------------------------------------
# ESCOLAS
# ----------------------------------------------------

@app.post("/schools")
def create_school(data: SchoolCreate, user=Depends(get_current_user)):
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Acesso negado")

    school_response = supabase.table("schools").insert({
        "name": data.name,
        "slug": data.slug,
        "plan": data.plan
    }).execute()

    school = school_response.data[0]

    admin_email = f"admin@{data.slug}.com"
    admin_password = "12345678"

    auth_response = supabase.auth.admin.create_user({
        "email": admin_email,
        "password": admin_password,
        "email_confirm": True
    })

    supabase.table("profiles").insert({
        "id": auth_response.user.id,
        "school_id": school["id"],
        "role": "admin",
        "full_name": "Administrador"
    }).execute()

    log_activity(user, "create", "school_with_admin")

    return {
        "school": school,
        "admin_email": admin_email,
        "admin_password": admin_password
    }

@app.get("/schools")
def get_schools(user=Depends(get_current_user)):
    if user["role"] == "super_admin":
        return supabase.table("schools").select("*").execute().data

    return supabase.table("schools") \
        .select("*") \
        .eq("id", user["school_id"]) \
        .execute().data

@app.post("/classes")
def create_class(data: ClassCreate, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    new_class = supabase.table("classes").insert({
        "school_id": user["school_id"],
        "name": data.name,
        "year": data.year
    }).execute()

    return new_class.data

@app.get("/classes")
def list_classes(user=Depends(get_current_user)):

    classes = supabase.table("classes") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute()

    return classes.data

@app.post("/assign-teacher")
def assign_teacher(teacher_id:str, class_id:str, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    supabase.table("teacher_classes").insert({
        "teacher_id": teacher_id,
        "class_id": class_id
    }).execute()

    return {"message":"Professor vinculado"}


# ----------------------------------------------------
# PROFESSORES (ADMIN)
# ----------------------------------------------------

@app.post("/teachers")
def create_teacher(data: TeacherCreate, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin pode criar professor")

    temp_password = "12345678"

    auth_response = supabase.auth.admin.create_user({
        "email": data.email,
        "password": temp_password,
        "email_confirm": True
    })

    if not auth_response.user:
        raise HTTPException(status_code=400, detail="Erro ao criar professor")

    supabase.table("profiles").insert({
        "id": auth_response.user.id,
        "school_id": user["school_id"],
        "role": "professor",
        "full_name": data.full_name
    }).execute()

    log_activity(user, "create", "teacher")

    return {
        "email": data.email,
        "temporary_password": temp_password
    }

@app.get("/teachers")
def list_teachers(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin pode listar professores")

    return supabase.table("profiles") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .eq("role", "professor") \
        .execute().data

@app.post("/ocr-upload")
async def ocr_upload(
    student_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):

    if user["role"] != "professor":
        raise HTTPException(status_code=403, detail="Apenas professor pode usar OCR")

    # Verificar se aluno pertence à mesma escola
    student_check = supabase.table("students") \
        .select("*") \
        .eq("id", student_id) \
        .eq("school_id", user["school_id"]) \
        .execute()

    if not student_check.data:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")

    # Salvar arquivo temporariamente
    file_id = str(uuid.uuid4())
    file_path = f"/tmp/{file_id}_{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Simulação OCR (substituir depois pelo módulo real)
    extracted_text = f"Texto extraído simulado do arquivo {file.filename}"

    # Salvar no banco com student_id
    supabase.table("ocr_uploads").insert({
        "school_id": user["school_id"],
        "student_id": student_id,
        "uploaded_by": user["id"],
        "file_url": file.filename,
        "extracted_text": extracted_text,
        "status": "completed"
    }).execute()

    log_activity(user, "create", "ocr_upload")

    return {
        "message": "OCR processado com sucesso",
        "extracted_text": extracted_text
    }

@app.get("/ocr-history")
def ocr_history(user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403, detail="Apenas professor pode acessar histórico")

    history = supabase.table("ocr_uploads") \
        .select("*") \
        .eq("uploaded_by", user["id"]) \
        .order("created_at", desc=True) \
        .execute()

    return history.data

@app.post("/assessments")
def create_assessment(data: AssessmentCreate, user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403)

    new_assessment = supabase.table("assessments").insert({
        "school_id": user["school_id"],
        "class_id": data.class_id,
        "created_by": user["id"],
        "title": data.title,
        "total_questions": data.total_questions
    }).execute()

    return new_assessment.data
@app.post("/assessment-question")
def create_question(data: QuestionCreate, user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403)

    supabase.table("assessment_questions").insert({
        "assessment_id": data.assessment_id,
        "question_number": data.question_number,
        "correct_answer": data.correct_answer,
        "weight": data.weight
    }).execute()

    return {"message":"Questão cadastrada"}



# ----------------------------------------------------
# ALUNOS
# ----------------------------------------------------

@app.post("/students")
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

@app.get("/students")
def list_students(user=Depends(get_current_user)):
    return supabase.table("students") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute().data
