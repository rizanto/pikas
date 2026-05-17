#!/bin/bash
# ==============================================================================
# PROFESSIONAL BACKUP FRAMEWORK: CENTRAL INITIALIZER (ONE-CLICK INSTALLER)
# ==============================================================================
# Run this script on your VPS host system where backup files are placed.
# Usage: bash setup_backup_system.sh

# Beautiful Terminal Banner
echo "=========================================================="
echo "    PROFESSIONAL BACKUP FRAMEWORK INITIALIZER v1.0"
echo "=========================================================="
echo "This installer will establish directories, permissions,"
echo "install dependencies, configure parameters, and set cron schedules."
echo "----------------------------------------------------------"

# ==============================================================================
# STAGE 1: GATHER TARGET PARAMETERS (INTERACTIVE)
# ==============================================================================
read -p "🔹 Enter Application Name (e.g. MANSUR, PIKAS): " APP_NAME
if [ -z "$APP_NAME" ]; then
    echo "❌ Error: Application Name cannot be empty!"
    exit 1
fi
APP_NAME_LC=$(echo "$APP_NAME" | tr '[:upper:]' '[:lower:]')

read -p "🔹 Enter Dokploy Docker Container Name (e.g. mansur-c2l4mb-web-1): " CONTAINER_NAME
if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ Error: Container Name cannot be empty!"
    exit 1
fi

read -p "🔹 Enter Database Type (sqlite/postgres) [default: sqlite]: " DB_TYPE
DB_TYPE=${DB_TYPE:-sqlite}
if [ "$DB_TYPE" != "sqlite" ] && [ "$DB_TYPE" != "postgres" ]; then
    echo "❌ Error: Database Type must be 'sqlite' or 'postgres'!"
    exit 1
fi

if [ "$DB_TYPE" == "sqlite" ]; then
    read -p "🔹 Enter SQLite Database Path inside Container [default: /app/db.sqlite3]: " DB_PATH_INSIDE
    DB_PATH_INSIDE=${DB_PATH_INSIDE:-/app/db.sqlite3}
else
    read -p "🔹 Enter PostgreSQL Database Name inside Container [default: pikas_db]: " DB_PATH_INSIDE
    DB_PATH_INSIDE=${DB_PATH_INSIDE:-pikas_db}
fi

echo "----------------------------------------------------------"

# ==============================================================================
# STAGE 2: INSTALL SYSTEM DEPENDENCIES
# ==============================================================================
echo "Checking VPS system dependencies..."
if ! command -v zip >/dev/null 2>&1; then
    echo "Installing missing package: zip..."
    sudo apt update && sudo apt install zip -y
    echo "✅ zip successfully installed!"
else
    echo "✅ Dependency check passed: zip is already installed."
fi

if ! command -v rclone >/dev/null 2>&1; then
    echo "⚠️ Warning: 'rclone' is not installed or not in PATH."
    echo "Please ensure you configure Rclone and setup Google Drive beforehand!"
fi

# ==============================================================================
# STAGE 3: ESTABLISH DIRECTORIES & OWNERSHIP Permissions
# ==============================================================================
echo "Setting up standardized backup directory tree..."

# Create core system paths
sudo mkdir -p /home/backups/scripts
sudo mkdir -p /home/backups/temp
sudo mkdir -p "/home/backups/local_archive/$APP_NAME_LC"

# Correct ownership recursively to the active VPS user
echo "Applying directory ownership ($USER:$USER)..."
sudo chown -R $USER:$USER /home/backups

# Set standard permissions (755 for directories, allowing reading/execution)
echo "Setting directory access permissions (755)..."
sudo chmod -R 755 /home/backups

# ==============================================================================
# STAGE 4: BOOTSTRAP APP SCRIPTS FROM REPO TEMPLATES
# ==============================================================================
echo "Bootstrapping application backup & restore scripts..."

SCRIPT_SRC_DIR=$(dirname "$0")

# 1. Copy config.sh ONLY if it doesn't already exist to preserve custom tokens
if [ ! -f "/home/backups/scripts/config.sh" ]; then
    if [ -f "$SCRIPT_SRC_DIR/config.sh" ]; then
        cp "$SCRIPT_SRC_DIR/config.sh" /home/backups/scripts/config.sh
        echo "✅ Created central config: /home/backups/scripts/config.sh"
    else
        echo "❌ Error: config.sh template file not found in installer source!"
        exit 1
    fi
