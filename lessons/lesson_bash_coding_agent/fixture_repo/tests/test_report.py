import unittest

from gradebook.report import summary


class ReportTests(unittest.TestCase):
    def test_summary_counts_every_student_once(self):
        result = summary([95, 85, 72, 40])
        self.assertEqual(result['count'], 4)
        self.assertEqual(result['grades'], {'A': 1, 'B': 1, 'C': 1, 'F': 1})
        self.assertEqual(result['average'], 73.0)
        self.assertEqual(result['pass_rate'], 0.75)

    def test_summary_of_nothing(self):
        self.assertEqual(summary([]), {'count': 0, 'average': None, 'pass_rate': None, 'grades': {}})


if __name__ == '__main__':
    unittest.main()
