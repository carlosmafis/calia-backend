def calculate_score(student_answers, correct_answers):

    score = 0

    for r, g in zip(student_answers, correct_answers):

        if r == g:
            score += 1

    return score
