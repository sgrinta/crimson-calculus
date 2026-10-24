"""Local readiness check. Runs without optional packages; never prints key values.

Usage: python setup_check.py [--test-ai] [--json]
The optional AI test sends only a fictional scenario, never saved session logs.
"""
import argparse
from datetime import datetime, timezone
import importlib
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
PACKAGES = ('dash', 'numpy', 'plotly', 'openai', 'dotenv')
VERSIONS = dict(dash=('dash',3,5),numpy=('numpy',2,3),plotly=('plotly',6,7),openai=('openai',2,3),dotenv=('python-dotenv',1,2))


def key_configuration(root=ROOT):
    """Match app precedence: process environment, project .env, then parent .env."""
    values, sources = {}, {}
    if importlib.util.find_spec('dotenv'):
        from dotenv import dotenv_values
        for path, source in ((root / '.env', 'project .env'), (root.parent / '.env', 'parent .env')):
            if path.is_file():
                for name, value in dotenv_values(path).items():
                    if name not in values:
                        values[name], sources[name] = value, source
    for name in ('PORTKEY_API_KEY', 'OPENAI_API_KEY'):
        if name in os.environ:
            values[name], sources[name] = os.environ[name], 'process environment'
    for name in ('PORTKEY_API_KEY', 'OPENAI_API_KEY'):
        if str(values.get(name) or '').strip():
            return dict(configured=True, key_name=name, source=sources[name])
    return dict(configured=False, key_name=None, source=None)


def run_checks(test_ai=False, root=ROOT):
    rows = []
    def add(name, status, detail):
        rows.append(dict(name=name, status=status, detail=detail))
    add('Python', 'pass' if sys.version_info >= (3,11) else 'fail',
        f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} · requires 3.11 or newer')
    missing=[]
    for package in PACKAGES:
        try:
            importlib.import_module(package)
            distribution,low,high=VERSIONS[package]
            if not low<=int(version(distribution).split('.')[0])<high:missing.append(package)
        except Exception:missing.append(package)
    add('Dependencies', 'fail' if missing else 'pass',
        'Missing, incompatible or failed to import: '+', '.join(missing)+'. Run python -m pip install -r requirements.txt.' if missing else 'All five application packages import successfully and match the required major versions.')
    required = ('data/portfolio_actions.json','data/portfolio_policy.bin','data/portfolio_values.bin',
                'assets/ai-host-selected-blonde.png','assets/practice-wheel-single.svg')
    absent = [p for p in required if not (root / p).is_file()]
    add('Bundled data & artwork', 'fail' if absent else 'pass',
        'Missing: '+', '.join(absent) if absent else 'Research sample, policy files and key artwork are present.')
    try:
        (root / 'runtime').mkdir(exist_ok=True)
        with tempfile.TemporaryFile(dir=root / 'runtime') as stream:
            stream.write(b'readiness check'); stream.flush()
        add('Local storage', 'pass', 'Runtime folder is writable for usage accounting. Browser session storage is separate.')
    except OSError:
        add('Local storage', 'fail', 'Cannot write to runtime/. Give this project folder write permission.')
    if 'numpy' not in missing:
        try:
            from engine import Scenario, compare
            result=compare(Scenario(bankroll=100,target=20,loss_limit=100,minimum=5,maximum=50,chip=5,spins=8))
            assert result['rows'] and all(0 <= r['success'] <= 1 for r in result['rows'])
            add('Calculator', 'pass', f"Small local scenario passed · {len(result['rows'])} systems · calculation {result['id']}. No AI tokens used.")
        except Exception:
            add('Calculator', 'fail', 'Calculator check failed. Run the documented tests for details.')
    else:
        add('Calculator', 'fail', 'Install dependencies before running the calculator check.')
    try:
        key=key_configuration(root)
        add('AI key', 'pass' if key['configured'] else 'warn',
            f"{key['key_name']} configured. Project .env, parent .env and process environment are supported. Key value is hidden."
            if key['configured'] else 'No AI key found. Calculator and practice still work. Add PORTKEY_API_KEY to this folder’s .env or its parent.')
    except Exception:
        key=dict(configured=False)
        add('AI key', 'fail', 'Could not read configuration. Check .env permissions and python-dotenv installation.')
    ai=None
    if test_ai:
        if missing or not key['configured']:
            add('AI connection', 'fail', 'Configure the key and install dependencies, then test again.')
        else:
            from agent import generate
            from dataclasses import asdict
            from engine import Scenario
            scenario=Scenario(bankroll=100,target=20,loss_limit=100,minimum=5,maximum=50,chip=5,spins=8)
            reply=generate([dict(role='user',content='This is a connection check. Briefly confirm that you can read the current calculation ID. Do not request any changes.')],asdict(scenario))
            ok=reply.get('mode')=='AI analyst'
            ai=dict(mode=reply.get('mode'),usage=reply.get('usage',{}),turn_id=reply.get('turn_id'))
            add('AI connection', 'pass' if ok else 'fail',
                'Vivienne responded using a fictional scenario. No saved sessions were shared.' if ok else
                ('Local AI allowance is unavailable. Check Usage & limits in Vivienne’s panel.' if reply.get('mode')=='budget guard' else
                 'AI connection did not complete. Check the configured key, network and model access.'))
    return dict(checked_at=datetime.now(timezone.utc).isoformat(),
                ready=not any(r['status']=='fail' for r in rows), checks=rows,
                ai_test_requested=bool(test_ai), ai_test=ai)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-ai',action='store_true',help='Make one bounded AI test turn; uses API tokens.')
    parser.add_argument('--json',action='store_true',help='Print a shareable report without key values.')
    args=parser.parse_args()
    result=run_checks(args.test_ai)
    if args.json:print(json.dumps(result,indent=2))
    else:
        print('Crimson Calculus · setup check')
        for row in result['checks']:print(f"[{row['status'].upper()}] {row['name']}: {row['detail']}")
        print('Ready.' if result['ready'] else 'Fix the failed checks, then run this command again.')
    return 0 if result['ready'] else 1


if __name__=='__main__':raise SystemExit(main())
