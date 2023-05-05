import sys
import time
import signal
import logging
import requests
import threading

from flask_limiter import Limiter
from token_bucket import TokenBucket
from flask import Flask, request, Response

app = Flask(__name__)

# Set up logging to STDOUT
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Replace the following with the desired rate limit
CONCURRENT_REQUESTS_LIMIT = 100
REQUESTS_PER_MINUTE_LIMIT = 3500
PROXY_TARGET = "https://api.openai.com"

semaphore = threading.Semaphore(CONCURRENT_REQUESTS_LIMIT)
active_requests = 0
active_requests_lock = threading.Lock()

limiter = Limiter(
    app,
    key_func=lambda: request.remote_addr,  # Although we're not limiting clients, this is required by the Limiter
    default_limits=[],  # No rate limits for clients
)

token_bucket = TokenBucket(REQUESTS_PER_MINUTE_LIMIT, 60)  # 60 seconds for a minute

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    with semaphore:
        if not token_bucket.consume():
            wait_time = token_bucket.get_wait_time()
            logging.info(f"No tokens available, waiting for {wait_time} seconds")
            time.sleep(wait_time)
            token_bucket.consume()

        logging.info(f"Forwarding request to {PROXY_TARGET}/{path}")
        resp = requests.request(
            method=request.method,
            url=f"{PROXY_TARGET}/{path}",
            headers={key: value for (key, value) in request.headers.items() if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
        )

    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]

    response = Response(resp.content, resp.status_code, headers)
    return response


def signal_handler(signal, frame):
    logging.info("Received signal, waiting for proxy calls to complete and shutting down gracefully...")

    # Wait for active requests to complete
    while True:
        with active_requests_lock:
            if active_requests == 0:
                break
        time.sleep(1)

    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
