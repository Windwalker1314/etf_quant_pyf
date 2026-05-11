import pandas as pd
import unittest

from etf_quant.validation.windows import make_walk_forward_windows


class WindowTests(unittest.TestCase):
    def test_rolling_windows_progress_by_step(self):
        windows = make_walk_forward_windows(
            start="2018-01-01",
            end="2022-12-31",
            train_months=36,
            validation_months=6,
            test_months=6,
            step_months=6,
            mode="rolling",
        )

        self.assertGreaterEqual(len(windows), 2)
        self.assertEqual(windows[0].train_start, pd.Timestamp("2018-01-01"))
        self.assertEqual(windows[0].test_start, pd.Timestamp("2021-07-01"))
        self.assertEqual(windows[1].train_start, pd.Timestamp("2018-07-01"))

    def test_expanding_windows_keep_train_start(self):
        windows = make_walk_forward_windows(
            start="2018-01-01",
            end="2022-12-31",
            train_months=36,
            validation_months=6,
            test_months=6,
            step_months=6,
            mode="expanding",
        )

        self.assertEqual(windows[0].train_start, pd.Timestamp("2018-01-01"))
        self.assertEqual(windows[1].train_start, pd.Timestamp("2018-01-01"))


if __name__ == "__main__":
    unittest.main()
