from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from TSRDownload import TSRDownload


class DownloadResumeTests(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.download_path = Path(directory)
        self.part_path = self.download_path / "mod.package.part"
        self.part_path.write_bytes(b"abc")
        self.downloader = TSRDownload(SimpleNamespace(), "")
        self.enterContext(
            patch.object(
                self.downloader,
                "_TSRDownload__getDownloadUrl",
                return_value="https://example.invalid/mod",
            )
        )
        self.enterContext(patch("TSRDownload._print_progress"))

    def mock_download_response(self, status, body, content_range=None):
        probe = MagicMock(
            headers={"Content-Disposition": 'attachment; filename="mod.package"'}
        )
        response = MagicMock(status_code=status, headers={"content-length": str(len(body))})
        if content_range is not None:
            response.headers["Content-Range"] = content_range
        response.__enter__.return_value = response
        response.iter_content.return_value = iter([body])
        return self.enterContext(
            patch.object(self.downloader.session, "get", side_effect=[probe, response])
        )

    def test_full_response_replaces_partial_file(self):
        get = self.mock_download_response(200, b"abcdef")
        path = self.downloader._attemptDownload(str(self.download_path))

        self.assertEqual(get.call_args.kwargs["headers"]["Range"], "bytes=3-")
        self.assertEqual(Path(path).read_bytes(), b"abcdef")
        self.assertFalse(self.part_path.exists())

    def test_matching_partial_response_appends(self):
        self.mock_download_response(206, b"def", "bytes 3-5/6")
        path = self.downloader._attemptDownload(str(self.download_path))

        self.assertEqual(Path(path).read_bytes(), b"abcdef")
        self.assertFalse(self.part_path.exists())

    def test_mismatched_partial_response_preserves_partial_file(self):
        self.mock_download_response(206, b"cdef", "bytes 2-5/6")

        with self.assertRaisesRegex(ValueError, "unexpected Content-Range"):
            self.downloader._attemptDownload(str(self.download_path))

        self.assertEqual(self.part_path.read_bytes(), b"abc")
        self.assertEqual(list(self.download_path.iterdir()), [self.part_path])

    def test_partial_response_with_no_content_range_preserves_partial_file(self):
        self.mock_download_response(206, b"def")

        with self.assertRaisesRegex(ValueError, "unexpected Content-Range"):
            self.downloader._attemptDownload(str(self.download_path))

        self.assertEqual(self.part_path.read_bytes(), b"abc")
        self.assertEqual(list(self.download_path.iterdir()), [self.part_path])

    def test_bounded_partial_response_saves_progress_without_finalizing(self):
        self.mock_download_response(206, b"de", "bytes 3-4/6")

        with self.assertRaisesRegex(ValueError, "Download is incomplete"):
            self.downloader._attemptDownload(str(self.download_path))

        self.assertEqual(self.part_path.read_bytes(), b"abcde")
        self.assertEqual(list(self.download_path.iterdir()), [self.part_path])

        get = self.mock_download_response(206, b"f", "bytes 5-5/6")
        path = self.downloader._attemptDownload(str(self.download_path))

        self.assertEqual(get.call_args.kwargs["headers"]["Range"], "bytes=5-")
        self.assertEqual(Path(path).read_bytes(), b"abcdef")
        self.assertFalse(self.part_path.exists())

    def test_response_body_cannot_extend_beyond_advertised_range(self):
        self.mock_download_response(206, b"defg", "bytes 3-5/6")

        with self.assertRaisesRegex(ValueError, "exceeds Content-Range"):
            self.downloader._attemptDownload(str(self.download_path))

        self.assertEqual(self.part_path.read_bytes(), b"abc")
        self.assertEqual(list(self.download_path.iterdir()), [self.part_path])

    def test_partial_response_with_unknown_total_cannot_finalize(self):
        self.mock_download_response(206, b"def", "bytes 3-5/*")

        with self.assertRaisesRegex(ValueError, "unexpected Content-Range"):
            self.downloader._attemptDownload(str(self.download_path))

        self.assertEqual(self.part_path.read_bytes(), b"abc")
        self.assertEqual(list(self.download_path.iterdir()), [self.part_path])
