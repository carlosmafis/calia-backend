import uuid
import shutil
import os

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from core.auth import get_current_user
from core.config import supabase

from services.ocr_service import read_answer_sheet

answers = read_answer_sheet(file_path, gabarito)
score = calculate_score(answers, gabarito)

router = APIRouter(prefix="/ocr", tags=["OCR"])


@router.post("/upload")
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

    return {
        "message": "OCR processado",
        "text": extracted_text
    }
