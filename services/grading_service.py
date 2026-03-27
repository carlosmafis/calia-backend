# services/grading_service.py

from core.config import supabase


def calculate_score(assessment_id, answers, answers_with_weight=None):
    """Calcula o score como número de acertos (0-10)
    
    Se answers_with_weight for fornecido, considera:
    - MARCADA: peso 1 (acerto/erro normal)
    - BRANCO: peso 0 (não respondeu)
    - MULTIPLA: peso 0 (múltiplas marcações)
    - ANULADA: peso 1 (sempre acerto)
    """
    questions = supabase.table("assessment_questions") \
        .select("*") \
        .eq("assessment_id", assessment_id) \
        .execute().data

    correct_count = 0
    total_weight = 0

    for q in questions:
        number = str(q["question_number"])
        correct = q["correct_answer"]
        
        # Se temos dados com peso, usar eles
        if answers_with_weight and number in answers_with_weight:
            resp_data = answers_with_weight[number]
            weight = resp_data.get("weight", 1)
            resp_type = resp_data.get("type", "MARCADA")
            answer = resp_data.get("answer")
            
            total_weight += weight
            
            # ANULADA sempre conta como acerto
            if resp_type == "ANULADA":
                correct_count += weight
            # BRANCO e MULTIPLA não contam (peso 0)
            elif weight == 0:
                pass
            # MARCADA: verifica se está correto
            elif answer == correct:
                correct_count += weight
        else:
            # Fallback para compatibilidade com respostas antigas
            total_weight += 1
            if answers.get(number) == correct:
                correct_count += 1

    # Calcular score de 0-10 baseado no número de acertos
    return int(correct_count)
