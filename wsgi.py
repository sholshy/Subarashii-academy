import os
import sys
from pathlib import Path
from werkzeug.middleware.proxy_fix import ProxyFix

# Configurar rutas para que Django encuentre sus módulos
BASE_DIR = Path(__file__).resolve().parent / 'smart_showcase'
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Importar aplicación Flask de la Academia
from public_web import app as flask_app

# Inicializar Django y ejecutar migraciones automáticas al iniciar en Render
django_app = None
try:
    import django
    django.setup()
    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    
    # Auto-migración e inicialización de admin
    try:
        call_command('migrate', interactive=False)
        call_command('init_admin')
    except Exception as _mig_err:
        print(f"[WSGI Startup] Migration/admin notice: {_mig_err}")

    django_app = get_wsgi_application()
    print("[WSGI] Django Smart Showcase inicializado correctamente.")
except Exception as e:
    print(f"[WSGI] Error inicializando Django: {e}")

class UnifiedApp:
    """
    Despachador unificado de peticiones:
    - Rutas /admin, /catalog, /inventory, /showcases, /pricing, /v/ -> Django
    - Rutas de ranking, torneos, temporadas, sala en vivo -> Flask (Academia)
    """
    def __init__(self, django_app, flask_app):
        self.django_app = django_app
        self.flask_app = flask_app
        self.django_prefixes = (
            '/admin',
            '/catalog',
            '/inventory',
            '/showcases',
            '/pricing',
            '/v/',
            '/accounts',
            '/static/admin',
            '/static/rest_framework',
        )

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if self.django_app and any(path.startswith(prefix) for prefix in self.django_prefixes):
            return self.django_app(environ, start_response)
        return self.flask_app(environ, start_response)

app = UnifiedApp(django_app, flask_app)

# ProxyFix para Render y proxies inversos
app = ProxyFix(
    app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    from werkzeug.serving import run_simple
    run_simple("0.0.0.0", port, app, use_reloader=False)
