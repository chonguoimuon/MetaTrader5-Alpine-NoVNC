import logging
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import MetaTrader5 as mt5
from flasgger import Swagger
from werkzeug.middleware.proxy_fix import ProxyFix
from swagger import swagger_config
from telegram_utils import load_telegram_config
import json
from routes.login import load_api_token  # Import load_api_token từ routes/login.py

# Import routes
from routes.health import health_bp
from routes.symbol import symbol_bp
from routes.data import data_bp
from routes.position import position_bp
from routes.order import order_bp
from routes.history import history_bp
from routes.error import error_bp
from routes.telegram import telegram_bp
from routes.login import login_bp

# Import worker functions
from trailing_stop_worker import start_worker, stop_worker
from trade_signal_worker import start_worker as start_signal_worker, stop_worker as stop_signal_worker

load_dotenv()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Load the API token from environment variable
MT5_API_AUTH_TOKEN = os.environ.get('MT5_API_AUTH_TOKEN')

# Load Telegram configuration from file at startup
load_telegram_config()

# Middleware to check Authorization header or token in body/query
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
    
    # Check if the request is for /Position or /Order endpoints
    is_position_or_order = request.path.startswith(('/close_position', '/close_all_positions', '/modify_sl_tp', 
                                                    '/get_positions', '/positions_total', '/apply_trailing_stop', 
                                                    '/cancel_trailing_stop', '/list_trailing_stop_jobs', '/order'))
    
    if auth_header:
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
            logger.warning("Invalid API token provided in Authorization header")
            return jsonify({"error": "Invalid API token"}), 401
        
        logger.debug("API token validated successfully via Authorization header")
        return None
    
    # If no Authorization header, check token for /Position and /Order endpoints
    if is_position_or_order:
        try:
            # For GET requests, check token in query parameters
            if request.method == 'GET':
                query_token = request.args.get('token')
                if query_token:
                    stored_token = load_api_token()  # Load token from api_token.json
                    if query_token == stored_token:
                        logger.debug("API token validated successfully via query parameter")
                        return None
                    else:
                        logger.warning("Invalid token provided in query parameter")
                        return jsonify({"error": "Invalid token in query parameter"}), 401
                else:
                    logger.warning("No token provided in query parameter for GET /Position or /Order endpoint")
                    return jsonify({"error": "Authorization header or token in query parameter is required"}), 401
            
            # For POST requests, check token in body
            data = request.get_json(silent=True)
            if data and 'token' in data:
                body_token = data['token']
                stored_token = load_api_token()  # Load token from api_token.json
                if body_token == stored_token:
                    logger.debug("API token validated successfully via request body")
                    return None
                else:
                    logger.warning("Invalid token provided in request body")
                    return jsonify({"error": "Invalid token in request body"}), 401
            else:
                logger.warning("No token provided in request body for /Position or /Order endpoint")
                return jsonify({"error": "Authorization header or token in request body is required"}), 401
        except Exception as e:
            logger.error(f"Error checking token: {str(e)}")
            return jsonify({"error": "Invalid request"}), 400
    
    # For other endpoints, require Authorization header
    logger.warning("No Authorization header provided")
    return jsonify({"error": "Authorization header is required"}), 401

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
app.register_blueprint(login_bp)

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