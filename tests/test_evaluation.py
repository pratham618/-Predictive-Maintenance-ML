"""Run with the project Python: python -m unittest discover -s tests."""
import sys
import unittest
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import evaluation


class EvaluationTests(unittest.TestCase):
    def test_counts_and_threshold_equality(self):
        result = evaluation.summarize([0, 0, 1, 1], [.1, .8, .7, .2], .7)
        self.assertEqual([result[k] for k in ["caught", "missed", "false_alarms", "correct_normal"]], [1,1,1,1])
        self.assertEqual(result["recall"], .5)
        self.assertEqual(result["precision"], .5)

    def test_no_alarms_precision_is_undefined(self):
        result = evaluation.summarize([0, 1], [.1, .2], .7)
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["precision_interval"])
        self.assertEqual(result["recall"], 0)

    def test_invalid_input_is_rejected(self):
        for labels, probabilities in [([0,1],[.2]),([0,2],[.1,.4]),([0,1],[.1,float("nan")]),([0,1],[.1,1.2])]:
            with self.assertRaises(ValueError):
                evaluation.summarize(labels, probabilities, .7)

    def test_preview_does_not_mutate_rows(self):
        rows = pd.DataFrame({"Actual failure":[0,1], "Failure probability":[.5,.6]})
        original = rows.copy(deep=True)
        low = evaluation.outcomes(rows, .4)
        high = evaluation.outcomes(rows, .7)
        self.assertEqual(low["Outcome"].tolist(), ["False alarm","Caught failure"])
        self.assertEqual(high["Outcome"].tolist(), ["Correct normal","Missed failure"])
        pd.testing.assert_frame_equal(rows, original)

    def test_intervals_cover_observed_rate(self):
        low, high = evaluation.wilson(58, 68)
        self.assertLess(low, 58/68)
        self.assertGreater(high, 58/68)
        self.assertIsNone(evaluation.wilson(0, 0))


if __name__ == "__main__":
    unittest.main()
