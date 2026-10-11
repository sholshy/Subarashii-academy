import os
from werkzeug.middleware.proxy_fix import ProxyFix
from public_web import app

# ProxyFix para soportar proxies inversos (Render, Cloudflare, Nginx, Railway)
# Corrige request.remote_addr, scheme (https) y cabeceras de host.
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
