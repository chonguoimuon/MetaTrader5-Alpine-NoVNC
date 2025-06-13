import logging
import requests
import MetaTrader5 as mt5
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)

# Đường dẫn tới thư mục cấu hình trong volume
CONFIG_DIR = "/config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "signal_config.json")

# Tạo thư mục config nếu chưa tồn tại
if not os.path.exists(CONFIG_DIR):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        logger.info(f"Created config directory: {CONFIG_DIR}")
    except Exception as e:
        logger.error(f"Failed to create config directory {CONFIG_DIR}: {str(e)}")
        raise

# Cấu hình Telegram mặc định
DEFAULT_CONFIG = {
    "bot_token": "",
    "chat_id": "",
    "enabled": False,
    "send_open": True,
    "send_close": True,
    "send_modify_tp_sl": True
}

# Biến toàn cục để lưu cấu hình trong bộ nhớ
telegram_config = DEFAULT_CONFIG.copy()

def load_telegram_config():
    """Load cấu hình Telegram từ file signal_config.json."""
    global telegram_config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                # Cập nhật telegram_config với các giá trị từ file, giữ mặc định nếu thiếu
                telegram_config.update({
                    key: loaded_config.get(key, DEFAULT_CONFIG[key])
                    for key in DEFAULT_CONFIG
                })
                logger.info(f"Telegram config loaded from {CONFIG_FILE}")
        else:
            logger.info(f"No signal_config.json found at {CONFIG_FILE}, using default Telegram config")
            save_telegram_config()  # Tạo file mới với cấu hình mặc định
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {CONFIG_FILE}: {str(e)}")
        telegram_config = DEFAULT_CONFIG.copy()
        save_telegram_config()  # Tạo lại file nếu JSON không hợp lệ
    except Exception as e:
        logger.error(f"Error loading Telegram config from {CONFIG_FILE}: {str(e)}")
        telegram_config = DEFAULT_CONFIG.copy()
        save_telegram_config()  # Lưu cấu hình mặc định nếu lỗi

def save_telegram_config():
    """Lưu cấu hình Telegram vào file signal_config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(telegram_config, f, indent=4)
        logger.info(f"Telegram config saved to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error saving Telegram config to {CONFIG_FILE}: {str(e)}")
        raise

def set_telegram_config(bot_token, chat_id, send_open=None, send_close=None, send_modify_tp_sl=None):
    """Thiết lập hoặc cập nhật cấu hình Telegram và lưu vào file."""
    try:
        telegram_config["bot_token"] = bot_token
        telegram_config["chat_id"] = chat_id
        # Cập nhật các trường boolean nếu được cung cấp
        if send_open is not None:
            telegram_config["send_open"] = bool(send_open)
        if send_close is not None:
            telegram_config["send_close"] = bool(send_close)
        if send_modify_tp_sl is not None:
            telegram_config["send_modify_tp_sl"] = bool(send_modify_tp_sl)
        save_telegram_config()  # Lưu cấu hình vào file
        logger.info("Telegram config updated and saved to signal_config.json")
    except Exception as e:
        logger.error(f"Error setting Telegram config: {str(e)}")
        raise

def get_telegram_config():
    """Lấy cấu hình Telegram hiện tại."""
    return telegram_config

def send_telegram_message(message, action):
    """Gửi tin nhắn đến Telegram nếu action được bật và message không rỗng."""
    if not message:
        logger.info(f"No message to send for action: {action} (empty message).")
        return False
    if not telegram_config["enabled"]:
        logger.info("Telegram signal sending is disabled.")
        return False
    if not telegram_config["bot_token"] or not telegram_config["chat_id"]:
        logger.error("Telegram bot token or chat ID not configured.")
        return False
    # Kiểm tra xem action có được bật trong cấu hình không
    if action == "open" and not telegram_config["send_open"]:
        logger.info("Open signal sending is disabled.")
        return False
    if action == "close" and not telegram_config["send_close"]:
        logger.info("Close signal sending is disabled.")
        return False
    if action == "modify_tp_sl" and not telegram_config["send_modify_tp_sl"]:
        logger.info("Modify TP/SL signal sending is disabled.")
        return False

    url = f"https://api.telegram.org/bot{telegram_config['bot_token']}/sendMessage"
    payload = {
        "chat_id": telegram_config["chat_id"],
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Telegram message sent successfully for action: {action}.")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        return False

def format_trade_signal(deal, position_ticket=None, action="open", **kwargs):
    """Định dạng tín hiệu giao dịch từ deal hoặc vị thế."""
    deal_dict = deal if isinstance(deal, dict) else deal._asdict()
    symbol = deal_dict.get("symbol", "N/A")
    volume = deal_dict.get("volume", 0.0)
    price = deal_dict.get("price", 0.0)
    order_type = "BUY" if deal_dict.get("type") == mt5.DEAL_TYPE_BUY else "SELL" if deal_dict.get("type") == mt5.DEAL_TYPE_SELL else "N/A"
    timestamp = deal_dict.get("time", 0)
    time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "open":
        message = (
            "🎰 *New Trade Opened (MT5)*\n"
            f"**Symbol**: {symbol}\n"
            f"**Type**: {order_type}\n"
            f"**Volume**: {volume:.2f}\n"
            f"**Price**: {price:.5f}\n"
            f"**Time**: {time_str}\n"
            f"**Position Ticket**: #ES{position_ticket if position_ticket else 'N/A'}"
        )
    elif action == "close":
        profit = deal_dict.get("profit", 0.0)
        message = (
            "📬 *Trade Closed (MT5)*\n"
            f"**Symbol**: {symbol}\n"
            f"**Type**: {order_type}\n"
            f"**Volume**: {volume:.2f}\n"
            f"**Close Price**: {price:.5f}\n"
            f"**Profit**: {profit:.2f}\n"
            f"**Time**: {time_str}\n"
            f"**Position Ticket**: #ES{position_ticket if position_ticket else 'N/A'}"
        )
    elif action == "modify_tp_sl":
        old_tp = kwargs.get("old_tp", 0.0)
        new_tp = kwargs.get("new_tp", 0.0)
        old_sl = kwargs.get("old_sl", 0.0)
        new_sl = kwargs.get("new_sl", 0.0)
        
        # Khởi tạo danh sách các dòng thay đổi
        changes = []
        if new_tp != old_tp:
            changes.append(f"**New TP**: {new_tp:.5f} (was {old_tp:.5f})")
        if new_sl != old_sl:
            changes.append(f"**New SL**: {new_sl:.5f} (was {old_sl:.5f})")
        
        # Nếu không có thay đổi, trả về chuỗi rỗng
        if not changes:
            return ""
        
        # Nối các thay đổi với ký tự xuống dòng
        changes_text = "\n".join(changes)
        
        # Tạo tin nhắn với các thay đổi
        message = (
            "♻️ *TP/SL Modified (MT5)*\n"
            f"**Symbol**: {symbol}\n"
            f"**Position Ticket**: #ES{position_ticket if position_ticket else 'N/A'}\n"
            f"{changes_text}\n"
            f"**Time**: {time_str}"
        )
    else:
        message = f"Unknown action: {action}"
        logger.warning(message)
    return message