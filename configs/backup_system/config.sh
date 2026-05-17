#!/bin/bash
# ==============================================================================
# CENTRAL BACKUP CONFIGURATION (SHARED CONFIG)
# ==============================================================================
# This file is loaded by both backup and restore scripts.
# Modify your credentials and system paths here once.

# Telegram Bot Integration
TG_TOKEN="8731584513:AAG8Po3eDs2BFPyrIWDeA23Pel_tKTZQG6w"
TG_CHAT_ID="727541374"


# Cloud Storage Integration (Rclone Remote Name)
RCLONE_REMOTE="gdrive_app"

# Local Directories on VPS
BACKUP_ROOT="/home/backups"
SCRIPTS_DIR="$BACKUP_ROOT/scripts"
LOCAL_ARCHIVE="$BACKUP_ROOT/local_archive"
TEMP_DIR="$BACKUP_ROOT/temp"

# Polished Notification Engine
send_notification() {
    local status_emoji=$1
    local app_name=$2
    local operation=$3 # "BACKUP" or "RESTORE"
    local message=$4
    local host_name=$(hostname)
    
    local full_text="*${status_emoji} ${operation} REPORT: ${app_name}*%0A"
    full_text+="------------------------------------------%0A"
    full_text+="${message}%0A"
    full_text+="------------------------------------------%0A"
    full_text+="📍 *Server:* \`${host_name}\`%0A"
    full_text+="📅 *Time:* \`$(date +'%Y-%m-%d %H:%M:%S')\`"

    curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT_ID}" \
        -d "text=${full_text}" \
        -d "parse_mode=Markdown"
}
