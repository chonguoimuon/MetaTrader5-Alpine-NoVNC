from flask import Blueprint, jsonify, request
import MetaTrader5 as mt5
import logging
from flasgger import swag_from
import json
import os
import uuid

login_bp = Blueprint('login', __name__)
logger = logging.getLogger(__name__)

# Đường dẫn tới thư mục cấu hình trong volume
CONFIG_DIR = "/config"
TOKEN_FILE = os.path.join(CONFIG_DIR, "api_token.json")

# Tạo thư mục config nếu chưa tồn tại
if not os.path.exists(CONFIG_DIR):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        logger.info(f"Created config directory: {CONFIG_DIR}")
    except Exception as e:
        logger.error(f"Failed to create config directory {CONFIG_DIR}: {str(e)}")
        raise

def load_api_token():
    """Load API token từ file api_token.json."""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                data = json.load(f)
                return data.get("token", "")
        else:
            logger.info(f"No api_token.json found at {TOKEN_FILE}, creating new token.")
            return generate_and_save_token()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {TOKEN_FILE}: {str(e)}")
        return generate_and_save_token()
    except Exception as e:
        logger.error(f"Error loading API token from {TOKEN_FILE}: {str(e)}")
        return generate_and_save_token()

def generate_and_save_token():
    """Tạo token mới và lưu vào file api_token.json."""
    try:
        new_token = str(uuid.uuid4())
        token_data = {"token": new_token}
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=4)
        logger.info(f"New API token generated and saved to {TOKEN_FILE}")
        return new_token
    except Exception as e:
        logger.error(f"Error generating/saving API token to {TOKEN_FILE}: {str(e)}")
        raise

@login_bp.route('/login', methods=['POST'])
@swag_from({
    'tags': ['Login'],
    'security': [{'ApiKeyAuth': []}],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'login': {
                        'type': 'integer',
                        'description': 'MetaTrader5 account login number'
                    },
                    'password': {
                        'type': 'string',
                        'description': 'MetaTrader5 account password'
                    },
                    'server': {
                        'type': 'string',
                        'description': 'MetaTrader5 server name'
                    }
                },
                'required': ['login', 'password', 'server']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Login successful',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'success'},
                    'message': {'type': 'string', 'example': 'Logged in successfully'}
                }
            }
        },
        400: {
            'description': 'Invalid request parameters',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        401: {
            'description': 'Unauthorized access',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        500: {
            'description': 'Login failed or internal server error',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    }
})
def login_endpoint():
    """
    Login to MetaTrader5 account
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        login = data.get('login')
        password = data.get('password')
        server = data.get('server')

        if not all([login, password, server]):
            return jsonify({"error": "Missing required fields: login, password, server"}), 400

        if mt5.initialize(login=int(login), password=password, server=server):
            logger.info(f"Successfully logged in to MT5 account {login} on server {server}")
            return jsonify({"status": "success", "message": "Logged in initialize"}), 200
            
        if mt5.login(login=int(login), password=password, server=server):
            logger.info(f"Successfully logged in to MT5 account {login} on server {server}")
            return jsonify({"status": "success", "message": "Logged in successfully"}), 200
            
        error_code = mt5.last_error()[0]
        logger.error(f"MT5 login failed: error code {error_code}")
        return jsonify({"error": f"Login failed: error code {error_code}"}), 500
        
    except ValueError as e:
        logger.warning(f"Invalid input: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@login_bp.route('/account_info', methods=['GET'])
@swag_from({
    'tags': ['Login'],
    'security': [{'ApiKeyAuth': []}],
    'responses': {
        200: {
            'description': 'Account information retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'login': {'type': 'integer', 'description': 'Account login number'},
                    'trade_mode': {'type': 'integer', 'description': 'Trade mode (0: demo, 1: real)'},
                    'leverage': {'type': 'integer', 'description': 'Account leverage'},
                    'balance': {'type': 'number', 'description': 'Account balance'},
                    'equity': {'type': 'number', 'description': 'Account equity'},
                    'margin': {'type': 'number', 'description': 'Used margin'},
                    'margin_free': {'type': 'number', 'description': 'Free margin'},
                    'margin_level': {'type': 'number', 'description': 'Margin level in percentage'},
                    'profit': {'type': 'number', 'description': 'Current profit'},
                    'currency': {'type': 'string', 'description': 'Account currency'},
                    'server': {'type': 'string', 'description': 'Trade server name'},
                    'name': {'type': 'string', 'description': 'Account holder name'},
                    'company': {'type': 'string', 'description': 'Broker company name'}
                }
            }
        },
        401: {
            'description': 'Unauthorized access',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        500: {
            'description': 'Failed to retrieve account info or internal server error',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    }
})
def account_info_endpoint():
    """
    Retrieve all information about the current MetaTrader5 account
    """
    try:
        if not mt5.initialize():
            logger.error("Failed to initialize MetaTrader5")
            return jsonify({"error": "Failed to initialize MetaTrader5"}), 500

        account_info = mt5.account_info()
        if account_info is None:
            error_code = mt5.last_error()[0]
            logger.error(f"Failed to retrieve account info: error code {error_code}")
            return jsonify({"error": f"Failed to retrieve account info: error code {error_code}"}), 500

        account_info_dict = {
            'login': account_info.login,
            'trade_mode': account_info.trade_mode,
            'leverage': account_info.leverage,
            'balance': account_info.balance,
            'equity': account_info.equity,
            'margin': account_info.margin,
            'margin_free': account_info.margin_free,
            'margin_level': account_info.margin_level,
            'profit': account_info.profit,
            'currency': account_info.currency,
            'server': account_info.server,
            'name': account_info.name,
            'company': account_info.company
        }

        logger.info(f"Successfully retrieved account info for login {account_info.login}")
        return jsonify(account_info_dict), 200

    except Exception as e:
        logger.error(f"Error in account_info: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@login_bp.route('/generate_token', methods=['POST'])
@swag_from({
    'tags': ['Login'],
    'security': [{'ApiKeyAuth': []}],
    'responses': {
        200: {
            'description': 'New API token generated successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'success'},
                    'token': {'type': 'string', 'description': 'Newly generated API token'},
                    'message': {'type': 'string', 'example': 'New API token generated and saved'}
                }
            }
        },
        500: {
            'description': 'Failed to generate or save token',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    }
})
def generate_token_endpoint():
    """
    Generate a new API token
    """
    try:
        new_token = generate_and_save_token()
        logger.info("New API token generated successfully")
        return jsonify({
            "status": "success",
            "token": new_token,
            "message": "New API token generated and saved"
        }), 200
    except Exception as e:
        logger.error(f"Error in generate_token: {str(e)}")
        return jsonify({"error": "Failed to generate or save token"}), 500

@login_bp.route('/get_token', methods=['GET'])
@swag_from({
    'tags': ['Login'],
    'security': [{'ApiKeyAuth': []}],
    'responses': {
        200: {
            'description': 'API token retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'success'},
                    'token': {'type': 'string', 'description': 'Current API token'},
                    'message': {'type': 'string', 'example': 'API token retrieved'}
                }
            }
        },
        500: {
            'description': 'Failed to retrieve token',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    }
})
def get_token_endpoint():
    """
    Retrieve the current API token
    """
    try:
        token = load_api_token()
        logger.info("API token retrieved successfully")
        return jsonify({
            "status": "success",
            "token": token,
            "message": "API token retrieved"
        }), 200
    except Exception as e:
        logger.error(f"Error in get_token: {str(e)}")
        return jsonify({"error": "Failed to retrieve token"}), 500