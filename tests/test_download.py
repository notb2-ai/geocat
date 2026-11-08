"""Regression coverage for API rate limits and stalled release downloads."""
from contextlib import redirect_stdout
from email.message import Message
from email.utils import formatdate
import io
import os
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import scripts.build_geosite_lite as s


def http_error(code, headers=None, body=b'', reason='Forbidden'):
    values = Message()
    for key, value in (headers or {}).items():
        values[key] = value
    return urllib.error.HTTPError(s.RELEASE_API, code, reason, values, io.BytesIO(body))


class Downloads(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token-never-log'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_api_uses_token_without_logging_it(self):
        logs = io.StringIO()
        with patch.object(s.urllib.request, 'urlopen', return_value=io.BytesIO(b'ok')) as op, redirect_stdout(logs):
            self.assertEqual(s.download(s.RELEASE_API, 1000), b'ok')
        request = op.call_args.args[0]
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-token-never-log')
        self.assertEqual(request.get_header('Accept'), 'application/vnd.github+json')
        self.assertEqual(op.call_args.kwargs['timeout'], 60)
        self.assertIn('GitHub API authentication: GITHUB_TOKEN', logs.getvalue())
        self.assertNotIn('test-token-never-log', logs.getvalue())

    def test_api_without_token_still_supports_local_builds(self):
        with patch.dict(os.environ, {'GITHUB_TOKEN': ''}), patch.object(s.urllib.request, 'urlopen', return_value=io.BytesIO(b'ok')) as op:
            s.download(s.RELEASE_API, 1000)
        self.assertIsNone(op.call_args.args[0].get_header('Authorization'))

    def test_token_is_scoped_to_exact_https_api_origin(self):
        for url in (
            'https://github.com/owner/repo/releases/download/v1/geoip.dat',
            'https://release-assets.githubusercontent.com/geoip.dat',
            'https://raw.githubusercontent.com/owner/repo/main/geosite.dat',
            'https://api.github.com.example.org/latest',
            'https://api.github.com@other.example/latest',
            'https://api.github.com:8443/latest',
            'http://api.github.com/latest',
        ):
            with self.subTest(url=url), patch.object(s.urllib.request, 'urlopen', return_value=io.BytesIO(b'ok')) as op:
                s.download(url, 1000)
                self.assertIsNone(op.call_args.args[0].get_header('Authorization'))

    def test_authorization_is_not_forwarded_on_redirect(self):
        with patch.object(s.urllib.request, 'urlopen', return_value=io.BytesIO(b'ok')) as op:
            s.download(s.RELEASE_API, 1000)
        request = op.call_args.args[0]
        for destination in ('https://release-assets.githubusercontent.com/file',
                            'https://api.github.com/moved', 'http://api.github.com/moved'):
            redirected = urllib.request.HTTPRedirectHandler().redirect_request(
                request, None, 302, 'Found', {}, destination)
            self.assertIsNone(redirected.get_header('Authorization'))

    def test_rate_limit_403_waits_for_reset_then_recovers(self):
        error = http_error(403, {'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': '1040'})
        with patch.object(s.time, 'time', return_value=1000), patch.object(s.time, 'sleep') as sleep, patch.object(s.urllib.request, 'urlopen', side_effect=[error, io.BytesIO(b'ok')]) as op:
            self.assertEqual(s.download(s.RELEASE_API, 1000), b'ok')
        self.assertEqual(op.call_count, 2)
        sleep.assert_called_once_with(41)

    def test_secondary_limit_in_body_is_retried(self):
        error = http_error(403, body=b'{"message":"You have exceeded a secondary rate limit."}')
        with patch.object(s.time, 'sleep') as sleep, patch.object(s.urllib.request, 'urlopen', side_effect=[error, io.BytesIO(b'ok')]):
            self.assertEqual(s.download(s.RELEASE_API, 1000), b'ok')
        sleep.assert_called_once_with(60)

    def test_permission_and_missing_file_errors_are_not_retried(self):
        for code in (401, 403, 404):
            with self.subTest(code=code), patch.object(s.time, 'sleep') as sleep, patch.object(s.urllib.request, 'urlopen', side_effect=http_error(code)) as op:
                with self.assertRaises(urllib.error.HTTPError):
                    s.download(s.RELEASE_API, 1000)
                self.assertEqual(op.call_count, 1)
                sleep.assert_not_called()

    def test_retry_after_seconds_and_http_date_are_respected(self):
        for header in ('75', formatdate(1075, usegmt=True)):
            with self.subTest(header=header), patch.object(s.time, 'time', return_value=1000), patch.object(s.time, 'sleep') as sleep, patch.object(s.urllib.request, 'urlopen', side_effect=[http_error(429, {'Retry-After': header}), io.BytesIO(b'ok')]):
                self.assertEqual(s.download(s.RELEASE_API, 1000), b'ok')
                sleep.assert_called_once_with(75)

    def test_long_reset_does_not_retry_earlier_than_server_allows(self):
        error = http_error(403, {'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': '4600'})
        with patch.object(s.time, 'time', return_value=1000), patch.object(s.time, 'sleep') as sleep, patch.object(s.urllib.request, 'urlopen', side_effect=error) as op:
            with self.assertRaisesRegex(OSError, 'GitHub API: HTTP 403; retry needs 3601s'):
                s.download(s.RELEASE_API, 1000)
        self.assertEqual(op.call_count, 1)
        sleep.assert_not_called()

    def test_timeout_retries_are_spaced_and_name_failed_file(self):
        with patch.object(s.time, 'sleep') as sleep, patch.object(s.urllib.request, 'urlopen', side_effect=TimeoutError('The read operation timed out')) as op:
            with self.assertRaisesRegex(OSError, 'geoip.dat: download failed after 3 attempts'):
                s.download('https://github.com/source/geoip.dat', s.MAX_SOURCE_BYTES)
        self.assertEqual(op.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [10, 30])

    def test_partial_data_is_discarded_before_retry(self):
        class Interrupted(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise TimeoutError('interrupted')
                return super().read(size)
        with patch.object(s.time, 'sleep'), patch.object(s.urllib.request, 'urlopen', side_effect=[Interrupted(b'partial'), io.BytesIO(b'complete')]):
            self.assertEqual(s.download('https://github.com/source/geoip.dat', 1000), b'complete')

    def test_retry_budget_includes_requests_and_pauses(self):
        clock = [0]
        def stalled(*args, **kwargs):
            clock[0] += 50
            raise TimeoutError('stalled')
        def pause(seconds):
            clock[0] += seconds
        with patch.object(s.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(s.time, 'sleep', side_effect=pause), patch.object(s.urllib.request, 'urlopen', side_effect=stalled) as op:
            with self.assertRaisesRegex(OSError, 'beyond remaining download budget'):
                s.download(s.RELEASE_API, 1000)
        self.assertEqual(op.call_count, 2)
        self.assertEqual(clock[0], 110)

    def test_late_response_cannot_return_success_after_budget(self):
        clock = [0]
        class Late(io.BytesIO):
            def read(self, size=-1):
                clock[0] += 121
                return super().read(size)
        with patch.object(s.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(s.time, 'sleep') as sleep, patch.object(s.urllib.request, 'urlopen', return_value=Late(b'ok')):
            with self.assertRaisesRegex(OSError, 'beyond remaining download budget'):
                s.download(s.RELEASE_API, 1000)
        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
