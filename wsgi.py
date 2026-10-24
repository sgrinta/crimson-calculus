"""Gunicorn entry point with a password gate for the shared online demo."""
from hmac import compare_digest
import os

from flask import Response, request

from app import server
from hosting import HOSTED_DEMO


def install_demo_gate(application, username, password):
    if not username or not password:
        raise RuntimeError('Set CRIMSON_DEMO_USERNAME and CRIMSON_DEMO_PASSWORD before publishing the hosted demo.')

    @application.before_request
    def require_demo_access():
        # The platform health probe reveals no personal data or paid capability.
        if request.path == '/health' and request.method in ('GET', 'HEAD'):
            return None
        auth = request.authorization
        valid = bool(auth and auth.type == 'basic')
        if valid:
            valid_user = compare_digest((auth.username or '').encode(), username.encode())
            valid_password = compare_digest((auth.password or '').encode(), password.encode())
            valid = valid_user and valid_password
        if not valid:
            return Response('Crimson Calculus demo: enter the shared access details.', 401,
                            {'WWW-Authenticate': 'Basic realm="Crimson Calculus", charset="UTF-8"',
                             'Cache-Control': 'no-store'})
        return None

    @application.after_request
    def private_demo_response(response):
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        if request.path != '/health':
            response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response


def configure_demo_access(application):
    # Public access is an explicit operator choice; AI usage limits still apply.
    if HOSTED_DEMO and os.getenv('CRIMSON_PUBLIC_DEMO') != '1':
        install_demo_gate(application, os.getenv('CRIMSON_DEMO_USERNAME', 'guest'),
                          os.getenv('CRIMSON_DEMO_PASSWORD', ''))


configure_demo_access(server)
