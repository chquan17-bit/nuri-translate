"""Move existing credentials through authenticated APIs without printing secrets."""
import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlsplit
import aiohttp

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.state'

def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['inspect', 'upload', 'switch', 'restore'])
    parser.add_argument('--endpoint', default='')
    parser.add_argument('--application-id', default=os.environ.get('NURI_APPLICATION_ID', ''))
    parser.add_argument('--project', default=os.environ.get('NURI_CLOUD_PROJECT', ''))
    parser.add_argument('--account', default=os.environ.get('NURI_GCLOUD_ACCOUNT', ''))
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[0-9]{16,22}', args.application_id):
        parser.error('Set --application-id or NURI_APPLICATION_ID to the intended Discord application ID.')
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]', args.project):
        parser.error('Set --project or NURI_CLOUD_PROJECT to the intended Google Cloud project ID.')
    if args.mode == 'upload' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', args.account):
        parser.error('Set --account or NURI_GCLOUD_ACCOUNT to the intended Google account.')
    if args.mode == 'switch' and not valid_endpoint(args.endpoint):
        parser.error('--endpoint must be an HTTPS Cloud Run /interactions URL without credentials or query parameters.')
    return args


def valid_endpoint(endpoint):
    try:
        parsed = urlsplit(endpoint)
        return (parsed.scheme == 'https' and bool(parsed.hostname)
                and parsed.hostname.endswith('.run.app') and parsed.path == '/interactions'
                and not parsed.query and not parsed.fragment and not parsed.username
                and not parsed.password and parsed.port is None)
    except ValueError:
        return False


def gcloud_token_command(args):
    executable = shutil.which('gcloud.cmd') or shutil.which('gcloud')
    if not executable:
        raise RuntimeError('gcloud_not_found_on_PATH')
    return [executable, 'auth', 'print-access-token',
            '--account=' + args.account, '--project=' + args.project, '--quiet']


async def main(argv=None):
    args = parse_args(argv)
    stage = 'verify-discord-application'
    try:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
            headers = {'Authorization': 'Bot ' + os.environ['DISCORD_BOT_TOKEN'],
                       'User-Agent': 'NuriTranslationMaintenance/0.1'}
            async def request(method, url, *, headers=headers, body=None):
                async with session.request(method, url, headers=headers, json=body,
                                           allow_redirects=False) as response:
                    if response.status >= 300:
                        raise RuntimeError(f'HTTP {response.status}')
                    return await response.json()
            app = await request('GET', 'https://discord.com/api/v10/oauth2/applications/@me')
            if str(app['id']) != args.application_id:
                raise RuntimeError('discord_application_mismatch')
            owner = str(app['team']['owner_user_id'] if app.get('team') else app['owner']['id'])
            if not re.fullmatch(r'[0-9]{16,22}', owner) or not re.fullmatch(r'[0-9a-fA-F]{64}', app['verify_key']):
                raise RuntimeError('discord_application_metadata_invalid')
            public = {'application_id': args.application_id, 'owner_id': owner, 'public_key': app['verify_key'],
                      'model': os.environ['GEMINI_MODEL'], 'project': args.project,
                      'region': 'asia-northeast3', 'interactions_endpoint': app.get('interactions_endpoint_url')}
            STATE.mkdir(parents=True, exist_ok=True)
            (STATE / 'cloud-public-config.json').write_text(json.dumps(public, indent=2), encoding='utf-8')
            if args.mode == 'inspect':
                print(json.dumps(public))
            if args.mode == 'upload':
                stage = 'authenticate-google'
                result = subprocess.run(gcloud_token_command(args),
                                        capture_output=True, text=True, check=True)
                gheaders = {'Authorization': 'Bearer ' + result.stdout.strip(), 'x-goog-user-project': args.project}
                for name, value in [('nuri-gemini-key', os.environ['GEMINI_API_KEY']),
                                    ('nuri-component-signing', secrets.token_urlsafe(32))]:
                    stage = 'upload-' + name
                    body = {'payload': {'data': base64.b64encode(value.encode()).decode()}}
                    version = await request('POST', f'https://secretmanager.googleapis.com/v1/projects/{args.project}/secrets/{name}:addVersion', headers=gheaders, body=body)
                    print(json.dumps({'secret': name, 'version': version['name'].rsplit('/', 1)[-1], 'saved': True}))
            if args.mode in ('switch', 'restore'):
                stage = 'set-discord-endpoint'
                before = STATE / 'cloud-cutover-before.json'
                if args.mode == 'switch':
                    if not before.exists():
                        before.write_text(json.dumps({'endpoint': app.get('interactions_endpoint_url'), 'captured_at': datetime.now(timezone.utc).isoformat()}), encoding='utf-8')
                    endpoint = args.endpoint
                else:
                    endpoint = json.loads(before.read_text(encoding='utf-8-sig'))['endpoint']
                    if endpoint not in (None, '') and not valid_endpoint(endpoint):
                        raise RuntimeError('saved_endpoint_invalid')
                await request('PATCH', 'https://discord.com/api/v10/applications/@me', body={'interactions_endpoint_url': endpoint})
                result = await request('GET', 'https://discord.com/api/v10/oauth2/applications/@me')
                if result.get('interactions_endpoint_url') != endpoint:
                    raise RuntimeError('Endpoint readback mismatch')
                if args.mode == 'restore':
                    marker_path = STATE / 'cloud-active.json'
                    marker = json.loads(marker_path.read_text(encoding='utf-8-sig')) if marker_path.exists() else {}
                    marker.update(active=False, restored_at=datetime.now(timezone.utc).isoformat(),
                                  restored_endpoint=endpoint)
                    pending_marker = marker_path.with_suffix('.json.tmp')
                    pending_marker.write_text(json.dumps(marker, indent=2), encoding='utf-8')
                    pending_marker.replace(marker_path)
                print(json.dumps({'application_id': args.application_id, 'endpoint': endpoint, 'verified': True}))
        return 0
    except Exception as error:
        safe_codes = {'gcloud_not_found_on_PATH', 'discord_application_mismatch',
                      'discord_application_metadata_invalid', 'saved_endpoint_invalid'}
        status = (str(error) if isinstance(error, RuntimeError)
                  and (re.fullmatch(r'HTTP [0-9]{3}', str(error)) or str(error) in safe_codes)
                  else type(error).__name__)
        print(json.dumps({'success': False, 'stage': stage, 'error': status}))
        return 1

if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
