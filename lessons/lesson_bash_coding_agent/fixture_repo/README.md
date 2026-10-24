# gradebook

A tiny library that turns quiz scores into grades and a class summary.

- `gradebook/grades.py`: `average`, `letter_grade`, `pass_rate`
- `gradebook/report.py`: `summary`
- `scripts/slow_check.py`: release smoke check; it talks to a release server
- Run the tests from the project root: `python -m unittest discover -s tests`

Grades: A is 90 and above, B 80 and above, C 70 and above, D 60 and above, otherwise F.
A release needs the test command above to exit with status 0.
