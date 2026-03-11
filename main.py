import os
import uuid
import shutil
import pandas as pd

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from supabase import create_client
from dotenv import load_dotenv

from pydantic import BaseModel
from typing import Optional, Dict
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


class StudentUpdate(BaseModel):
    name: str
    status: str


class TeacherCreate(BaseModel):
    email: str
    full_name: str


class ClassCreate(BaseModel):
    name: str
    year: str


class AssignTeacher(BaseModel):
    teacher_id: str
    class_id: str


class AssessmentCreate(BaseModel):
    class_id: str
    title: str
    total_questions: int


class QuestionCreate(BaseModel):
    assessment_id: str
    question_number: int
    correct_answer: str
    weight: float


class SubmitAnswers(BaseModel):
    assessment_id: str
    student_id: str
    answers: Dict[str, str]

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

    profile = supabase.table("profiles").select("*").eq("id", user_data.id).execute()

    if not profile.data:
        raise HTTPException(status_code=403, detail="Perfil não encontrado")

    return profile.data[0]

# ----------------------------------------------------
# UTILIDADES
# ----------------------------------------------------

def log_activity(user, action, entity):

    supabase.table("activity_logs").insert({
        "school_id": user["school_id"],
        "user_id": user["id"],
        "action": action,
        "entity": entity,
        "created_at": datetime.utcnow().isoformat()
    }).execute()


def calculate_score(student_answers, correct_answers):

    score = 0

    for q in correct_answers:

        number = str(q["question_number"])
        correct = q["correct_answer"]
        weight = q["weight"]

        if student_answers.get(number) == correct:
            score += weight

    return score

# ----------------------------------------------------
# ROOT
# ----------------------------------------------------

@app.get("/")
def root():
    return {"status": "CALIA Backend Online"}

@app.get("/me")
def get_me(user=Depends(get_current_user)):
    return user

# ----------------------------------------------------
# ESCOLAS
# ----------------------------------------------------

@app.post("/schools")
def create_school(data: SchoolCreate, user=Depends(get_current_user)):

    if user["role"] != "super_admin":
        raise HTTPException(status_code=403)

    school = supabase.table("schools").insert({
        "name": data.name,
        "slug": data.slug,
        "plan": data.plan
    }).execute().data[0]

    admin_email = f"admin@{data.slug}.com"
    admin_password = "12345678"

    auth_user = supabase.auth.admin.create_user({
        "email": admin_email,
        "password": admin_password,
        "email_confirm": True
    })

    supabase.table("profiles").insert({
        "id": auth_user.user.id,
        "school_id": school["id"],
        "role": "admin",
        "full_name": "Administrador"
    }).execute()

    return {
        "school": school,
        "admin_email": admin_email,
        "admin_password": admin_password
    }

# ----------------------------------------------------
# TURMAS
# ----------------------------------------------------

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

# ----------------------------------------------------
# PROFESSOR x TURMA
# ----------------------------------------------------

@app.post("/assign-teacher")
def assign_teacher(data: AssignTeacher, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    existing = supabase.table("teacher_classes") \
        .select("*") \
        .eq("teacher_id", data.teacher_id) \
        .eq("class_id", data.class_id) \
        .execute()

    if existing.data:
        return {"message": "Professor já vinculado"}

    supabase.table("teacher_classes").insert({
        "teacher_id": data.teacher_id,
        "class_id": data.class_id
    }).execute()

    return {"message": "Professor vinculado"}

# ----------------------------------------------------
# PROFESSORES
# ----------------------------------------------------

@app.post("/teachers")
def create_teacher(data: TeacherCreate, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    password = "12345678"

    auth = supabase.auth.admin.create_user({
        "email": data.email,
        "password": password,
        "email_confirm": True
    })

    supabase.table("profiles").insert({
        "id": auth.user.id,
        "school_id": user["school_id"],
        "role": "professor",
        "full_name": data.full_name
    }).execute()

    return {"email": data.email, "temporary_password": password}


@app.get("/teachers")
def list_teachers(user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    return supabase.table("profiles") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .eq("role", "professor") \
        .execute().data

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


@app.put("/students/{student_id}")
def update_student(student_id: str, data: StudentUpdate, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    supabase.table("students").update({
        "name": data.name,
        "status": data.status
    }).eq("id", student_id).execute()

    return {"message": "Atualizado"}


@app.delete("/students/{student_id}")
def delete_student(student_id: str, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    supabase.table("students").delete().eq("id", student_id).execute()

    return {"message": "Aluno removido"}

# ----------------------------------------------------
# IMPORTAÇÃO DE ALUNOS
# ----------------------------------------------------

@app.post("/students-upload")
async def upload_students(class_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    if file.filename.endswith(".xlsx"):
        df = pd.read_excel(file.file)
    else:
        df = pd.read_csv(file.file)

    for _, row in df.iterrows():

        supabase.table("students").insert({
            "school_id": user["school_id"],
            "class_id": class_id,
            "name": row["name"],
            "status": row.get("status", "CURSANDO")
        }).execute()

    return {"message": "Alunos importados"}

# ----------------------------------------------------
# AVALIAÇÕES
# ----------------------------------------------------

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

    return {"message": "Questão cadastrada"}

# ----------------------------------------------------
# OCR
# ----------------------------------------------------

@app.post("/ocr-upload")
async def ocr_upload(student_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403)

    file_id = str(uuid.uuid4())
    file_path = f"/tmp/{file_id}_{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extracted_text = f"OCR simulado {file.filename}"

    supabase.table("ocr_uploads").insert({
        "school_id": user["school_id"],
        "student_id": student_id,
        "uploaded_by": user["id"],
        "file_url": file.filename,
        "extracted_text": extracted_text,
        "status": "completed"
    }).execute()

    os.remove(file_path)

    return {"message": "OCR processado"}

# ----------------------------------------------------
# CORREÇÃO
# ----------------------------------------------------

@app.post("/submit-answers")
def submit_answers(data: SubmitAnswers, user=Depends(get_current_user)):

    correct = supabase.table("assessment_questions") \
        .select("*") \
        .eq("assessment_id", data.assessment_id) \
        .execute().data

    score = calculate_score(data.answers, correct)

    supabase.table("student_submissions").insert({
        "school_id": user["school_id"],
        "assessment_id": data.assessment_id,
        "student_id": data.student_id,
        "uploaded_by": user["id"],
        "extracted_answers": data.answers,
        "score": score
    }).execute()

    return {"score": score}

# ----------------------------------------------------
# DASHBOARD
# ----------------------------------------------------

@app.get("/student-progress/{student_id}")
def student_progress(student_id: str, user=Depends(get_current_user)):

    data = supabase.table("student_submissions") \
        .select("score,created_at") \
        .eq("student_id", student_id) \
        .order("created_at") \
        .execute()

    return data.data
