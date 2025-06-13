#!/bin/bash

source /scripts/02-common.sh

log_message "RUNNING" "04-install-mt5.sh"

# Check if MetaTrader 5 is installed
if [ -e "$mt5file" ]; then
    log_message "INFO" "File $mt5file already exists."
else
    log_message "INFO" "File $mt5file is not installed. Installing..."

    # Set Windows 10 mode in Wine and download and install MT5
    # $wine_executable reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d "win10" /f
    log_message "INFO" "Downloading MT5 installer..."
    wget -O /tmp/mt5setup.exe $mt5setup_url > /dev/null 2>&1
    log_message "INFO" "Installing MetaTrader 5..."
    $wine_executable /tmp/mt5setup.exe /auto
    rm -f /tmp/mt5setup.exe
    
    # Đường dẫn đến thư mục nguồn chứa các file MetaTrader
    SOURCE_DIR="/Metatrader"

    # Đường dẫn đến thư mục đích của MetaTrader 5
    DEST_DIR="/config/.wine/drive_c/Program Files/MetaTrader 5"

    # Sao chép tất cả các file từ thư mục nguồn sang thư mục đích và ghi đè
    log_message "INFO" "Đang sao chép tất cả file từ '$SOURCE_DIR' sang '$DEST_DIR'..."
    cp -rv "$SOURCE_DIR"/* "$DEST_DIR"/

    # Kiểm tra xem lệnh copy có thành công không
    if [ $? -eq 0 ]; then
        log_message "INFO" "Sao chép file thành công."
        log_message "INFO" "Đang xóa thư mục nguồn '$SOURCE_DIR' và tất cả nội dung..."
        rm -rf "$SOURCE_DIR"    
    else
        log_message "ERROR" "Lỗi: Không thể sao chép các file. Vui lòng kiểm tra quyền truy cập hoặc đường dẫn."
    fi     
fi