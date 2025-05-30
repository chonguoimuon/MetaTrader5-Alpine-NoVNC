import logging
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import MetaTrader5 as mt5
from flasgger import Swagger
from werkzeug.middleware.proxy_fix import ProxyFix
from swagger import swagger_config

# Import routes
from routes.health import health_bp
from routes.symbol import symbol_bp
from routes.data import data_bp
from routes.position import position_bp
from routes.order import order_bp
from routes.history import history_bp
from routes.error import error_bp
from routes.telegram import telegram_bp
from routes.login import login_bp  # Added new login blueprint

# Import worker functions
from trailing_stop_worker import start_worker, stop_worker
from trade_signal_worker import start_worker as start_signal_worker, stop_worker as stop_signal_worker

load_dotenv()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Load the API token from environment variable
MT5_API_AUTH_TOKEN = os.environ.get('MT5_API_AUTH_TOKEN')

# Middleware to check Authorization header
@app.before_request
def check_auth_token():
    # Skip auth check for health endpoint and Swagger-related endpoints
    swagger_paths = ['/apidocs/', '/apispec_1.json']
    if (request.path == '/health' or 
        request.path in swagger_paths or 
        request.path.startswith('/flasgger_static/')):
        return None
    
    # Get the Authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        logger.warning("No Authorization header provided")
        return jsonify({"error": "Authorization header is required"}), 401
    
    # Accept either 'Bearer <token>' or raw token
    token = auth_header
    if auth_header.lower().startswith('bearer '):
        try:
            auth_type, token = auth_header.split(' ', 1)
        except ValueError:
            logger.warning("Malformed Authorization header")
            return jsonify({"error": "Malformed Authorization header, expected 'Bearer <token>' or raw token"}), 401
    
    if not MT5_API_AUTH_TOKEN:
        logger.error("MT5_API_AUTH_TOKEN environment variable not set")
        return jsonify({"error": "Server configuration error"}), 500
    
    if token != MT5_API_AUTH_TOKEN:
        logger.warning("Invalid API token provided")
        return jsonify({"error": "Invalid API token"}), 401
    
    # Token is valid, proceed with the request
    logger.debug("API token validated successfully")
    return None

swagger = Swagger(app, config=swagger_config)

# Register blueprints
app.register_blueprint(health_bp)
app.register_blueprint(symbol_bp)
app.register_blueprint(data_bp)
app.register_blueprint(position_bp)
app.register_blueprint(order_bp)
app.register_blueprint(history_bp)
app.register_blueprint(error_bp)
app.register_blueprint(telegram_bp)
app.register_blueprint(login_bp)  # Register new login blueprint

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

if __name__ == '__main__':
    try:
        start_worker()
        start_signal_worker()
        app.run(host='0.0.0.0', port=5001)
    finally:
        stop_worker()
        stop_signal_worker()
        logger.info("Flask app finished running.")
