from flask import Blueprint, jsonify
import MetaTrader5 as mt5
from flasgger import swag_from
import logging
from lib import ensure_symbol_in_marketwatch

symbol_bp = Blueprint('symbol', __name__)
logger = logging.getLogger(__name__)

@symbol_bp.route('/symbol_info_tick/<symbol>', methods=['GET'])
@swag_from({
    'tags': ['Symbol'],
    'security': [{'ApiKeyAuth': []}],
    'parameters': [
        {
            'name': 'symbol',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'Symbol name to retrieve tick information.'
        }
    ],
    'responses': {
        200: {
            'description': 'Tick information retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'bid': {'type': 'number'},
                    'ask': {'type': 'number'},
                    'last': {'type': 'number'},
                    'volume': {'type': 'integer'},
                    'time': {'type': 'integer'}
                }
            }
        },
        400: {
            'description': 'Failed to add symbol to MarketWatch.'
        },
        404: {
            'description': 'Failed to get symbol tick info.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def get_symbol_info_tick_endpoint(symbol):
    """
    Get Symbol Tick Information
    ---
    description: Retrieve the latest tick information for a given symbol.
    """
    try:
        if not mt5.initialize():
            logger.error("MT5 initialization failed in get_symbol_info_tick.")
            return jsonify({"error": "MT5 initialization failed"}), 500

        if not ensure_symbol_in_marketwatch(symbol):
            logger.error(f"Failed to add symbol {symbol} to MarketWatch.")
            return jsonify({"error": f"Failed to add symbol {symbol} to MarketWatch"}), 400
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Failed to get tick info for symbol {symbol}.")
            return jsonify({"error": "Failed to get symbol tick info"}), 404
        
        tick_dict = tick._asdict()
        return jsonify(tick_dict)
    
    except Exception as e:
        logger.error(f"Error in get_symbol_info_tick: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@symbol_bp.route('/symbol_info/<symbol>', methods=['GET'])
@swag_from({
    'tags': ['Symbol'],
    'security': [{'ApiKeyAuth': []}],
    'parameters': [
        {
            'name': 'symbol',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'Symbol name to retrieve information.'
        }
    ],
    'responses': {
        200: {
            'description': 'Symbol information retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'path': {'type': 'string'},
                    'description': {'type': 'string'},
                    'volume_min': {'type': 'number'},
                    'volume_max': {'type': 'number'},
                    'volume_step': {'type': 'number'},
                    'price_digits': {'type': 'integer'},
                    'spread': {'type': 'number'},
                    'points': {'type': 'integer'},
                    'trade_mode': {'type': 'integer'},
                }
            }
        },
        400: {
            'description': 'Failed to add symbol to MarketWatch.'
        },
        404: {
            'description': 'Failed to get symbol info.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def get_symbol_info(symbol):
    """
    Get Symbol Information
    ---
    description: Retrieve detailed information for a given symbol.
    """
    try:
        if not mt5.initialize():
            logger.error("MT5 initialization failed in get_symbol_info.")
            return jsonify({"error": "MT5 initialization failed"}), 500

        if not ensure_symbol_in_marketwatch(symbol):
            logger.error(f"Failed to add symbol {symbol} to MarketWatch.")
            return jsonify({"error": f"Failed to add symbol {symbol} to MarketWatch"}), 400
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Failed to get info for symbol {symbol}.")
            return jsonify({"error": "Failed to get symbol info"}), 404
        
        symbol_info_dict = symbol_info._asdict()
        return jsonify(symbol_info_dict)
    
    except Exception as e:
        logger.error(f"Error in get_symbol_info: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500