from flask import Blueprint, jsonify, request
import MetaTrader5 as mt5
import logging
from flasgger import swag_from
import time
from datetime import datetime, timedelta
import pytz

from trailing_stop_worker import add_trailing_stop_job_to_worker
from lib import ensure_symbol_in_marketwatch

order_bp = Blueprint('order', __name__)
logger = logging.getLogger(__name__)

@order_bp.route('/order', methods=['POST'])
@swag_from({
    'tags': ['Order'],
    'security': [{'ApiKeyAuth': []}],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'symbol': {'type': 'string', 'description': 'Trading symbol (e.g., "EURUSD").'},
                    'volume': {'type': 'number', 'description': 'Volume of the order (e.g., 0.1).'},
                    'type': {'type': 'string', 'enum': ['BUY', 'SELL'], 'description': 'Order type ("BUY" or "SELL").'},
                    'deviation': {'type': 'integer', 'default': 20, 'description': 'Maximum allowed deviation from the requested price in points (default is 20).'},
                    'magic': {'type': 'integer', 'default': 0, 'description': 'Magic number for the order (default is 0).'},
                    'comment': {'type': 'string', 'default': '', 'description': 'Comment for the order (default is empty string).'},
                    'type_filling': {'type': 'string', 'enum': ['ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', 'ORDER_FILLING_RETURN'], 'description': 'Order filling type (IOC, FOK, or RETURN).'},
                    'sl': {'type': 'number', 'description': 'Optional Stop Loss price.'},
                    'tp': {'type': 'number', 'description': 'Optional Take Profit price.'},
                    'ts': {'type': 'number', 'description': 'Optional Trailing Stop distance in points. If provided, trailing stop is enabled for the new position.'},
                    'token': {'type': 'string', 'description': 'API token for authentication if Authorization header is not provided.'}
                },
                'required': ['symbol', 'volume', 'type']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Order executed successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'result': {
                        'type': 'object',
                        'properties': {
                            'retcode': {'type': 'integer'},
                            'order': {'type': 'integer'},
                            'deal': {'type': 'integer'},
                            'magic': {'type': 'integer'},
                            'price': {'type': 'number'},
                            'volume': {'type': 'number'},
                            'symbol': {'type': 'string'},
                            'comment': {'type': 'string'}
                        }
                    },
                    'position_ticket': {'type': 'integer', 'description': 'Ticket of the newly created position, if any.'},
                    'trailing_stop_status': {'type': 'string', 'description': 'Status of trailing stop activation (e.g., "activated", "not requested", "failed").'}
                }
            }
        },
        400: {
            'description': 'Bad request or order failed.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def post_order():
    """
    Place a Market Order
    ---
    description: Place a market buy or sell order for a given symbol and volume. Authenticate using Authorization header or token in request body.
    """
    try:
        data = request.get_json()
        if not data or 'symbol' not in data or 'volume' not in data or 'type' not in data:
            return jsonify({"error": "symbol, volume, and type are required"}), 400

        symbol = str(data['symbol'])
        if not ensure_symbol_in_marketwatch(symbol):
            return jsonify({"error": f"Failed to add symbol {symbol} to MarketWatch"}), 400        
        
        volume = float(data['volume'])
        order_type_str = data['type'].upper()
        deviation = int(data.get('deviation', 20))
        magic = int(data.get('magic', 0))
        comment = str(data.get('comment', ''))
        type_filling_str = data.get('type_filling', 'ORDER_FILLING_IOC').upper()
        ts_distance = data.get('ts')

        order_type_map = {
            'BUY': mt5.ORDER_TYPE_BUY,
            'SELL': mt5.ORDER_TYPE_SELL
        }
        order_type = order_type_map.get(order_type_str)
        if order_type is None:
            return jsonify({"error": f"Invalid order type: {order_type_str}. Must be 'BUY' or 'SELL'."}), 400

        type_filling_map = {
            'ORDER_FILLING_IOC': mt5.ORDER_FILLING_IOC,
            'ORDER_FILLING_FOK': mt5.ORDER_FILLING_FOK,
            'ORDER_FILLING_RETURN': mt5.ORDER_FILLING_RETURN
        }
        type_filling = type_filling_map.get(type_filling_str)
        if type_filling is None:
             return jsonify({"error": f"Invalid filling type: {type_filling_str}. Must be 'ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', or 'ORDER_FILLING_RETURN'."}), 400

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Failed to get tick for symbol: {symbol}")
            return jsonify({"error": f"Failed to get tick for symbol: {symbol}"}), 400

        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        if price == 0.0:
             logger.error(f"Invalid price retrieved for symbol: {symbol}")
             return jsonify({"error": f"Invalid price retrieved for symbol: {symbol}"}), 400

        request_data = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling,
        }

        if 'sl' in data and data['sl'] is not None:
            request_data["sl"] = float(data['sl'])
        if 'tp' in data and data['tp'] is not None:
            request_data["tp"] = float(data['tp'])

        logger.info(f"Sending order request: {request_data}")

        result = mt5.order_send(request_data)
        logger.debug(f"Order result: {result}")

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_code, error_str = mt5.last_error()
            error_message = result.comment if result else "MT5 order_send returned None"
            logger.error(f"Order failed: {error_message}. MT5 Error: {error_str}")

            return jsonify({
                "error": f"Order failed: {error_message}",
                "mt5_error": error_str,
                "result": result._asdict() if result else None
            }), 400

        logger.info(f"Order executed successfully. Result: {result._asdict()}")

        trailing_stop_status = "not requested"
        position_ticket = None

        if ts_distance is not None:
            deal_ticket = result.deal
            if deal_ticket != 0:
                logger.info(f"Order resulted in deal ticket: {deal_ticket}. Attempting to find associated position.")
                utc_now = datetime.now(pytz.UTC)
                from_date = utc_now - timedelta(seconds=5)
                to_date = utc_now + timedelta(seconds=1)

                deals = mt5.history_deals_get(ticket=deal_ticket)
                found_position_ticket = None
                if deals:
                    for deal in deals:
                        if deal.ticket == deal_ticket and deal.position_id != 0 and deal.order == result.order:
                            found_position_ticket = deal.position_id
                            logger.info(f"Found position ticket {found_position_ticket} for deal {deal_ticket} and order {result.order}.")
                            break

                if found_position_ticket:
                    position_ticket = found_position_ticket
                    positions = mt5.positions_get(ticket=position_ticket)
                    if positions and len(positions) > 0:
                        new_position = positions[0]
                        added_to_worker = add_trailing_stop_job_to_worker(position_ticket, float(ts_distance))
                        if added_to_worker:
                            trailing_stop_status = "activated"
                            logger.info(f"Trailing stop job added to worker for position {position_ticket}.")
                        else:
                            trailing_stop_status = "failed to activate (worker add failed)"
                            logger.error(f"Failed to add trailing stop job to worker for position {position_ticket}.")
                    else:
                        trailing_stop_status = "failed to activate (position details not found)"
                        logger.error(f"Deal {deal_ticket} associated with position {position_ticket}, but position details could not be retrieved.")
                else:
                    trailing_stop_status = "failed to activate (position not linked to deal or order mismatch)"
                    logger.error(f"Deal {deal_ticket} found, but no associated position_id or order mismatch with {result.order}.")
            else:
                trailing_stop_status = "not activated (no deal created)"
                logger.warning(f"Order executed successfully but did not result in a deal (ticket {result.order}). Trailing stop not activated.")

        response_data = {
            "message": "Order executed successfully",
            "result": result._asdict(),
            "trailing_stop_status": trailing_stop_status
        }
        if position_ticket is not None:
             response_data["position_ticket"] = position_ticket

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in post_order: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500