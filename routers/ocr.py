import uuid
import os
import cv2
import numpy as np
from PIL import Image

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

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Imagem muito grande"
        )

    file_id = str(uuid.uuid4())
    file_path = f"/tmp/{file_id}.jpg"

    # salvar imagem
    with open(file_path, "wb") as f:
        f.write(contents)

    # otimização: reduzir resolução
    img = cv2.imread(file_path)

    h, w = img.shape[:2]

    altura_max = 1000

    if h > altura_max:

        proporcao = altura_max / h
        novo_w = int(w * proporcao)

        img = cv2.resize(img, (novo_w, altura_max))

        cv2.imwrite(file_path, img)

    # buscar gabarito
    assessment = supabase.table("assessments") \
        .select("*") \
        .eq("id", assessment_id) \
        .execute()

    if not assessment.data:
        raise HTTPException(status_code=404)

    gabarito = assessment.data[0]["gabarito"].split(",")

    gabarito = [g.strip().upper() for g in gabarito]

    # executar OCR
    respostas = read_answer_sheet(file_path, gabarito)

    # calcular nota
    score = calculate_score(respostas, gabarito)

    # salvar resultado
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
