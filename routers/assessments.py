from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
import logging

from core.auth import get_current_user
from core.config import supabase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Assessments"])


# ==========================
# MODELOS
# ==========================

class QuestionItem(BaseModel):
    question_number: int
    correct_answer: str
    weight: float = 1.0


class AssessmentCreate(BaseModel):
    class_id: str
    subject_id: str
    title: str
    questions: List[QuestionItem]
    bimestre: int = 1  # 1, 2, 3 ou 4


# ==========================
# LISTAR AVALIAÇÕES
# ==========================

@router.get("/")
def list_assessments(user=Depends(get_current_user)):

    if user["role"] == "professor":
        # Professor vê avaliações das suas turmas
        teacher_classes = supabase.table("teacher_classes") \
            .select("class_id") \
            .eq("teacher_id", user["id"]) \
            .execute()

        class_ids = [tc["class_id"] for tc in (teacher_classes.data or [])]

        if not class_ids:
            return []

        data = supabase.table("assessments") \
            .select("*") \
            .eq("school_id", user["school_id"]) \
            .in_("class_id", class_ids) \
            .execute()

        return data.data

    # Admin e super_admin veem tudo da escola
    data = supabase.table("assessments") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute()

    return data.data


# ==========================
# DETALHES DE UMA AVALIAÇÃO
# ==========================

@router.get("/{assessment_id}")
def get_assessment(assessment_id: str, user=Depends(get_current_user)):

    assessment = supabase.table("assessments") \
        .select("*") \
        .eq("id", assessment_id) \
        .single() \
        .execute()

    if not assessment.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    # Buscar questões
    questions = supabase.table("assessment_questions") \
        .select("*") \
        .eq("assessment_id", assessment_id) \
        .order("question_number") \
        .execute()

    result = assessment.data
    result["questions"] = questions.data or []
    
    # Montar gabarito (answer_key) a partir das questões
    answer_key = {}
    if questions.data:
        for q in questions.data:
            answer_key[str(q["question_number"])] = q["correct_answer"]
    
    result["answer_key"] = answer_key

    return result


# ==========================
# CRIAR AVALIAÇÃO (ROTA 1: /create-full)
# ==========================

