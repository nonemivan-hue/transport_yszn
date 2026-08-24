"""
JSON-based storage layer for transport cards system.
Designed to be easily replaceable with SQL (MySQL/PostgreSQL) later.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def _get_path(name):
    return DATA_DIR / f"{name}.json"


def load_all(name):
    path = _get_path(name)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_all(name, data):
    path = _get_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_one(name, predicate):
    for item in load_all(name):
        if predicate(item):
            return item
    return None


def find_many(name, predicate):
    return [item for item in load_all(name) if predicate(item)]


def insert(name, item):
    data = load_all(name)
    if "id" not in item or not item["id"]:
        item["id"] = str(uuid.uuid4())
    item["created_at"] = datetime.now().isoformat()
    data.append(item)
    save_all(name, data)
    return item


def update(name, predicate, updates):
    data = load_all(name)
    for item in data:
        if predicate(item):
            item.update(updates)
            item["updated_at"] = datetime.now().isoformat()
            save_all(name, data)
            return item
    return None


def delete(name, predicate):
    data = load_all(name)
    new_data = [item for item in data if not predicate(item)]
    save_all(name, new_data)


def get_next_number(prefix, name="counters"):
    """Get next sequential document number."""
    counters = load_all(name)
    counter = next((c for c in counters if c.get("prefix") == prefix), None)
    if counter is None:
        counter = {"prefix": prefix, "value": 1}
        counters.append(counter)
    else:
        counter["value"] += 1
    save_all(name, counters)
    return f"{prefix}-{counter['value']:03d}"


# Initialize default data
def init_defaults():
    # Default admin user
    employees = load_all("employees")
    if not employees:
        insert("employees", {
            "id": str(uuid.uuid4()),
            "full_name": "Администратор",
            "login": "admin",
            "password": "admin",  # In production, use hashed passwords
            "roles": ["admin"],
            "permissions": {}
        })

    # Default constants
    constants = load_all("constants")
    if not constants:
        insert("constants", {
            "id": str(uuid.uuid4()),
            "organization_name": "ООО Транспортные Карты"
        })


init_defaults()
