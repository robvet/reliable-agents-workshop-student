# ============================================================
# Frontend — static site served by nginx, which also reverse-
# proxies the API paths to the backend Container App so the
# browser stays same-origin (no CORS). APIM can slot into the
# proxy hop later.
#   Build context: repository root
#   docker build -t frontend -f src/frontend/Dockerfile .
# ============================================================

FROM nginx:alpine

# Reverse-proxy + static config template. nginx:alpine's entrypoint runs
# envsubst on every /etc/nginx/templates/*.template file at container start
# (only substituting names that match an actual env var, so nginx's own
# $uri/$scheme/etc. variables are left untouched) and writes the result to
# /etc/nginx/conf.d/<name> — this is how APIM_SUBSCRIPTION_KEY gets injected
# without ever being baked into the image or committed to source control.
COPY src/frontend/nginx.conf /etc/nginx/templates/default.conf.template

# Static site and workshop lab documents.
COPY src/frontend/ /usr/share/nginx/html/
COPY labs/ /usr/share/nginx/html/labs/

EXPOSE 80
