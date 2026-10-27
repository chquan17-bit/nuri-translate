"""Public HTTP boundary smoke check; never uses credentials or model calls."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def service_url(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname
                or not parsed.hostname.endswith('.run.app')
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or parsed.username or parsed.password or parsed.port is not None):
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError('Use an HTTPS Cloud Run service URL without a path, credentials, port, or query.') from None
    return value.rstrip('/')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ingress-url', required=True, type=service_url)
    parser.add_argument('--worker-url', required=True, type=service_url)
    parser.add_argument('--application-id', default=os.environ.get('NURI_APPLICATION_ID', ''))
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parents[1] / '.state' / 'cloud-boundary-verification.json')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[0-9]{16,22}', args.application_id):
        parser.error('Set --application-id or NURI_APPLICATION_ID to the intended Discord application ID.')
    return args


def main(argv=None):
    args = parse_args(argv)
    # No ambient proxy settings or redirects, and no authenticated requests.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    checks = []
    for name, method, url, expected, payload, headers in [
        ('ingress_health', 'GET', args.ingress_url + '/health', 200, None, {}),
        ('ingress_has_no_worker_route', 'POST', args.ingress_url + '/tasks', 404, {}, {}),
        ('unsigned_interaction_denied', 'POST', args.ingress_url + '/interactions', 401, {'type': 1}, {}),
        ('forged_signature_denied', 'POST', args.ingress_url + '/interactions', 401, {'type': 1, 'application_id': args.application_id},
         {'X-Signature-Timestamp': str(int(time.time())), 'X-Signature-Ed25519': '00' * 64}),
        ('anonymous_worker_denied', 'POST', args.worker_url + '/tasks', 403, {}, {}),
    ]:
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        request = Request(url, data=data, method=method,
                          headers={'Content-Type': 'application/json', **headers})
        started = time.monotonic()
        status = None
        error = None
        try:
            with opener.open(request, timeout=20) as response:
                status = response.status
        except HTTPError as response:
            status = response.code
            response.close()
        except Exception as failure:
            # Exception text can contain URLs or network settings. Keep only type.
            error = type(failure).__name__
        row = {'check': name, 'status': status, 'expected': expected,
               'passed': status == expected, 'seconds': round(time.monotonic() - started, 3)}
        if error:
            row['error_type'] = error
        checks.append(row)
    result = {'passed': all(row['passed'] for row in checks), 'checks': checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
