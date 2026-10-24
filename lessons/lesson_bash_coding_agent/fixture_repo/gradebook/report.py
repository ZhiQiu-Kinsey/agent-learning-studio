"""Class summary built on the helpers in grades.py."""
from collections import Counter

from gradebook.grades import average, letter_grade, pass_rate


def summary(scores):
    """Count, average, pass rate and the number of students per letter grade."""
    if not scores:
        return {'count': 0, 'average': None, 'pass_rate': None, 'grades': {}}
    grades = Counter(letter_grade(score) for score in scores)
    return {'count': len(scores), 'average': round(average(scores), 1),
            'pass_rate': pass_rate(scores), 'grades': dict(sorted(grades.items()))}
