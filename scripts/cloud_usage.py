"""Inspect/migrate only today's numeric usage; no credential or content output."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from google.cloud import firestore
from google.oauth2.credentials import Credentials

ROOT = Path(__file__).resolve().parents[1]

def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['inspect', 'seed'])
    parser.add_argument('--project', default=os.environ.get('NURI_CLOUD_PROJECT', ''))
    parser.add_argument('--account', default=os.environ.get('NURI_GCLOUD_ACCOUNT', ''))
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]', args.project):
        parser.error('Set --project or NURI_CLOUD_PROJECT to the intended Google Cloud project ID.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', args.account):
        parser.error('Set --account or NURI_GCLOUD_ACCOUNT to the intended Google account.')
    return args


def gcloud_token_command(args):
    executable = shutil.which('gcloud.cmd') or shutil.which('gcloud')
    if not executable:
        raise RuntimeError('gcloud_not_found_on_PATH')
    return [executable, 'auth', 'print-access-token',
            '--account=' + args.account, '--project=' + args.project, '--quiet']


def main(argv=None):
    args = parse_args(argv)
    try:
        command = gcloud_token_command(args)
        day = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        local = 0
        path = ROOT / '.state' / 'usage.sqlite'
        if path.exists():
            with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
                row = db.execute('SELECT attempts FROM daily WHERE day=?', (day,)).fetchone()
                local = int(row[0]) if row else 0
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        client = firestore.Client(project=args.project, credentials=Credentials(result.stdout.strip()))
        collection = client.collection('nuri_limits')
        daily = collection.document('day_' + day)
        marker = collection.document('local_migration_' + day)
        if args.mode == 'seed':
            @firestore.transactional
            def seed(transaction):
                previous = marker.get(transaction=transaction)
                current = daily.get(transaction=transaction)
                current_count = (current.to_dict() or {}).get('attempts', 0)
                if previous.exists:
                    return current_count, False
                transaction.set(daily, {'day': day, 'attempts': current_count + local})
                transaction.set(marker, {'day': day, 'attempts': local})
                return current_count + local, True
            cloud, migrated = seed(client.transaction())
        else:
            cloud = (daily.get().to_dict() or {}).get('attempts', 0)
            migrated = marker.get().exists
        print(json.dumps({'day': day, 'local_attempts': local, 'cloud_attempts': cloud, 'local_usage_migrated': migrated, 'limit': 25}))
        return 0
    except Exception as error:
        error_type = 'gcloud_not_found_on_PATH' if isinstance(error, RuntimeError) and str(error) == 'gcloud_not_found_on_PATH' else type(error).__name__
        print(json.dumps({'success': False, 'error_type': error_type}))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
