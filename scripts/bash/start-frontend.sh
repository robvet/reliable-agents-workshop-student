#!/bin/bash
# Serve the static frontend on http://localhost:5500.
#
# The backend CORS config only allows the UI origin on port 5500 (see src/app/main.py),
# so this server must run on 5500. It serves the plain static files in src/frontend and
# talks to the backend at http://localhost:8010 (see src/frontend/app.js).
#
# Run the backend separately (./start, or the VS Code debugger) so you can debug it
# while the UI stays up.

set -e

cd "$(dirname "${BASH_SOURCE[0]}")/../../src/frontend"

# Free our own port. -sTCP:LISTEN matches only the process LISTENING on 5500. Without it
# lsof also lists browser tabs holding a connection, and we would kill the browser too.
lsof -ti:5500 -sTCP:LISTEN 2>/dev/null | xargs -r kill
sleep 1

echo -e "\033[36mFrontend -> http://localhost:5500\033[0m"

# Open the browser once the server has had a moment to bind. The ?t= timestamp makes every
# launch a fresh URL, so the browser can never hand you a stale cached page.
(sleep 1; open "http://localhost:5500/?t=$(date +%s)") &

# Serve with caching disabled so the browser can never show a stale index.html/app.js
# in dev. Without this, http.server sends Last-Modified/304 and browsers reuse old files.
exec python3 -c '
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_header(self, key, value):
        # Drop Last-Modified so the browser never issues a conditional 304 revalidate.
        if key.lower() == "last-modified":
            return
        super().send_header(key, value)

port = int(sys.argv[1])
HTTPServer(("127.0.0.1", port), NoCacheHandler).serve_forever()
' 5500
