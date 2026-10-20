import unittest
from datetime import datetime
from unittest.mock import patch

import RMRB_Downloader as downloader


class DailyDownloaderTests(unittest.TestCase):
    def test_next_run_is_today_before_noon(self):
        now = datetime(2026, 10, 20, 11, 30)
        self.assertEqual(
            downloader.Get_Next_Daily_Run(now),
            datetime(2026, 10, 20, 12, 0),
        )

    def test_next_run_is_tomorrow_at_or_after_noon(self):
        at_noon = datetime(2026, 10, 20, 12, 0)
        after_noon = datetime(2026, 10, 20, 18, 45)
        expected = datetime(2026, 10, 21, 12, 0)
        self.assertEqual(downloader.Get_Next_Daily_Run(at_noon), expected)
        self.assertEqual(downloader.Get_Next_Daily_Run(after_noon), expected)

    @patch.object(downloader, "THREAD_SAFE_PRINT")
    @patch.object(downloader, "RMRB_PDF_Downloader")
    @patch.object(downloader, "Check_RMRB_Exist")
    def test_download_missing_dates_only(self, check_mock, download_mock, _print_mock):
        check_mock.return_value = ["20261019", "20261020"]

        result = downloader.Download_Missing_RMRB(
            "20260101", "20261020", "D:/RMRB/", "test.log"
        )

        self.assertEqual(result, ["20261019", "20261020"])
        self.assertEqual(download_mock.call_count, 2)
        self.assertEqual(
            [call.kwargs["Begin_date"] for call in download_mock.call_args_list],
            ["20261019", "20261020"],
        )

    @patch.object(downloader, "THREAD_SAFE_PRINT")
    @patch.object(downloader, "Download_Missing_RMRB")
    def test_daily_mode_catches_up_then_runs_at_noon(self, download_mock, _print_mock):
        times = iter(
            [
                datetime(2026, 10, 20, 10, 0),
                datetime(2026, 10, 20, 10, 0),
                datetime(2026, 10, 20, 12, 0),
            ]
        )
        sleeps = []

        downloader.Run_Daily_Downloader(
            Download_Path="D:/RMRB/",
            Log_File_Path="test.log",
            Now_Function=lambda: next(times),
            Sleep_Function=sleeps.append,
            Max_Scheduled_Runs=1,
        )

        self.assertEqual(sleeps, [7200.0])
        self.assertEqual(download_mock.call_count, 2)
        self.assertEqual(
            download_mock.call_args_list[0].args[:2],
            ("20260101", "20261020"),
        )
        self.assertEqual(
            download_mock.call_args_list[1].args[:2],
            ("20260101", "20261020"),
        )


if __name__ == "__main__":
    unittest.main()