@router.post("/create-full")
def create_assessment_full(data: AssessmentCreate, user=Depends(get_current_user)):
    """Criar avaliação com todas as questões de uma vez"""
    
    logger.info(f"POST /assessments/create-full - User: {user.get('email')}")
    
    # Permitir professor e admin criarem avaliações
    if user["role"] not in ("professor", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão para criar avaliação")

    # Validar dados
    if not data.class_id:
        raise HTTPException(status_code=400, detail="class_id é obrigatório")
    if not data.subject_id:
        raise HTTPException(status_code=400, detail="subject_id é obrigatório")
    if not data.title or not data.title.strip():
        raise HTTPException(status_code=400, detail="title é obrigatório")
    if not data.questions or len(data.questions) == 0:
        raise HTTPException(status_code=400, detail="questions não pode estar vazio")

    try:
        assessment = supabase.table("assessments").insert({
            "school_id": user["school_id"],
            "class_id": data.class_id,
            "subject_id": data.subject_id,
            "created_by": user["id"],
            "title": data.title.strip(),
            "total_questions": len(data.questions),
            "bimestre": data.bimestre
        }).execute().data[0]

        rows = []
        for q in data.questions:
            rows.append({
                "assessment_id": assessment["id"],
                "question_number": q.question_number,
                "correct_answer": q.correct_answer,
                "weight": q.weight
            })

        if rows:
            supabase.table("assessment_questions").insert(rows).execute()

        logger.info(f"Assessment created: {assessment['id']}")
        return {"message": "Avaliação criada com sucesso", "data": assessment}
    except Exception as e:
        logger.error(f"Error creating assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar avaliação: {str(e)}")


# ==========================
# RESULTADOS DE UMA AVALIAÇÃO
# ==========================

@router.get("/{assessment_id}/results")
def get_assessment_results(assessment_id: str, class_id: str = None, user=Depends(get_current_user)):

    try:
        query = supabase.table("student_submissions") \
            .select("id, assessment_id, student_id, score, extracted_answers, created_at, students(id, name, registration_number), assessments(class_id)") \
            .eq("assessment_id", assessment_id)
        
        submissions = query.execute()
        
        # Filtrar por class_id se fornecido
        results = []
        if submissions.data:
            for sub in submissions.data:
                # Buscar class_id da avaliação
                sub_class_id = None
                if isinstance(sub.get("assessments"), dict):
                    sub_class_id = sub.get("assessments", {}).get("class_id")
                
                result = {
                    "id": sub.get("id"),
                    "assessment_id": sub.get("assessment_id"),
                    "student_id": sub.get("student_id"),
                    "student_name": sub.get("students", {}).get("name") if isinstance(sub.get("students"), dict) else "Aluno",
                    "score": sub.get("score"),
                    "answers": sub.get("extracted_answers"),
                    "created_at": sub.get("created_at"),
                    "class_id": sub_class_id
                }
                results.append(result)
        
        return results
    except Exception as e:
        print(f"Erro ao buscar resultados: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar resultados: {str(e)}")


@router.get("/{assessment_id}/submissions")
def get_assessment_submissions(assessment_id: str, user=Depends(get_current_user)):
    """Endpoint alternativo para compatibilidade com frontend"""
    try:
        # Buscar submissões com informações do aluno e avaliação
        # Primeiro tenta com JOIN, se falhar retorna sem JOIN
        try:
            query = supabase.table("student_submissions") \
                .select("id, assessment_id, student_id, score, extracted_answers, created_at, students(id, name, registration_number), assessments(class_id)") \
                .eq("assessment_id", assessment_id)
            
            submissions = query.execute()
        except:
            # Se o JOIN falhar, busca sem JOIN
            query = supabase.table("student_submissions") \
                .select("id, assessment_id, student_id, score, extracted_answers, created_at, class_id") \
                .eq("assessment_id", assessment_id)
            
            submissions = query.execute()
        
        results = []
        if submissions.data:
            for sub in submissions.data:
                # Tentar buscar nome do aluno
                student_name = "Aluno"
                if isinstance(sub.get("students"), dict):
                    student_name = sub.get("students", {}).get("name", "Aluno")
                
                # Buscar class_id da avaliação
                class_id = None
                if isinstance(sub.get("assessments"), dict):
                    class_id = sub.get("assessments", {}).get("class_id")
                elif sub.get("class_id"):
                    class_id = sub.get("class_id")
                
                result = {
                    "id": sub.get("id"),
                    "assessment_id": sub.get("assessment_id"),
                    "student_id": sub.get("student_id"),
                    "student_name": student_name,
                    "score": sub.get("score"),
                    "answers": sub.get("extracted_answers"),
                    "created_at": sub.get("created_at"),
                    "class_id": class_id
                }
                results.append(result)
        
        print(f"Retornando {len(results)} submissões para avaliação {assessment_id}")
        return results
    except Exception as e:
        print(f"Erro ao buscar submissões: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar submissões: {str(e)}")


@router.get("/{assessment_id}/results/")
def get_assessment_results_slash(assessment_id: str, class_id: str = None, user=Depends(get_current_user)):
    """Rota alternativa com barra final"""
    return get_assessment_results(assessment_id, class_id, user)


@router.get("/{assessment_id}/submissions/")
def get_assessment_submissions_slash(assessment_id: str, user=Depends(get_current_user)):
    """Rota alternativa com barra final"""
    return get_assessment_submissions(assessment_id, user)


# ==========================
# EDITAR AVALIAÇÃO
# ==========================

class AssessmentUpdate(BaseModel):
    title: str = None
    questions: List[QuestionItem] = None
    bimestre: int = None  # 1, 2, 3 ou 4


@router.put("/{assessment_id}")
def update_assessment(assessment_id: str, data: AssessmentUpdate, user=Depends(get_current_user)):
    """Editar avaliação (título e/ou questões)"""
    
    logger.info(f"PUT /assessments/{assessment_id} - User: {user.get('email')}")
    
    try:
        # Buscar avaliação
        assessment = supabase.table("assessments") \
            .select("*") \
            .eq("id", assessment_id) \
            .single() \
            .execute()
        
        if not assessment.data:
            raise HTTPException(status_code=404, detail="Avaliação não encontrada")
        
        # Verificar permissão (apenas criador ou admin)
        if user["role"] not in ("admin", "super_admin") and assessment.data["created_by"] != user["id"]:
            raise HTTPException(status_code=403, detail="Sem permissão para editar esta avaliação")
        
        # Atualizar título e/ou bimestre se fornecidos
        update_data = {}
        if data.title:
            update_data["title"] = data.title.strip()
        if data.bimestre is not None:
            if data.bimestre not in (1, 2, 3, 4):
                raise HTTPException(status_code=400, detail="Bimestre deve ser 1, 2, 3 ou 4")
            update_data["bimestre"] = data.bimestre
        
        if update_data:
            supabase.table("assessments") \
                .update(update_data) \
                .eq("id", assessment_id) \
                .execute()
        
        # Atualizar questões se fornecidas
        if data.questions:
            # Deletar questões antigas
            supabase.table("assessment_questions") \
                .delete() \
                .eq("assessment_id", assessment_id) \
                .execute()
            
            # Inserir novas questões
            rows = []
            for q in data.questions:
                rows.append({
                    "assessment_id": assessment_id,
                    "question_number": q.question_number,
                    "correct_answer": q.correct_answer,
                    "weight": q.weight
                })
            
            if rows:
                supabase.table("assessment_questions").insert(rows).execute()
            
            # Atualizar total de questões
            supabase.table("assessments") \
                .update({"total_questions": len(data.questions)}) \
                .eq("id", assessment_id) \
                .execute()
        
        logger.info(f"Assessment updated: {assessment_id}")
        return {"message": "Avaliação atualizada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar avaliação: {str(e)}")


# ==========================
# DELETAR AVALIAÇÃO
# ==========================

@router.delete("/{assessment_id}")
def delete_assessment(assessment_id: str, user=Depends(get_current_user)):
    """Deletar avaliação"""
    
    logger.info(f"DELETE /assessments/{assessment_id} - User: {user.get('email')}")
    
    try:
        # Buscar avaliação
        assessment = supabase.table("assessments") \
            .select("*") \
            .eq("id", assessment_id) \
            .single() \
            .execute()
        
        if not assessment.data:
            raise HTTPException(status_code=404, detail="Avaliação não encontrada")
        
        # Verificar permissão (apenas criador ou admin)
        if user["role"] not in ("admin", "super_admin") and assessment.data["created_by"] != user["id"]:
            raise HTTPException(status_code=403, detail="Sem permissão para deletar esta avaliação")
        
        # Deletar questões
        supabase.table("assessment_questions") \
            .delete() \
            .eq("assessment_id", assessment_id) \
            .execute()
        
        # Deletar submissões
        supabase.table("student_submissions") \
            .delete() \
            .eq("assessment_id", assessment_id) \
            .execute()
        
        # Deletar avaliação
        supabase.table("assessments") \
            .delete() \
            .eq("id", assessment_id) \
            .execute()
        
        logger.info(f"Assessment deleted: {assessment_id}")
        return {"message": "Avaliação deletada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao deletar avaliação: {str(e)}")



# ==========================
# ANULAR QUESTÃO
# ==========================

class AnnulQuestionRequest(BaseModel):
    question_number: int


@router.post("/{assessment_id}/annul-question")
def annul_question(
    assessment_id: str,
    data: AnnulQuestionRequest,
    user=Depends(get_current_user)
):
    """Anula uma questão e atualiza as notas de todos os alunos corrigidos"""
    
    try:
        # Verificar permissão
        assessment = supabase.table("assessments") \
            .select("*") \
            .eq("id", assessment_id) \
            .single() \
            .execute()
        
        if not assessment.data:
            raise HTTPException(status_code=404, detail="Avaliação não encontrada")
        
        # Buscar todas as submissões da avaliação
        submissions = supabase.table("student_submissions") \
            .select("*") \
            .eq("assessment_id", assessment_id) \
            .execute()
        
        if not submissions.data:
            return {"message": "Nenhuma submissão para atualizar", "updated_count": 0}
        
        # Para cada submissão, atualizar o score
        from services.grading_service import calculate_score
        
        updated_count = 0
        for submission in submissions.data:
            try:
                # Obter respostas
                answers = submission.get("extracted_answers", {})
                if isinstance(answers, str):
                    import json
                    answers = json.loads(answers)
                
                # Criar answers_with_weight com a questão anulada
                answers_with_weight = {}
                
                # Buscar gabarito
                questions = supabase.table("assessment_questions") \
                    .select("*") \
                    .eq("assessment_id", assessment_id) \
                    .execute()
                
                for q in (questions.data or []):
                    q_num = str(q["question_number"])
                    answer = answers.get(q_num, "BRANCO")
                    
                    if q["question_number"] == data.question_number:
                        # Marcar como anulada
                        answers_with_weight[q_num] = {
                            "type": "ANULADA",
                            "answer": None,
                            "weight": 1
                        }
                    else:
                        # Manter resposta original
                        answers_with_weight[q_num] = {
                            "type": "MARCADA" if answer in ["A","B","C","D","E"] else answer,
                            "answer": answer if answer in ["A","B","C","D","E"] else None,
                            "weight": 1 if answer in ["A","B","C","D","E"] else 0
                        }
                
                # Recalcular score
                new_score = calculate_score(assessment_id, answers, answers_with_weight)
                
                # Atualizar submissão
                supabase.table("student_submissions") \
                    .update({"score": new_score}) \
                    .eq("id", submission["id"]) \
                    .execute()
                
                updated_count += 1
            except Exception as e:
                logger.error(f"Erro ao atualizar submissão {submission['id']}: {str(e)}")
                continue
        
        return {
            "message": f"Questão {data.question_number} anulada com sucesso",
            "updated_count": updated_count
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao anular questão: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao anular questão: {str(e)}")
