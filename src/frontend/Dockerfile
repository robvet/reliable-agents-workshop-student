# ============================================================
# Frontend — static site served by nginx, which also reverse-
# proxies the API paths to the backend Container App so the
# browser stays same-origin (no CORS). APIM can slot into the
# proxy hop later.
#   Build context: src/frontend
#   docker build -t frontend -f src/frontend/Dockerfile src/frontend
# ============================================================

FROM nginx:alpine

# Reverse-proxy + static config template. nginx:alpine's entrypoint runs
# envsubst on every /etc/nginx/templates/*.template file at container start
# (only substituting names that match an actual env var, so nginx's own
# $uri/$scheme/etc. variables are left untouched) and writes the result to
# /etc/nginx/conf.d/<name> — this is how APIM_SUBSCRIPTION_KEY gets injected
# without ever being baked into the image or committed to source control.
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Static site (index.html, app.js, styles.css, html/, images/).
COPY . /usr/share/nginx/html/

EXPOSE 80
