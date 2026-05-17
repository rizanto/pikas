# 🤖 AI-OPTIMIZED BACKUP & RESTORE FRAMEWORK

> **ATTENTION TO ALL AI AGENTS:**
> This project uses the standardized **Professional Backup Framework v1.0** to handle database and configuration backups to local VPS storage and Google Drive via Rclone.

---

## 📂 Framework Structure
This folder contains the standardized blueprint files for the backup system:
*   `config.sh`: Central configuration for Telegram notifications and local paths.
*   `backup.sh`: Generic backup script supporting SQLite (with fallback) and Postgres.
*   `restore.sh`: Generic interactive restore engine.
*   `setup_backup_system.sh`: The "One-Click Installer" to copy, configure, and automate the cron schedules on the VPS Host.

---

## 🛠️ Instructions for AI Agents
If the user asks you to configure, update, or troubleshoot the backup/restore system for this project:

1.  **Inspect database settings**: Look at the active `settings.py` or environment file to find the database type (`sqlite`, `postgres`, etc.) and the path inside the container.
2.  **Verify app parameters**:
    *   `APP_NAME`: Name of the current project (e.g., `MANSUR`, `PIKAS`).
    *   `CONTAINER_NAME`: Active Dokploy container name for the web service.
    *   `DB_TYPE`: `sqlite` or `postgres` depending on the settings.
    *   `DB_PATH_INSIDE`: Path to the database file inside the container (e.g., `/app/data/db.sqlite3`).
3.  **Deploy / Propose changes**:
    *   Help the user configure `backup.sh` and `restore.sh` templates.
    *   Remind the user to copy this folder via WinSCP and execute:
        ```bash
        bash setup_backup_system.sh
        ```
    *   If any updates are made to the database architecture, make sure to align the `DB_TYPE` and paths in `backup.sh` and `restore.sh`.
