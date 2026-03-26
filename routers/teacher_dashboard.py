from fastapi import APIRouter, Depends, HTTPException
from core.auth import get_current_user
from core.config import supabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teacher/dashboard", tags=["Teacher Dashboard"])


# ==========================
# RESUMO DA TURMA
# ==========================

@router.get("/class/{class_id}/summary")
def get_class_summary(class_id: str, user=Depends(get_current_user)):
    """Retorna resumo da turma com estatísticas"""
    
    try:
        # Buscar submissões da turma
        submissions = supabase.table("student_submissions") \
            .select("score, status") \
            .eq("class_id", class_id) \
            .execute()
        
        subs = submissions.data or []
        
        # Calcular estatísticas
        scores = [s.get("score", 0) for s in subs if s.get("status") == "corrected" and s.get("score") is not None]
        
        if not scores:
            return {
                "average": 0,
                "median": 0,
                "std_dev": 0,
                "max_score": 0,
                "min_score": 0,
                "approved": 0,
                "failed": 0,
                "absent": 0,
                "total": 0
            }
        
        # Calcular média
        average = sum(scores) / len(scores)
        
        # Calcular mediana
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        median = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2 if n % 2 == 0 else sorted_scores[n // 2]
        
        # Calcular desvio padrão
        variance = sum((x - average) ** 2 for x in scores) / len(scores)
        std_dev = variance ** 0.5
        
        # Contar status
        approved = sum(1 for s in subs if s.get("status") == "corrected" and s.get("score", 0) >= 6)
        failed = sum(1 for s in subs if s.get("status") == "corrected" and s.get("score", 0) < 6)
        absent = sum(1 for s in subs if s.get("status") == "ausente")
        
        return {
            "average": round(average, 2),
            "median": round(median, 2),
            "std_dev": round(std_dev, 2),
            "max_score": round(max(scores), 2),
            "min_score": round(min(scores), 2),
            "approved": approved,
            "failed": failed,
            "absent": absent,
            "total": len(subs)
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar resumo da turma: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# ANÁLISE POR ALUNO
# ==========================

@router.get("/class/{class_id}/students")
def get_class_students(
    class_id: str,
    user=Depends(get_current_user),
    sort_by: str = "score",  # score, name, trend
    order: str = "desc"  # asc, desc
):
    """Retorna lista de alunos da turma com análise"""
    
    try:
        # Buscar alunos da turma
        students = supabase.table("students") \
            .select("id, name, registration_number") \
            .eq("class_id", class_id) \
            .execute()
        
        students_data = students.data or []
        result = []
        
        for student in students_data:
            # Buscar submissões do aluno
            submissions = supabase.table("student_submissions") \
                .select("score, status, created_at") \
                .eq("student_id", student["id"]) \
                .eq("class_id", class_id) \
                .order("created_at", desc=True) \
                .execute()
            
            subs = submissions.data or []
            
            if not subs:
                continue
            
            latest_sub = subs[0]
            score = latest_sub.get("score", 0)
            status = latest_sub.get("status")
            
            # Determinar status do aluno
            if status == "ausente":
                student_status = "absent"
            elif score >= 6:
                student_status = "approved"
            elif score >= 5:
                student_status = "at_risk"
            else:
                student_status = "failed"
            
            # Calcular tendência (melhora/piora/estável)
            if len(subs) >= 2:
                prev_score = subs[1].get("score", 0)
                if score > prev_score:
                    trend = "up"
                elif score < prev_score:
                    trend = "down"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            
            result.append({
                "student_id": student["id"],
                "name": student["name"],
                "registration": student["registration_number"],
                "score": round(score, 2),
                "status": student_status,
                "trend": trend,
                "submissions_count": len(subs)
            })
        
        # Ordenar
        if sort_by == "score":
            result.sort(key=lambda x: x["score"], reverse=(order == "desc"))
        elif sort_by == "name":
            result.sort(key=lambda x: x["name"], reverse=(order == "desc"))
        
        return result
    
    except Exception as e:
        logger.error(f"Erro ao buscar alunos da turma: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# ANÁLISE POR QUESTÃO (APROFUNDADA)
# ==========================

@router.get("/assessment/{assessment_id}/questions/analysis")
def get_questions_analysis(assessment_id: str, user=Depends(get_current_user)):
    """Retorna análise detalhada de cada questão"""
    
    try:
        # Buscar questões
        questions = supabase.table("assessment_questions") \
            .select("question_number, correct_answer") \
            .eq("assessment_id", assessment_id) \
            .order("question_number") \
            .execute()
        
        questions_data = questions.data or []
        
        # Buscar submissões
        submissions = supabase.table("student_submissions") \
            .select("extracted_answers") \
            .eq("assessment_id", assessment_id) \
            .execute()
        
        subs = submissions.data or []
        result = []
        
        for q in questions_data:
            q_num = str(q["question_number"])
            expected = q["correct_answer"]
            
            # Contar respostas
            option_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "BRANCO": 0}
            correct_count = 0
            
            for sub in subs:
                answers = sub.get("extracted_answers") or {}
                answer = answers.get(q_num, "BRANCO").upper()
                
                if answer in option_counts:
                    option_counts[answer] += 1
                else:
                    option_counts["BRANCO"] += 1
                
                if answer == expected.upper():
                    correct_count += 1
            
            # Calcular percentual de acerto
            pct = (correct_count / len(subs) * 100) if subs else 0
            
            # Identificar distrator mais escolhido
            distractors = {k: v for k, v in option_counts.items() if k != expected.upper() and k != "BRANCO"}
            most_chosen_distractor = max(distractors.items(), key=lambda x: x[1])[0] if distractors else None
            
            # Classificar dificuldade
            if pct >= 70:
                difficulty = "easy"
            elif pct >= 40:
                difficulty = "medium"
            else:
                difficulty = "hard"
            
            result.append({
                "question": q_num,
                "expected": expected,
                "correct_count": correct_count,
                "total": len(subs),
                "pct": round(pct, 1),
                "option_counts": option_counts,
                "most_chosen_distractor": most_chosen_distractor,
                "difficulty": difficulty
            })
        
        return result
    
    except Exception as e:
        logger.error(f"Erro ao buscar análise de questões: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# ALUNOS EM RISCO
# ==========================

@router.get("/class/{class_id}/at-risk")
def get_at_risk_students(class_id: str, user=Depends(get_current_user)):
    """Retorna alunos em risco com histórico e sugestões"""
    
    try:
        # Buscar alunos com score < 5
        submissions = supabase.table("student_submissions") \
            .select("student_id, score, status, students(id, name, registration_number)") \
            .eq("class_id", class_id) \
            .execute()
        
        subs = submissions.data or []
        
        # Filtrar alunos em risco
        at_risk_students = {}
        
        for sub in subs:
            if sub.get("status") == "corrected" and sub.get("score", 0) < 5:
                student_id = sub.get("student_id")
                student_name = sub.get("students", {}).get("name", "Aluno") if isinstance(sub.get("students"), dict) else "Aluno"
                student_reg = sub.get("students", {}).get("registration_number", "—") if isinstance(sub.get("students"), dict) else "—"
                
                if student_id not in at_risk_students:
                    at_risk_students[student_id] = {
                        "student_id": student_id,
                        "name": student_name,
                        "registration": student_reg,
                        "scores": [],
                        "risk_level": "high"
                    }
                
                at_risk_students[student_id]["scores"].append(sub.get("score", 0))
        
        # Calcular média de scores e tendência
        result = []
        for student_id, data in at_risk_students.items():
            avg_score = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            
            # Determinar tendência
            if len(data["scores"]) >= 2:
                if data["scores"][-1] > data["scores"][0]:
                    trend = "improving"
                elif data["scores"][-1] < data["scores"][0]:
                    trend = "worsening"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            
            data["average_score"] = round(avg_score, 2)
            data["trend"] = trend
            result.append(data)
        
        # Ordenar por score (menor primeiro)
        result.sort(key=lambda x: x["average_score"])
        
        return result
    
    except Exception as e:
        logger.error(f"Erro ao buscar alunos em risco: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# PROGRESSO TEMPORAL DO ALUNO
# ==========================

@router.get("/student/{student_id}/progress")
def get_student_progress(student_id: str, user=Depends(get_current_user)):
    """Retorna progresso temporal do aluno com comparação com turma"""
    
    try:
        # Buscar submissões do aluno
        submissions = supabase.table("student_submissions") \
            .select("score, status, created_at, assessment_id") \
            .eq("student_id", student_id) \
            .order("created_at") \
            .execute()
        
        student_subs = submissions.data or []
        
        if not student_subs:
            return {"progress": [], "class_average": 0}
        
        # Buscar class_id do aluno
        student = supabase.table("students") \
            .select("class_id") \
            .eq("id", student_id) \
            .single() \
            .execute()
        
        class_id = student.data.get("class_id") if student.data else None
        
        # Buscar submissões da turma para comparação
        class_subs = supabase.table("student_submissions") \
            .select("score, status") \
            .eq("class_id", class_id) \
            .execute() if class_id else None
        
        class_scores = [s.get("score", 0) for s in (class_subs.data or []) if s.get("status") == "corrected" and s.get("score") is not None]
        class_average = sum(class_scores) / len(class_scores) if class_scores else 0
        
        # Montar progresso
        progress = []
        for i, sub in enumerate(student_subs):
            if sub.get("status") == "corrected":
                progress.append({
                    "index": i + 1,
                    "score": round(sub.get("score", 0), 2),
                    "date": sub.get("created_at"),
                    "assessment_id": sub.get("assessment_id")
                })
        
        return {
            "progress": progress,
            "class_average": round(class_average, 2),
            "student_average": round(sum([p["score"] for p in progress]) / len(progress), 2) if progress else 0
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar progresso do aluno: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")
