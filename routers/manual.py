from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict

from core.auth import get_current_user
from core.config import supabase
from services.grading_service import calculate_score

router = APIRouter(tags=["Manual Correction"])


class ManualSubmission(BaseModel):
    assessment_id: str
    student_id: str
    answers: Dict[str, str]


@router.post("/submit-answers")
def submit_answers(data: ManualSubmission, user=Depends(get_current_user)):

    if user["role"] not in ("professor", "admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")

    score = calculate_score(
        data.assessment_id,
        data.answers
    )

    # Buscar class_id da avaliação
    assessment = supabase.table("assessments") \
        .select("class_id") \
        .eq("id", data.assessment_id) \
        .single() \
        .execute()
    
    class_id = assessment.data.get("class_id") if assessment.data else None

    supabase.table("student_submissions").insert({
        "school_id": user["school_id"],
        "assessment_id": data.assessment_id,
        "student_id": data.student_id,
        "class_id": class_id,
        "uploaded_by": user["id"],
        "extracted_answers": data.answers,
        "score": score,
        "method": "manual"
    }).execute()

    return {"score": score, "answers": data.answers}
