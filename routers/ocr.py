import uuid
import shutil
import os

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from core.auth import get_current_user
from core.config import supabase

from services.ocr_service import read_answer_sheet
from services.grading_service import calculate_score

router = APIRouter(prefix="/ocr", tags=["OCR"])


MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/correct")
async def correct_exam(
    assessment_id: str,
    student_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):

    if user["role"] != "professor":
        raise HTTPException(status_code=403)

    # ------------------------------------------------
    # Validar tamanho do arquivo
    # ------------------------------------------------

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Imagem muito grande (máx 5MB)"
        )

    file_id = str(uuid.uuid4())
    file_path = f"/tmp/{file_id}.jpg"

    with open(file_path, "wb") as buffer:
        buffer.write(contents)

    # ------------------------------------------------
    # Buscar gabarito da avaliação
    # ------------------------------------------------

    assessment = supabase.table("assessments") \
        .select("*") \
        .eq("id", assessment_id) \
        .execute()

    if not assessment.data:
        raise HTTPException(status_code=404)

    gabarito = assessment.data[0]["gabarito"].split(",")

    gabarito = [g.strip().upper() for g in gabarito]

    # ------------------------------------------------
    # EXECUTAR OCR (seu código)
    # ------------------------------------------------

    try:

        respostas = read_answer_sheet(file_path, gabarito)

    except Exception as e:

        os.remove(file_path)

        raise HTTPException(
            status_code=400,
            detail=f"Erro OCR: {str(e)}"
        )

    # ------------------------------------------------
    # CALCULAR NOTA
    # ------------------------------------------------

    score = calculate_score(respostas, gabarito)

    # ------------------------------------------------
    # SALVAR RESULTADO
    # ------------------------------------------------

    supabase.table("student_submissions").insert({

        "school_id": user["school_id"],
        "assessment_id": assessment_id,
        "student_id": student_id,
        "uploaded_by": user["id"],
        "extracted_answers": respostas,
        "score": score

    }).execute()

    os.remove(file_path)

    return {
        "answers": respostas,
        "score": score
    }
