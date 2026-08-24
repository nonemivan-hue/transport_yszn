# Миграция на PostgreSQL

## Быстрый старт

### 1. Установка PostgreSQL
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# macOS
brew install postgresql
brew services start postgresql

# Windows
# Скачайте установщик с https://www.postgresql.org/download/windows/
```

### 2. Создание базы данных
```bash
sudo -u postgres psql
```

Внутри psql:
```sql
CREATE DATABASE transport_cards WITH ENCODING = 'UTF8';
CREATE USER tc_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE transport_cards TO tc_user;
\q
```

### 3. Инициализация таблиц
```bash
cd transport_cards
psql -U tc_user -d transport_cards -f postgres/init.sql
```

### 4. Установка зависимостей
```bash
pip install psycopg2-binary python-dotenv
```

### 5. Настройка подключения
Скопируйте файл конфигурации:
```bash
cp postgres/.env.example .env
```

Отредактируйте `.env`:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=transport_cards
DB_USER=tc_user
DB_PASSWORD=your_password
```

### 6. Переключение на PostgreSQL

В файле `app.py` замените импорт storage:

**Было:**
```python
from app.storage import load_all, save_all, insert, update, delete, get_next_number
```

**Стало:**
```python
# Для PostgreSQL:
from postgres.storage_pg import load_all, save_all, insert, update, delete, get_next_number
# Для JSON (по умолчанию):
# from app.storage import load_all, save_all, insert, update, delete, get_next_number
```

Также в `app.py` добавьте загрузку .env в начало файла:
```python
from dotenv import load_dotenv
load_dotenv()
```

### 7. Запуск
```bash
python app.py
```

## Структура таблиц

### card_types
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| name | VARCHAR(255) | Вид карты |
| print_name | VARCHAR(255) | Наименование для печати |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### owners
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| full_name | VARCHAR(500) | ФИО владельца |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### applicants
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| full_name | VARCHAR(500) | ФИО заявителя |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### organizations
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| name | VARCHAR(500) | Наименование организации |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### mfcs
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| code | VARCHAR(50) | Код МФЦ |
| name | VARCHAR(500) | Наименование МФЦ |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### employees
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| full_name | VARCHAR(500) | ФИО сотрудника |
| login | VARCHAR(100) | Логин (уникальный) |
| password | VARCHAR(255) | Пароль |
| roles | JSONB | Роли ["admin", "user"] |
| permissions | JSONB | Права доступа |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### cards
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| card_number | VARCHAR(19) | Номер карты (уникальный) |
| card_type_id | UUID | Ссылка на card_types |
| status | VARCHAR(50) | Статус карты |
| owner_id | UUID | Ссылка на owners |
| applicant_id | UUID | Ссылка на applicants |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### documents
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| doc_type | VARCHAR(50) | Тип документа |
| doc_number | VARCHAR(50) | Номер документа |
| doc_date | DATE | Дата документа |
| organization_id | UUID | Ссылка на organizations |
| mfc_id | UUID | Ссылка на mfcs |
| employee_id | UUID | Ссылка на employees |
| lines | JSONB | Табличная часть |
| status | VARCHAR(20) | Статус (draft/posted) |
| created_by | UUID | Кто создал |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |
| posted_at | TIMESTAMP | Дата проведения |
| posted_by | UUID | Кто провел |

### action_log
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | Первичный ключ |
| user_id | UUID | Ссылка на employees |
| action | VARCHAR(100) | Действие |
| details | TEXT | Детали |
| timestamp | TIMESTAMP | Время действия |

### constants
| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| organization_name | VARCHAR(500) | Название организации |

### counters
| Поле | Тип | Описание |
|------|-----|----------|
| prefix | VARCHAR(20) | Префикс номера |
| value | INTEGER | Текущее значение |

## Миграция данных из JSON

Если у вас уже есть данные в JSON:

```python
import json
import psycopg2
from psycopg2.extras import execute_values

# Подключение к PostgreSQL
conn = psycopg2.connect(
    host="localhost", database="transport_cards",
    user="tc_user", password="your_password"
)
cur = conn.cursor()

# Загрузка JSON
with open('data/cards.json', 'r', encoding='utf-8') as f:
    cards = json.load(f)

# Вставка данных
columns = cards[0].keys()
query = f"INSERT INTO cards ({','.join(columns)}) VALUES %s"
values = [[item[col] for col in columns] for item in cards]
execute_values(cur, query, values)
conn.commit()
```

## Резервное копирование PostgreSQL

```bash
# Создание бэкапа
pg_dump -U tc_user -d transport_cards > backup.sql

# Восстановление
psql -U tc_user -d transport_cards < backup.sql
```
