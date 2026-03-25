# services/grading_service.py

from core.config import supabase


def calculate_score(assessment_id, answers):
    """Calcula o score como número de acertos (0-10)"""
    questions = supabase.table("assessment_questions") \
        .select("*") \
        .eq("assessment_id", assessment_id) \
        .execute().data

    correct_count = 0
    total_questions = len(questions)

    for q in questions:
        number = str(q["question_number"])
        correct = q["correct_answer"]

        if answers.get(number) == correct:
            correct_count += 1

    # Calcular score de 0-10 baseado no número de acertos
    if total_questions > 0:
        score = (correct_count / total_questions) * 10
    else:
        score = 0

    return round(score, 2)