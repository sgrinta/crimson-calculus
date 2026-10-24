"""Deployment access and concurrency boundaries; no network or real credentials."""
import base64
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import threading
import time
import unittest
import os
from unittest.mock import patch

from flask import Flask
import hosting
from wsgi import install_demo_gate, configure_demo_access


class PublicDemoTests(unittest.TestCase):
    def app(self):
        application = Flask('public-demo-test')
        application.add_url_rule('/', 'home', lambda: 'demo')
        application.add_url_rule('/_dash-update-component', 'callback', lambda: 'callback', methods=['POST'])
        return application

    def test_explicit_public_demo_allows_anonymous_home_and_callbacks(self):
        application = self.app()
        with patch('wsgi.HOSTED_DEMO', True), patch.dict(os.environ, {'CRIMSON_PUBLIC_DEMO':'1'}, clear=True):
            configure_demo_access(application)
        client = application.test_client()
        self.assertEqual(client.get('/').status_code, 200)
        self.assertEqual(client.post('/_dash-update-component').status_code, 200)
        self.assertNotIn('WWW-Authenticate', client.get('/').headers)

    def test_hosted_access_remains_private_without_explicit_public_choice(self):
        application = self.app()
        with patch('wsgi.HOSTED_DEMO', True), patch.dict(os.environ, {'CRIMSON_DEMO_PASSWORD':'test-only'}, clear=True):
            configure_demo_access(application)
        self.assertEqual(application.test_client().get('/').status_code, 401)

    def test_public_mode_does_not_disable_hosted_compute_limits(self):
        with patch('wsgi.HOSTED_DEMO', True), patch.dict(os.environ, {'CRIMSON_PUBLIC_DEMO':'1'}, clear=True):
            configure_demo_access(self.app())
            import wsgi
            self.assertTrue(wsgi.HOSTED_DEMO)


class DemoAccessTests(unittest.TestCase):
    def setUp(self):
        application = Flask(__name__)
        application.add_url_rule('/', 'home', lambda: 'demo')
        application.add_url_rule('/health', 'health', lambda: {'status': 'ok'})
        application.add_url_rule('/_dash-update-component', 'callback', lambda: 'callback', methods=['POST'])
        application.add_url_rule('/assets/art.png', 'art', lambda: 'image')
        install_demo_gate(application, 'guest', 'dummy-password-for-test-only')
        self.client = application.test_client()

    def credentials(self, password='dummy-password-for-test-only', username='guest'):
        value = base64.b64encode((username + ':' + password).encode()).decode()
        return {'Authorization': 'Basic ' + value}

    def test_anonymous_home_prompts_for_access(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 401)
        self.assertIn('Basic realm=', response.headers['WWW-Authenticate'])

    def test_anonymous_callback_cannot_use_ai_or_calculations(self):
        self.assertEqual(self.client.post('/_dash-update-component', json={}).status_code, 401)

    def test_anonymous_assets_are_also_protected(self):
        self.assertEqual(self.client.get('/assets/art.png').status_code, 401)

    def test_health_probe_works_without_credentials(self):
        self.assertEqual(self.client.get('/health').json, {'status': 'ok'})

    def test_correct_credentials_allow_home_and_callbacks(self):
        self.assertEqual(self.client.get('/', headers=self.credentials()).status_code, 200)
        self.assertEqual(self.client.post('/_dash-update-component', headers=self.credentials()).status_code, 200)

    def test_wrong_username_or_password_is_rejected(self):
        self.assertEqual(self.client.get('/', headers=self.credentials(password='wrong')).status_code, 401)
        self.assertEqual(self.client.get('/', headers=self.credentials(username='wrong')).status_code, 401)

    def test_non_ascii_bad_credentials_return_refusal(self):
        self.assertEqual(self.client.get('/', headers=self.credentials(username='visiteur-é')).status_code, 401)

    def test_private_responses_are_not_publicly_cached_or_indexed(self):
        response = self.client.get('/', headers=self.credentials())
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        self.assertEqual(response.headers['X-Robots-Tag'], 'noindex, nofollow')

    def test_missing_demo_password_fails_closed(self):
        with self.assertRaises(RuntimeError):
            install_demo_gate(Flask('missing'), 'guest', '')


class CalculationConcurrencyTests(unittest.TestCase):
    def test_hosted_calculations_cannot_allocate_in_parallel(self):
        active = 0
        peak = 0
        counts_lock = threading.Lock()
        start = threading.Barrier(4)
        with patch.object(hosting, 'HOSTED_DEMO', True):
            @hosting.one_calculation_at_a_time
            @lru_cache(maxsize=4)
            def calculate(value):
                nonlocal active, peak
                with counts_lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(.015)
                with counts_lock:
                    active -= 1
                return value * 2
        def request(value):
            start.wait(timeout=2)
            return calculate(value)
        with ThreadPoolExecutor(max_workers=4) as executor:
            self.assertEqual(list(executor.map(request, range(4))), [0, 2, 4, 6])
        self.assertEqual(peak, 1)
        self.assertEqual(calculate.cache_info().currsize, 4)
        calculate.cache_clear()
        self.assertEqual(calculate.cache_info().currsize, 0)

    def test_nested_calculations_do_not_deadlock(self):
        with patch.object(hosting, 'HOSTED_DEMO', True):
            inner = hosting.one_calculation_at_a_time(lambda: 7)
            outer = hosting.one_calculation_at_a_time(inner)
        self.assertEqual(outer(), 7)