else
    echo "ℹ️ Central config already exists. Skipping replacement to preserve credentials."
fi

# 2. Copy and configure backup.sh
if [ -f "$SCRIPT_SRC_DIR/backup.sh" ]; then
    TARGET_BACKUP="/home/backups/scripts/${APP_NAME_LC}_backup.sh"
    cp "$SCRIPT_SRC_DIR/backup.sh" "$TARGET_BACKUP"
    
    # Dynamically inject parameters
    sed -i 's/APP_NAME=".*"/APP_NAME="'"$APP_NAME"'"/g' "$TARGET_BACKUP"
    sed -i 's/CONTAINER_NAME=".*"/CONTAINER_NAME="'"$CONTAINER_NAME"'"/g' "$TARGET_BACKUP"
    sed -i 's/DB_TYPE=".*"/DB_TYPE="'"$DB_TYPE"'"/g' "$TARGET_BACKUP"
    sed -i 's|DB_PATH_INSIDE=".*"|DB_PATH_INSIDE="'"$DB_PATH_INSIDE"'"|g' "$TARGET_BACKUP"
    
    echo "✅ Standardized Backup Script: $TARGET_BACKUP"
else
    echo "❌ Error: backup.sh template file not found in installer source!"
    exit 1
fi

# 3. Copy and configure restore.sh
if [ -f "$SCRIPT_SRC_DIR/restore.sh" ]; then
    TARGET_RESTORE="/home/backups/scripts/${APP_NAME_LC}_restore.sh"
    cp "$SCRIPT_SRC_DIR/restore.sh" "$TARGET_RESTORE"
    
    # Dynamically inject parameters
    sed -i 's/APP_NAME=".*"/APP_NAME="'"$APP_NAME"'"/g' "$TARGET_RESTORE"
    sed -i 's/CONTAINER_NAME=".*"/CONTAINER_NAME="'"$CONTAINER_NAME"'"/g' "$TARGET_RESTORE"
    sed -i 's/DB_TYPE=".*"/DB_TYPE="'"$DB_TYPE"'"/g' "$TARGET_RESTORE"
    sed -i 's|DB_PATH_INSIDE=".*"|DB_PATH_INSIDE="'"$DB_PATH_INSIDE"'"|g' "$TARGET_RESTORE"
    
    echo "✅ Standardized Restore Script: $TARGET_RESTORE"
else
    echo "❌ Error: restore.sh template file not found in installer source!"
    exit 1
fi

# 4. Make all scripts in the directory executable
chmod +x /home/backups/scripts/*.sh

# ==============================================================================
# STAGE 5: AUTOMATE CRON JOB SCHEDULES (INTERACTIVE)
# ==============================================================================
echo "----------------------------------------------------------"
read -p "🔹 Do you want to schedule automatic daily backups at 02:00 AM? (y/n): " CRON_DECISION

if [ "$CRON_DECISION" == "y" ] || [ "$CRON_DECISION" == "Y" ]; then
    CRON_LINE="0 2 * * * /bin/bash /home/backups/scripts/${APP_NAME_LC}_backup.sh >/dev/null 2>&1"
    
    # Check if this script cron already exists in current user crontab
    if crontab -l 2>/dev/null | grep -F "$TARGET_BACKUP" >/dev/null; then
        echo "ℹ️ Backup schedule already exists in crontab."
    else
        # Append safe crontab entries without overwriting existing jobs
        (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
        echo "✅ Added automatic backup to Crontab successfully!"
    fi
fi

# ==============================================================================
# COMPLETION
# ==============================================================================
echo "=========================================================="
echo "    🏁 INITIALIZATION SYSTEM COMPLETED SUCCESSFULLY! 🏁"
echo "=========================================================="
echo "📂 Backup Location: /home/backups/local_archive/$APP_NAME_LC/"
echo "⚙️ Config File    : /home/backups/scripts/config.sh"
echo "🚀 Run Backup now : bash /home/backups/scripts/${APP_NAME_LC}_backup.sh"
echo "⏪ Run Restore now: bash /home/backups/scripts/${APP_NAME_LC}_restore.sh"
echo "=========================================================="
