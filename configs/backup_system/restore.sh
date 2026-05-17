#!/bin/bash
# ==============================================================================
# PROFESSIONAL BACKUP FRAMEWORK: GENERIC INTERACTIVE RESTORE TEMPLATE
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
# STEP 1: SCAN LOCAL & CLOUD BACKUPS
# ==============================================================================
DATE=$(date +"%Y%m%d_%H%M")
ARCHIVE_PATH="$LOCAL_ARCHIVE/${APP_NAME,,}"
REMOTE_TARGET="$RCLONE_REMOTE:${APP_NAME}/backups"

echo "=========================================="
echo " SCANNING BACKUP DIRECTORIES FOR $APP_NAME "
echo "=========================================="

echo "Scanning local storage..."
local_files=($(ls -1 "$ARCHIVE_PATH"/${APP_NAME}_*.zip 2>/dev/null | xargs -n 1 basename | sort -r))

echo "Scanning Google Drive storage via Rclone..."
remote_files=($(rclone lsf "$REMOTE_TARGET" --include "${APP_NAME}_*.zip" 2>/dev/null | sort -r))

# ==============================================================================
# STEP 2: BUILD UNIFIED INTERACTIVE MENU
# ==============================================================================
options=()
origins=()

for lf in "${local_files[@]}"; do
    options+=("$lf")
    origins+=("LOCAL")
done

for rf in "${remote_files[@]}"; do
    rf_clean=$(echo "$rf" | tr -d '\r/' | xargs)
    [ -z "$rf_clean" ] && continue
    
    already_local=0
    for lf in "${local_files[@]}"; do
        if [ "$rf_clean" == "$lf" ]; then
            already_local=1
            break
        fi
    done
    
    if [ $already_local -eq 0 ]; then
        options+=("$rf_clean")
        origins+=("CLOUD")
    fi
done

total_options=${#options[@]}

if [ $total_options -eq 0 ]; then
    echo "❌ Error: No backup files found locally or on Google Drive for $APP_NAME!"
    exit 1
fi

echo ""
echo "Select a backup file to restore:"
echo "------------------------------------------"
for i in "${!options[@]}"; do
    num=$((i + 1))
    file="${options[$i]}"
    origin="${origins[$i]}"
    
    if [ "$origin" == "LOCAL" ]; then
        echo -e "[$num] \e[32mLOCAL\e[0m  - $file"
    else
        echo -e "[$num] \e[36mCLOUD\e[0m  - $file \e[90m(Will download automatically)\e[0m"
    fi
done
echo "------------------------------------------"

read -p "Enter selection number (1-$total_options) or 'q' to cancel: " choice

if [ "$choice" == "q" ] || [ "$choice" == "Q" ]; then
    echo "Restore canceled."
    exit 0
fi

if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "$total_options" ]; then
    idx=$((choice - 1))
    selected_file="${options[$idx]}"
    selected_origin="${origins[$idx]}"
else
    echo "❌ Error: Invalid selection!"
    exit 1
fi

# ==============================================================================
# STEP 3: CLOUD RETRIEVAL
# ==============================================================================
if [ "$selected_origin" == "CLOUD" ]; then
    echo ""
    echo "📥 Downloading backup from Google Drive..."
    mkdir -p "$ARCHIVE_PATH"
    
    if rclone copyto "$REMOTE_TARGET/$selected_file" "$ARCHIVE_PATH/$selected_file"; then
        echo "✅ Download successful!"
    else
        echo "❌ Error: Failed to pull file from Google Drive! Check Rclone connection."
        send_notification "❌" "$APP_NAME" "RESTORE" "FAILED: Could not download $selected_file from Cloud."
        exit 1
    fi
fi

# ==============================================================================
# STEP 4: EXTRACTION & INTEGRITY CHECK
# ==============================================================================
RESTORE_WORK_DIR="$TEMP_DIR/${APP_NAME}_restore_$DATE"
mkdir -p "$RESTORE_WORK_DIR"

