# services/grading_service.py

from core.config import supabase


def calculate_score(assessment_id, answers):

    questions = supabase.table("assessment_questions") \
        .select("*") \
        .eq("assessment_id", assessment_id) \
        .execute().data

    score = 0

    for q in questions:

        number = str(q["question_number"])
        correct = q["correct_answer"]
        weight = q["weight"]

        if answers.get(number) == correct:
            score += weight

    return score