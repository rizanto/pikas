#!/bin/bash
# ==============================================================================
# PROFESSIONAL BACKUP FRAMEWORK: GENERIC BACKUP TEMPLATE
# ==============================================================================
# Reuses global config paths and Telegram notification integration.
source /home/backups/scripts/config.sh

# ==============================================================================
# STEP 0: APP PARAMETERS (Automatically populated by setup_backup_system.sh)
# ==============================================================================
APP_NAME="TEMPLATE_APP"
CONTAINER_NAME="TEMPLATE_CONTAINER"
DB_TYPE="sqlite"
DB_PATH_INSIDE="/app/db.sqlite3"
ENV_PATH_INSIDE="/app/.env"

# ==============================================================================
# STEP 1: INITIALIZATION
# ==============================================================================
DATE=$(date +"%Y%m%d_%H%M")
WORK_DIR="$TEMP_DIR/${APP_NAME}_backup_$DATE"
ARCHIVE_PATH="$LOCAL_ARCHIVE/${APP_NAME,,}"
ZIP_NAME="${APP_NAME}_${DATE}.zip"
ZIP_FULL_PATH="$ARCHIVE_PATH/$ZIP_NAME"

mkdir -p "$WORK_DIR" "$ARCHIVE_PATH"
echo "Starting backup process for $APP_NAME..."

# ==============================================================================
# STEP 2: DATABASE EXTRACTION
# ==============================================================================
case $DB_TYPE in
  sqlite)
    if docker exec $CONTAINER_NAME which sqlite3 > /dev/null 2>&1; then
        echo "Using sqlite3 .backup method (Optimal consistency)..."
        docker exec $CONTAINER_NAME sqlite3 $DB_PATH_INSIDE ".backup '/tmp/db_dump.sqlite3'"
        docker cp $CONTAINER_NAME:/tmp/db_dump.sqlite3 "$WORK_DIR/db.sqlite3"
        docker exec $CONTAINER_NAME rm /tmp/db_dump.sqlite3
    else
        echo "sqlite3 command not found inside container. Falling back to direct hot-copy..."
        docker cp $CONTAINER_NAME:$DB_PATH_INSIDE "$WORK_DIR/db.sqlite3"
    fi
    ;;
  postgres)
    echo "Exporting PostgreSQL database..."
    DATABASE_URL=$(docker exec $CONTAINER_NAME env | grep DATABASE_URL | cut -d'=' -f2- | tr -d '\r')
    if [ -z "$DATABASE_URL" ]; then
        DATABASE_URL=$(docker exec $CONTAINER_NAME cat $ENV_PATH_INSIDE | grep DATABASE_URL | cut -d'=' -f2- | tr -d '\r')
    fi
    DOCKER_NETWORK=$(docker inspect $CONTAINER_NAME --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -n 1)
    echo "Running pg_dump using temporary postgres container on network $DOCKER_NETWORK..."
    docker run --rm --network "$DOCKER_NETWORK" postgres:alpine pg_dump "$DATABASE_URL" > "$WORK_DIR/db_dump.sql"
    ;;
esac

echo "Copying environment file..."
if docker exec $CONTAINER_NAME test -f $ENV_PATH_INSIDE; then
    docker cp $CONTAINER_NAME:$ENV_PATH_INSIDE "$WORK_DIR/.env"
else
    echo "ℹ️ .env file not found at $ENV_PATH_INSIDE. Reconstructing .env from active container environments..."
    docker exec $CONTAINER_NAME env | grep -E "^(SECRET_KEY|DATABASE_URL|SATKER_NAME|ALLOWED_HOSTS|CSRF_TRUSTED_ORIGINS|DEBUG|GOOGLE_SERVICE_ACCOUNT_JSON|DJANGO_SUPERUSER_)" > "$WORK_DIR/.env"
fi

# ==============================================================================
# STEP 3: COMPRESSION
# ==============================================================================
if command -v zip >/dev/null 2>&1; then
    echo "Compressing backup package..."
    cd "$WORK_DIR" && zip -rj "$ZIP_FULL_PATH" . > /dev/null
    cd - > /dev/null
    FILE_SIZE=$(du -h "$ZIP_FULL_PATH" | cut -f1)
else
    echo "Error: 'zip' utility is not installed on the VPS host system!"
    send_notification "❌" "$APP_NAME" "BACKUP" "FAILED: 'zip' command not found on Host VPS. Run: sudo apt install zip"
    rm -rf "$WORK_DIR"
    exit 1
fi

# ==============================================================================
# STEP 4: CLOUD UPLOAD & NOTIFICATION
# ==============================================================================
REMOTE_TARGET="$RCLONE_REMOTE:${APP_NAME}/backups"

echo "Uploading package to Google Drive..."
if rclone copy "$ZIP_FULL_PATH" "$REMOTE_TARGET"; then
    MSG="✅ *Status:* SUCCESS%0A📂 *File:* \`${ZIP_NAME}\`%0A📦 *Size:* \`${FILE_SIZE}\`%0A☁️ *Remote Target:* \`${REMOTE_TARGET}\`"
    send_notification "✅" "$APP_NAME" "BACKUP" "$MSG"
    echo "Backup completed successfully!"
else
    MSG="❌ *Status:* FAILED%0A⚠️ *Error:* Rclone upload failed!"
    send_notification "❌" "$APP_NAME" "BACKUP" "$MSG"
    echo "Backup upload failed."
fi

# ==============================================================================
# STEP 5: RETENTION & CLEANUP
# ==============================================================================
echo "Enforcing backup retention policies..."
find "$ARCHIVE_PATH" -type f -mtime +3 -delete
rclone delete "$REMOTE_TARGET" --min-age 7d --include "${APP_NAME}_*.zip" --rmdirs
rm -rf "$WORK_DIR"
echo "Cleanup completed."