echo "Extracting backup package..."
if unzip -q "$ARCHIVE_PATH/$selected_file" -d "$RESTORE_WORK_DIR"; then
    echo "Verification: Checking package integrity..."
    if [ "$DB_TYPE" == "sqlite" ]; then
        if [ ! -f "$RESTORE_WORK_DIR/db.sqlite3" ] || [ ! -f "$RESTORE_WORK_DIR/.env" ]; then
            echo "❌ Error: Backup package is incomplete (missing db.sqlite3 or .env)!"
            send_notification "❌" "$APP_NAME" "RESTORE" "FAILED: Backup package $selected_file is corrupted or incomplete."
            rm -rf "$RESTORE_WORK_DIR"
            exit 1
        fi
    elif [ "$DB_TYPE" == "postgres" ]; then
        if [ ! -f "$RESTORE_WORK_DIR/db_dump.sql" ] || [ ! -f "$RESTORE_WORK_DIR/.env" ]; then
            echo "❌ Error: Backup package is incomplete (missing db_dump.sql or .env)!"
            send_notification "❌" "$APP_NAME" "RESTORE" "FAILED: Backup package $selected_file is corrupted or incomplete."
            rm -rf "$RESTORE_WORK_DIR"
            exit 1
        fi
    fi
    echo "✅ Verification successful!"
else
    echo "❌ Error: Extraction failed!"
    rm -rf "$RESTORE_WORK_DIR"
    exit 1
fi

# ==============================================================================
# STEP 5: FINAL CONFIRMATION
# ==============================================================================
echo ""
echo "⚠️  CRITICAL WARNING ⚠️"
echo "You are about to restore $APP_NAME to version: $selected_file"
echo "This will OVERWRITE the current active database and .env configuration!"
echo "------------------------------------------"
read -p "Are you absolutely sure you want to proceed? (Type 'yes' to confirm): " final_confirm

if [ "$final_confirm" != "yes" ]; then
    echo "Restore canceled."
    rm -rf "$RESTORE_WORK_DIR"
    exit 0
fi

# ==============================================================================
# STEP 6: EXECUTE OVERWRITE & CONTAINER REBOOT
# ==============================================================================
echo "Restoring state into Docker container ($CONTAINER_NAME)..."
docker cp "$RESTORE_WORK_DIR/.env" "$CONTAINER_NAME:$ENV_PATH_INSIDE"

if [ "$DB_TYPE" == "sqlite" ]; then
    docker cp "$RESTORE_WORK_DIR/db.sqlite3" "$CONTAINER_NAME:$DB_PATH_INSIDE"
elif [ "$DB_TYPE" == "postgres" ]; then
    echo "Restoring PostgreSQL database dump..."
    DATABASE_URL=$(grep DATABASE_URL "$RESTORE_WORK_DIR/.env" | cut -d'=' -f2- | tr -d '\r')
    DOCKER_NETWORK=$(docker inspect $CONTAINER_NAME --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -n 1)
    echo "Wiping target database public schema to prevent conflicts..."
    docker run --rm --network "$DOCKER_NETWORK" postgres:alpine psql "$DATABASE_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    echo "Running psql restore using temporary postgres container on network $DOCKER_NETWORK..."
    docker run --rm -i --network "$DOCKER_NETWORK" postgres:alpine psql "$DATABASE_URL" < "$RESTORE_WORK_DIR/db_dump.sql"
fi

echo "Rebooting container..."
if docker restart "$CONTAINER_NAME" > /dev/null 2>&1; then
    echo "✅ Container successfully rebooted!"
    MSG="✅ *Status:* SUCCESS%0A📂 *Restored From:* \`${selected_file}\` (%0A📍 *Origin:* \`${selected_origin}\`)%0A🚀 *Status:* Application is live and healthy."
    send_notification "✅" "$APP_NAME" "RESTORE" "$MSG"
    echo "Restore process completed successfully!"
else
    echo "❌ Warning: Container failed to restart."
    MSG="⚠️ *Status:* WARNING%0A📂 *Restored From:* \`${selected_file}\`%0A⚠️ *Error:* Files restored, but container reboot failed."
    send_notification "⚠️" "$APP_NAME" "RESTORE" "$MSG"
fi

# ==============================================================================
# STEP 7: CLEANUP
# ==============================================================================
rm -rf "$RESTORE_WORK_DIR"
