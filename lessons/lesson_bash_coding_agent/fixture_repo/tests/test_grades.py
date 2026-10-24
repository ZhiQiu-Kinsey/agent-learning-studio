import unittest

from gradebook.grades import average, letter_grade, pass_rate

BOUNDARIES = [(100, 'A'), (95, 'A'), (90, 'A'), (89, 'B'), (80, 'B'), (79, 'C'), (70, 'C'),
              (69, 'D'), (60, 'D'), (59, 'F'), (0, 'F')]


class GradeTests(unittest.TestCase):
    def test_average(self):
        self.assertEqual(average([60, 80, 100]), 80)

    def test_average_of_nothing_is_an_error(self):
        with self.assertRaises(ValueError):
            average([])

    def test_letter_boundaries(self):
        for score, expected in BOUNDARIES:
            with self.subTest(score=score):
                self.assertEqual(letter_grade(score), expected)

    def test_pass_rate(self):
        self.assertEqual(pass_rate([50, 60, 70, 80]), 0.75)

    def test_pass_rate_of_nothing_is_none(self):
        self.assertIsNone(pass_rate([]))


if __name__ == '__main__':
    unittest.main()
