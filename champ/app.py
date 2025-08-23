from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix  # optional, safe behind proxies

from champ.routes.chat import champ_bp
from champ.routes.dashboard import dashboard_bp
from champ.routes.metrics import metrics_bp
# app.py (or wherever you init Flask)
from champ.routes.insights import insights_bp




def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Optional: nicer JSON output in logs/responses (no functional change)
    app.config["JSON_SORT_KEYS"] = False

    # Optional: respect X-Forwarded-* when behind a proxy/load balancer
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    # Blueprints
    app.register_blueprint(dashboard_bp, url_prefix="/")
    app.register_blueprint(champ_bp, url_prefix="/api/champ")
    app.register_blueprint(metrics_bp, url_prefix="/api/metrics")
    app.register_blueprint(insights_bp, url_prefix="/api")
    
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=True)
