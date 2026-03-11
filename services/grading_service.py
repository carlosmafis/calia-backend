def calculate_score(student_answers, correct_answers):

    score = 0

    for q in correct_answers:

        number = str(q["question_number"])
        correct = q["correct_answer"]
        weight = q["weight"]

        if student_answers.get(number) == correct:
            score += weight

    return score
