from fastapi import APIRouter, Depends
from core.auth import get_current_user
from core.config import supabase
from services.grading_service import calculate_score

router = APIRouter()


@router.post("/submit-answers")
def submit_answers(data: dict, user=Depends(get_current_user)):

    assessment_id = data["assessment_id"]
    student_id = data["student_id"]
    answers = data["answers"]

    score = calculate_score(
        assessment_id,
        answers
    )

    supabase.table("student_submissions").insert({

        "school_id": user["school_id"],
        "assessment_id": assessment_id,
        "student_id": student_id,
        "uploaded_by": user["id"],
        "extracted_answers": answers,
        "score": score

    }).execute()

    return {"score": score}