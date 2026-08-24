# Миграция на MySQL

## Быстрый старт

### 1. Установка MySQL
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install mysql-server

# macOS
brew install mysql
brew services start mysql

# Windows
# Скачайте установщик с https://dev.mysql.com/downloads/installer/
```

### 2. Создание базы данных
```bash
sudo mysql -u root
```

Внутри MySQL:
```sql
CREATE DATABASE transport_cards CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'tc_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON transport_cards.* TO 'tc_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. SQL-скрипт создания таблиц

```sql
USE transport_cards;

-- =====================================================
-- TABLE: card_types
-- =====================================================
CREATE TABLE IF NOT EXISTS card_types (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    print_name VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: owners
-- =====================================================
CREATE TABLE IF NOT EXISTS owners (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    full_name VARCHAR(500) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: applicants
-- =====================================================
CREATE TABLE IF NOT EXISTS applicants (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    full_name VARCHAR(500) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: organizations
-- =====================================================
CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    name VARCHAR(500) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: mfcs
-- =====================================================
CREATE TABLE IF NOT EXISTS mfcs (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    code VARCHAR(50) NOT NULL,
    name VARCHAR(500) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: employees
-- =====================================================
CREATE TABLE IF NOT EXISTS employees (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    full_name VARCHAR(500) NOT NULL,
    login VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    roles JSON DEFAULT '["user"]',
    permissions JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: cards
-- =====================================================
CREATE TABLE IF NOT EXISTS cards (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    card_number VARCHAR(19) UNIQUE NOT NULL,
    card_type_id VARCHAR(36),
    status VARCHAR(50) DEFAULT '',
    owner_id VARCHAR(36),
    applicant_id VARCHAR(36),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (card_type_id) REFERENCES card_types(id) ON DELETE SET NULL,
    FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE SET NULL,
    FOREIGN KEY (applicant_id) REFERENCES applicants(id) ON DELETE SET NULL,
    INDEX idx_cards_number (card_number),
    INDEX idx_cards_status (status),
    INDEX idx_cards_type (card_type_id)
);

-- =====================================================
-- TABLE: documents
-- =====================================================
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    doc_type VARCHAR(50) NOT NULL,
    doc_number VARCHAR(50) NOT NULL,
    doc_date DATE NOT NULL,
    organization_id VARCHAR(36),
    mfc_id VARCHAR(36),
    employee_id VARCHAR(36),
    lines JSON DEFAULT '[]',
    status VARCHAR(20) DEFAULT 'draft',
    created_by VARCHAR(36),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    posted_at DATETIME,
    posted_by VARCHAR(36),
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL,
    FOREIGN KEY (mfc_id) REFERENCES mfcs(id) ON DELETE SET NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL,
    INDEX idx_documents_type (doc_type),
    INDEX idx_documents_date (doc_date),
    INDEX idx_documents_status (status)
);

-- =====================================================
-- TABLE: action_log
-- =====================================================
CREATE TABLE IF NOT EXISTS action_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36),
    action VARCHAR(100) NOT NULL,
    details TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES employees(id) ON DELETE SET NULL,
    INDEX idx_action_log_user (user_id),
    INDEX idx_action_log_timestamp (timestamp)
);

-- =====================================================
-- TABLE: constants
-- =====================================================
CREATE TABLE IF NOT EXISTS constants (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    organization_name VARCHAR(500) DEFAULT 'ООО Транспортные Карты'
);

-- =====================================================
-- TABLE: counters
-- =====================================================
CREATE TABLE IF NOT EXISTS counters (
    prefix VARCHAR(20) PRIMARY KEY,
    value INT DEFAULT 1
);

-- =====================================================
-- DEFAULT DATA
-- =====================================================
INSERT IGNORE INTO employees (id, full_name, login, password, roles, permissions)
VALUES (UUID(), 'Администратор', 'admin', 'admin', '["admin"]', '{}');

INSERT IGNORE INTO constants (organization_name)
VALUES ('ООО Транспортные Карты');

INSERT IGNORE INTO counters (prefix, value)
VALUES ('DOC', 1);
```

