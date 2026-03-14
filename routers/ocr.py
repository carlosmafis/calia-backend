from fastapi import APIRouter, UploadFile, File, Depends
import uuid
import shutil

from core.auth import get_current_user
from core.config import supabase

from services.ocr_service import process_image
from services.grading_service import calculate_score

router = APIRouter()

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

    answers = process_image(file_path)

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
        "answers":answers,
        "score":score
    }