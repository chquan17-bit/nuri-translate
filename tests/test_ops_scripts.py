"""Maintenance commands must pin identities and fail closed without secrets."""
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import cloud_connection, cloud_usage, verify_cloud_boundaries


APP_ID = '111111111111111111'


class MaintenanceScriptsTests(unittest.TestCase):
    def test_missing_identity_rejected_before_external_or_state_access(self):
        with patch.dict('os.environ', {}, clear=True), redirect_stderr(io.StringIO()):
            for module, arguments in (
                (cloud_connection, ['inspect']),
                (cloud_usage, ['inspect']),
                (verify_cloud_boundaries, ['--ingress-url', 'https://ingress-example.a.run.app',
                                          '--worker-url', 'https://worker-example.a.run.app']),
            ):
                with self.subTest(module=module.__name__), self.assertRaises(SystemExit) as error:
                    module.parse_args(arguments)
                self.assertEqual(error.exception.code, 2)

    def test_gcloud_commands_pin_account_and_project_and_require_executable(self):
        args = Namespace(account='owner@example.com', project='nuri-test')
        for module in (cloud_connection, cloud_usage):
            with self.subTest(module=module.__name__):
                with patch.object(module.shutil, 'which', return_value='C:/Tools/gcloud.cmd'):
                    command = module.gcloud_token_command(args)
                self.assertIn('--account=owner@example.com', command)
                self.assertIn('--project=nuri-test', command)
                self.assertEqual(command[:3], ['C:/Tools/gcloud.cmd', 'auth', 'print-access-token'])
                with patch.object(module.shutil, 'which', return_value=None):
                    with self.assertRaisesRegex(RuntimeError, 'gcloud_not_found_on_PATH'):
                        module.gcloud_token_command(args)

    def test_switch_endpoint_rejects_credentials_external_hosts_and_invalid_ports(self):
        for url in ('https://user:password@ingress.a.run.app/interactions',
                    'https://example.com/interactions', 'http://ingress.a.run.app/interactions',
                    'https://ingress.a.run.app:bad/interactions',
                    'https://ingress.a.run.app/interactions?token=value'):
            with self.subTest(url=url):
                self.assertFalse(cloud_connection.valid_endpoint(url))
        self.assertTrue(cloud_connection.valid_endpoint('https://ingress-example.a.run.app/interactions'))

    def check_boundaries(self, results):
        class FakeOpener:
            def __init__(self):
                self.requests = []

            def open(self, request, timeout):
                self.requests.append(request)
                result = results[len(self.requests) - 1]
                if isinstance(result, Exception):
                    raise result
                raise HTTPError(request.full_url, result, 'status', {}, None)

        opener = FakeOpener()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'new' / 'nested' / 'boundaries.json'
            with patch.object(verify_cloud_boundaries, 'build_opener', return_value=opener), redirect_stdout(io.StringIO()):
                code = verify_cloud_boundaries.main([
                    '--ingress-url', 'https://ingress-example.a.run.app',
                    '--worker-url', 'https://worker-example.a.run.app',
                    '--application-id', APP_ID, '--output', str(output),
                ])
            report = json.loads(output.read_text(encoding='utf-8'))
        return code, report, opener.requests

    def test_boundary_report_creates_parent_and_uses_expected_app_for_forgery(self):
        code, report, requests = self.check_boundaries([200, 404, 401, 401, 403])
        self.assertEqual(code, 0)
        self.assertTrue(report['passed'])
        self.assertEqual(len(requests), 5)
        self.assertEqual(json.loads(requests[3].data)['application_id'], APP_ID)
        self.assertTrue(all(not request.has_header('Authorization') for request in requests))

    def test_boundary_network_errors_fail_and_do_not_leak_exception_text(self):
        code, report, _ = self.check_boundaries([URLError('DO-NOT-EXPOSE'), 404, 401, 401, 403])
        self.assertEqual(code, 1)
        self.assertFalse(report['passed'])
        self.assertEqual(report['checks'][0]['error_type'], 'URLError')
        self.assertNotIn('DO-NOT-EXPOSE', json.dumps(report))


if __name__ == '__main__':
    unittest.main()