### 4. Установка зависимостей
```bash
pip install PyMySQL cryptography python-dotenv
```

### 5. MySQL Storage модуль

Создайте файл `mysql/storage_mysql.py`:

```python
"""MySQL storage layer for transport cards system."""
import os
import uuid
import json
from datetime import datetime
from contextlib import contextmanager

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    raise ImportError("PyMySQL is required. Install: pip install PyMySQL cryptography")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "database": os.environ.get("DB_NAME", "transport_cards"),
    "user": os.environ.get("DB_USER", "tc_user"),
    "password": os.environ.get("DB_PASSWORD", "your_password"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
}

@contextmanager
def get_connection():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

@contextmanager
def get_cursor():
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

class MySQLStorage:
    TABLE_MAP = {
        "cards": "cards", "card_types": "card_types",
        "owners": "owners", "applicants": "applicants",
        "organizations": "organizations", "mfcs": "mfcs",
        "employees": "employees", "documents": "documents",
        "action_log": "action_log", "constants": "constants",
        "counters": "counters",
    }

    def load_all(self, name):
        table = self.TABLE_MAP.get(name, name)
        with get_cursor() as cur:
            cur.execute(f"SELECT * FROM {table} ORDER BY created_at")
            return cur.fetchall()

    def insert(self, name, item):
        table = self.TABLE_MAP.get(name, name)
        if "id" not in item or not item["id"]:
            item["id"] = str(uuid.uuid4())
        item["created_at"] = datetime.now().isoformat()
        columns = list(item.keys())
        values = list(item.values())
        placeholders = ["%s"] * len(values)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        with get_cursor() as cur:
            cur.execute(sql, values)
        return item

    def update(self, name, predicate, updates):
        table = self.TABLE_MAP.get(name, name)
        updates["updated_at"] = datetime.now().isoformat()
        items = self.load_all(name)
        for item in items:
            if predicate(item):
                set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
                sql = f"UPDATE {table} SET {set_clause} WHERE id = %s"
                values = list(updates.values()) + [item["id"]]
                with get_cursor() as cur:
                    cur.execute(sql, values)
                item.update(updates)
                return item
        return None

    def delete(self, name, predicate):
        table = self.TABLE_MAP.get(name, name)
        items = self.load_all(name)
        for item in items:
            if predicate(item):
                with get_cursor() as cur:
                    cur.execute(f"DELETE FROM {table} WHERE id = %s", (item["id"],))

    def get_next_number(self, prefix, name="counters"):
        table = self.TABLE_MAP.get(name, name)
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT value FROM {table} WHERE prefix = %s", (prefix,))
            row = cur.fetchone()
            if row:
                value = row["value"] + 1
                cur.execute(f"UPDATE {table} SET value = %s WHERE prefix = %s", (value, prefix))
            else:
                value = 1
                cur.execute(f"INSERT INTO {table} (prefix, value) VALUES (%s, %s)", (prefix, value))
            conn.commit()
            cur.close()
            return f"{prefix}-{value:06d}"

_mysql_storage = MySQLStorage()

load_all = _mysql_storage.load_all
save_all = lambda name, data: None
find_one = lambda name, pred: next((x for x in load_all(name) if pred(x)), None)
find_many = lambda name, pred: [x for x in load_all(name) if pred(x)]
insert = _mysql_storage.insert
update = _mysql_storage.update
delete = _mysql_storage.delete
get_next_number = _mysql_storage.get_next_number
```

### 6. Переключение на MySQL

В `app.py` замените импорт:
```python
# Для MySQL:
from mysql.storage_mysql import load_all, save_all, insert, update, delete, get_next_number
# Для JSON (по умолчанию):
# from app.storage import load_all, save_all, insert, update, delete, get_next_number
```

Добавьте в начало `app.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

### 7. Запуск
```bash
python app.py
```

## Резервное копирование MySQL

```bash
# Создание бэкапа
mysqldump -u tc_user -p transport_cards > backup.sql

# Восстановление
mysql -u tc_user -p transport_cards < backup.sql
```
