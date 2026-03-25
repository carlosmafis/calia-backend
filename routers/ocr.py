from fastapi import APIRouter, UploadFile, File, Depends, Form
from pydantic import BaseModel
import uuid
import shutil

from core.auth import get_current_user
from core.config import supabase

from services.ocr_service import read_answer_sheet
from services.grading_service import calculate_score

router = APIRouter()


@router.post("/correct")
async def correct_exam(
    assessment_id: str = Form(...),
    student_id: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):

    file_path = f"/tmp/{uuid.uuid4()}.jpg"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    questions = (
        supabase.table("assessment_questions")
        .select("*")
        .eq("assessment_id", data.assessment_id)
        .order("question_number")
        .execute()
        .data
    )

    gabarito = [q["correct_answer"] for q in questions]

    ocr_result = read_answer_sheet(
        file_path,
        gabarito
    )

    answers = ocr_result["answers"]
    debug_image = ocr_result["debug_image"]

    if isinstance(answers, list):
        answers = {str(i + 1): v for i, v in enumerate(answers)}

    print("RESPOSTAS OCR:", answers)

    score = calculate_score(
        assessment_id,
        answers
    )

    # Buscar class_id da avaliação
    assessment = supabase.table("assessments") \
        .select("class_id") \
        .eq("id", data.assessment_id) \
        .single() \
        .execute()
    
    class_id = assessment.data.get("class_id") if assessment.data else None
    if not class_id:
        raise HTTPException(status_code=400, detail="Avaliação não encontrada ou sem turma")

    supabase.table("student_submissions").insert({

        "school_id": user["school_id"],
        "assessment_id": data.assessment_id,
        "student_id": data.student_id,
        "class_id": class_id,
        "uploaded_by": user["id"],
        "extracted_answers": answers,
        "score": score

    }).execute()

    return {
        "answers": answers,
        "score": score,
        "debug_image": debug_image
    }


class ConfirmCorrection(BaseModel):
    assessment_id: str
    student_id: str
    answers: dict  # Pode ser dict ou array, será convertido


class MarkAbsentRequest(BaseModel):
    assessment_id: str
    student_id: str


@router.post("/mark-absent")
def mark_absent(
    data: MarkAbsentRequest,
    user=Depends(get_current_user)
):
    """Marca um aluno como ausente na avaliação"""
    # Buscar class_id da avaliação
    assessment = supabase.table("assessments") \
        .select("class_id") \
        .eq("id", data.assessment_id) \
        .single() \
        .execute()
    
    class_id = assessment.data.get("class_id") if assessment.data else None
    if not class_id:
        raise HTTPException(status_code=400, detail="Avaliação não encontrada ou sem turma")

    # Verificar se ja existe submissao
    existing = supabase.table("student_submissions") \
        .select("id") \
        .eq("assessment_id", data.assessment_id) \
        .eq("student_id", data.student_id) \
        .execute()
    
    submission_data = {
        "school_id": user["school_id"],
        "assessment_id": data.assessment_id,
        "student_id": data.student_id,
        "class_id": class_id,
        "uploaded_by": user["id"],
        "status": "ausente",
        "extracted_answers": {},
        "score": None
    }
    
    if existing.data and len(existing.data) > 0:
        # Atualizar submissao existente
        supabase.table("student_submissions") \
            .update(submission_data) \
            .eq("id", existing.data[0]["id"]) \
            .execute()
    else:
        # Criar nova submissao
        supabase.table("student_submissions").insert(submission_data).execute()

    return {
        "status": "ausente",
        "message": "Aluno marcado como ausente"
    }


@router.post("/confirm")
def confirm_correction(
    data: ConfirmCorrection,
    user=Depends(get_current_user)
):

    # Converter answers de array para dict se necessário
    answers = data.answers
    # 🔥 Corrige lista
    if isinstance(answers, list):
        answers = {str(i + 1): v for i, v in enumerate(answers)}
    
    # 🔥 Corrige dict vindo como 0–9
    elif isinstance(answers, dict):
        answers = {str(int(k) + 1): v for k, v in answers.items()}
    
    score = calculate_score(
        data.assessment_id,
        answers
    )

    # Buscar class_id da avaliacao
    assessment = supabase.table("assessments") \
        .select("class_id") \
        .eq("id", data.assessment_id) \
        .single() \
        .execute()
    
    class_id = assessment.data.get("class_id") if assessment.data else None
    if not class_id:
        raise HTTPException(status_code=400, detail="Avaliacao nao encontrada ou sem turma")

    # Verificar se ja existe submissao
    existing = supabase.table("student_submissions") \
        .select("id") \
        .eq("assessment_id", data.assessment_id) \
        .eq("student_id", data.student_id) \
        .execute()
    
    submission_data = {
        "school_id": user["school_id"],
        "assessment_id": data.assessment_id,
        "student_id": data.student_id,
        "class_id": class_id,
        "uploaded_by": user["id"],
        "extracted_answers": answers,
        "score": score
    }
    
    if existing.data and len(existing.data) > 0:
        # Atualizar submissao existente
        supabase.table("student_submissions") \
            .update(submission_data) \
            .eq("id", existing.data[0]["id"]) \
            .execute()
    else:
        # Criar nova submissao
        supabase.table("student_submissions").insert(submission_data).execute()

    return {
        "score": score,
        "message": "Correcao salva com sucesso"
    }
