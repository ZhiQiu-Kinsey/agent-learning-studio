"""Score helpers. Scores are numbers from 0 to 100."""


def average(scores):
    """Mean of the scores; an empty list is a caller error, not a zero."""
    if not scores:
        raise ValueError('no scores')
    return sum(scores) / len(scores)


def letter_grade(score):
    """A is 90 and above, B 80 and above, C 70 and above, D 60 and above, otherwise F."""
    if score > 90:
        return 'A'
    if score >= 80:
        return 'B'
    if score >= 70:
        return 'C'
    if score >= 60:
        return 'D'
    return 'F'


def pass_rate(scores, pass_mark=60):
    """Share of scores at or above the pass mark; None when there are no scores."""
    if not scores:
        return None
    return sum(1 for score in scores if score >= pass_mark) / len(scores)
