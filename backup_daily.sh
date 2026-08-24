#!/bin/bash
# Ежедневное резервное копирование базы данных
# Скрипт для настройки в cron

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
BACKUP_DIR="${SCRIPT_DIR}/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_daily_${TIMESTAMP}.zip"

# Создаем директорию для резервных копий, если не существует
mkdir -p "${BACKUP_DIR}"

# Создаем резервную копию
cd "${SCRIPT_DIR}"
zip -r "${BACKUP_DIR}/${BACKUP_NAME}" data/

# Удаляем старые резервные копии (старше 30 дней)
find "${BACKUP_DIR}" -name "backup_daily_*.zip" -mtime +30 -delete

echo "Резервная копия создана: ${BACKUP_NAME}"
