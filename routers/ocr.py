from fastapi import APIRouter, UploadFile, File, Depends, Body
import uuid
import shutil

from core.auth import get_current_user
from core.config import supabase

from services.ocr_service import read_answer_sheet
from services.grading_service import calculate_score

router = APIRouter()


# ===============================
# OCR CORRECTION
# ===============================

@router.post("/correct")

async def correct_exam(
    assessment_id:str,
    student_id:str,
    file:UploadFile = File(...),
    user=Depends(get_current_user)
):

    file_path = f"/tmp/{uuid.uuid4()}.jpg"

    with open(file_path,"wb") as buffer:
        shutil.copyfileobj(file.file,buffer)

    # buscar gabarito

    questions = supabase.table("assessment_questions") \
        .select("*") \
        .eq("assessment_id",assessment_id) \
        .order("question_number") \
        .execute().data

    gabarito = [
        q["correct_answer"] for q in questions
    ]

    # rodar OCR

    answers = read_answer_sheet(
        file_path,
        gabarito
    )

    # calcular nota

    score = calculate_score(
        assessment_id,
        answers
    )

    # salvar resultado

    supabase.table("student_submissions").insert({

        "school_id":user["school_id"],
        "assessment_id":assessment_id,
        "student_id":student_id,
        "uploaded_by":user["id"],
        "extracted_answers":answers,
        "score":score

    }).execute()

    return {
        "answers":answers,
        "score":score
    }


# ===============================
# MANUAL CORRECTION
# ===============================

@router.post("/submit-answers")

def submit_answers(
    data: dict = Body(...),
    user=Depends(get_current_user)
):

    assessment_id = data["assessment_id"]
    student_id = data["student_id"]
    answers = data["answers"]

    score = calculate_score(
        assessment_id,
        answers
    )

    supabase.table("student_submissions").insert({

        "school_id":user["school_id"],
        "assessment_id":assessment_id,
        "student_id":student_id,
        "uploaded_by":user["id"],
        "extracted_answers":answers,
        "score":score

    }).execute()

    return {
        "score":score
    }