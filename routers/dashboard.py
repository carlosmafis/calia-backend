from fastapi import APIRouter, Depends
from core.config import supabase
from core.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/student-progress/{student_id}")
def student_progress(student_id: str, user=Depends(get_current_user)):

    data = supabase.table("student_submissions") \
        .select("score,created_at") \
        .eq("student_id", student_id) \
        .order("created_at") \
        .execute()

    return data.data
