"""One process keeps the small demo's caches and shared usage limits together."""
import os

bind = '0.0.0.0:' + os.getenv('PORT', '10000')
workers = 1
worker_class = 'gthread'
threads = 4
timeout = 900
graceful_timeout = 30
accesslog = '-'
errorlog = '-'
capture_output = True
preload_app = False
