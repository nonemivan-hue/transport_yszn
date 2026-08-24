"""
Data models and business logic for transport cards system.
"""
from app.storage import (
    load_all, save_all, find_one, find_many, insert, update, delete, get_next_number
)
from datetime import datetime


# ============== CONSTANTS ==============
CARD_STATUSES = {
    "ready_to_print": "Готова к печати",
    "ready_to_issue": "Готова к выдаче",
    "issued": "Выдана",
    "defect": "Брак",
    "transferred_region": "Передана в другой регион",
    "": ""
}

DOCUMENT_TYPES = {
    "receipt": "Прием карт",
    "defect": "Брак",
    "print": "Печать карт",
    "issue": "Выдача карт",
    "transfer_mfc": "Передача в МФЦ",
    "transfer_region": "Передача в другой регион",
    "return_mfc": "Возврат из МФЦ"
}

REPORT_STATUSES = [
    "ready_to_print",
    "ready_to_issue", 
    "issued",
    "defect",
    "transferred_region"
]


# ============== HELPERS ==============
def now_iso():
    return datetime.now().isoformat()


def log_action(user_id, action, details=""):
    insert("action_log", {
        "user_id": user_id,
        "action": action,
        "details": details,
        "timestamp": now_iso()
    })


# ============== CARD REFERENCE ==============
def get_cards(filters=None, sort_by=None):
    cards = load_all("cards")
    if filters:
        for key, value in filters.items():
            if value:
                cards = [c for c in cards if str(c.get(key, "")).lower().find(str(value).lower()) >= 0]
    if sort_by:
        cards = sorted(cards, key=lambda x: x.get(sort_by, ""))
    return cards


def get_card_by_number(number):
    return find_one("cards", lambda c: c.get("card_number") == number)


def create_or_update_card(card_data, user_id=None):
    existing = get_card_by_number(card_data.get("card_number"))
    if existing:
        updates = {k: v for k, v in card_data.items() if k not in ["id", "created_at"]}
        updates["updated_at"] = now_iso()
        result = update("cards", lambda c: c.get("id") == existing["id"], updates)
        if user_id:
            log_action(user_id, "UPDATE_CARD", f"Updated card {card_data.get('card_number')}")
        return result
    else:
        result = insert("cards", card_data)
        if user_id:
            log_action(user_id, "CREATE_CARD", f"Created card {card_data.get('card_number')}")
        return result


# ============== CARD TYPES ==============
def get_card_types():
    return load_all("card_types")


def get_card_type_by_id(ct_id):
    return find_one("card_types", lambda c: c.get("id") == ct_id)


def get_card_type_by_name(name):
    return find_one("card_types", lambda c: c.get("name") == name)


# ============== OWNERS ==============
def get_owners():
    return load_all("owners")


def get_owner_by_id(o_id):
    return find_one("owners", lambda o: o.get("id") == o_id)


def get_owner_by_name(full_name):
    return find_one("owners", lambda o: o.get("full_name") == full_name)


def create_owner_if_not_exists(full_name, user_id=None):
    existing = get_owner_by_name(full_name)
    if existing:
        return existing
    result = insert("owners", {"full_name": full_name})
    if user_id:
        log_action(user_id, "CREATE_OWNER", f"Created owner {full_name}")
    return result


# ============== APPLICANTS ==============
def get_applicants():
    return load_all("applicants")


def get_applicant_by_id(a_id):
    return find_one("applicants", lambda a: a.get("id") == a_id)


def get_applicant_by_name(full_name):
    return find_one("applicants", lambda a: a.get("full_name") == full_name)


def create_applicant_if_not_exists(full_name, user_id=None):
    existing = get_applicant_by_name(full_name)
    if existing:
        return existing
    result = insert("applicants", {"full_name": full_name})
    if user_id:
        log_action(user_id, "CREATE_APPLICANT", f"Created applicant {full_name}")
    return result


# ============== ORGANIZATIONS ==============
def get_organizations():
    return load_all("organizations")


def get_organization_by_id(org_id):
    return find_one("organizations", lambda o: o.get("id") == org_id)


# ============== MFC ==============
def get_mfcs():
    return load_all("mfcs")


def get_mfc_by_id(mfc_id):
    return find_one("mfcs", lambda m: m.get("id") == mfc_id)


# ============== EMPLOYEES ==============
def get_employees():
    return load_all("employees")


def get_employee_by_id(e_id):
    return find_one("employees", lambda e: e.get("id") == e_id)


def get_employee_by_login(login):
    return find_one("employees", lambda e: e.get("login") == login)


def check_permission(employee, resource, level="view"):
    """Check if employee has permission for resource at given level."""
    if "admin" in employee.get("roles", []):
        return True
    perms = employee.get("permissions", {})
    resource_perm = perms.get(resource, "")
    if level == "view":
        return resource_perm in ["view", "edit"]
    if level == "edit":
        return resource_perm == "edit"
    return False


# ============== DOCUMENTS ==============
def get_documents(doc_type=None):
    docs = load_all("documents")
    if doc_type:
        docs = [d for d in docs if d.get("doc_type") == doc_type]
    return sorted(docs, key=lambda x: x.get("doc_date", ""), reverse=True)


def get_document_by_id(doc_id):
    return find_one("documents", lambda d: d.get("id") == doc_id)


def delete_document(doc_id, user_id=None):
    doc = get_document_by_id(doc_id)
    if not doc:
        return False
    # Revert card statuses if needed
    if doc.get("status") == "posted":
        for line in doc.get("lines", []):
            card = get_card_by_number(line.get("card_number"))
            if card:
                # Simple revert - set to previous status or empty
                update("cards", lambda c: c.get("id") == card["id"],
                       {"status": "", "updated_at": now_iso()})
    delete("documents", lambda d: d.get("id") == doc_id)
    if user_id:
        log_action(user_id, "DELETE_DOC", f"Deleted document {doc.get('doc_number')}")
    return True


def post_document(doc_id, user_id=None):
    """Post a document - apply business logic and update card statuses."""
    doc = get_document_by_id(doc_id)
    if not doc or doc.get("status") == "posted":
        return False, "Документ не найден или уже проведен"

    errors = []
    doc_type = doc.get("doc_type")
    lines = doc.get("lines", [])

    for idx, line in enumerate(lines, 1):
        card_number = line.get("card_number")
        card = get_card_by_number(card_number)

        if doc_type == "receipt":
            # Прием карт
            if card and card.get("status") not in ["", "transferred_region"]:
                errors.append(f"Строка {idx}: Карта {card_number} уже существует со статусом '{CARD_STATUSES.get(card.get('status'), card.get('status'))}'")
            else:
                card_data = {
                    "card_number": card_number,
                    "card_type_id": line.get("card_type_id"),
                    "status": "ready_to_print",
                    "owner_id": "",
                    "applicant_id": ""
                }
                create_or_update_card(card_data, user_id)

        elif doc_type == "defect":
            # Брак
            if not card:
                errors.append(f"Строка {idx}: Карта {card_number} не зарегистрирована в системе")
            elif card.get("status") not in ["ready_to_print", "ready_to_issue"]:
                errors.append(f"Строка {idx}: Карта {card_number} имеет статус '{CARD_STATUSES.get(card.get('status'), card.get('status'))}'")
            else:
                update("cards", lambda c: c.get("id") == card["id"],
                       {"status": "defect", "updated_at": now_iso()})

        elif doc_type == "print":
            # Печать карт
            if not card:
                errors.append(f"Строка {idx}: Карта {card_number} не зарегистрирована в системе")
            elif card.get("status") != "ready_to_print":
                errors.append(f"Строка {idx}: Карта {card_number} имеет статус '{CARD_STATUSES.get(card.get('status'), card.get('status'))}'")
            else:
                # Create/update owner
                owner = create_owner_if_not_exists(line.get("owner_name", ""), user_id) if line.get("owner_name") else None
                updates = {
                    "status": "ready_to_issue",
                    "owner_id": owner["id"] if owner else card.get("owner_id", ""),
                    "updated_at": now_iso()
                }
                update("cards", lambda c: c.get("id") == card["id"], updates)

        elif doc_type == "issue":
            # Выдача карт
            if not card:
                errors.append(f"Строка {idx}: Карта {card_number} не числится в системе")
            elif card.get("status") != "ready_to_issue":
                errors.append(f"Строка {idx}: Карта {card_number} имеет статус '{CARD_STATUSES.get(card.get('status'), card.get('status'))}'")
            else:
                # Handle applicant
                card_type = get_card_type_by_id(card.get("card_type_id"))
                ct_name = card_type.get("name", "") if card_type else ""
                if ct_name == "Многодетные семьи" and line.get("applicant_name"):
                    applicant = create_applicant_if_not_exists(line.get("applicant_name"), user_id)
                    applicant_id = applicant["id"]
                else:
                    applicant_id = card.get("owner_id", "")

                update("cards", lambda c: c.get("id") == card["id"],
                       {"status": "issued", "applicant_id": applicant_id, "updated_at": now_iso()})

        elif doc_type == "transfer_mfc":
            # Передача в МФЦ
            if not card:
                errors.append(f"Строка {idx}: Карта {card_number} не числится в системе")
            elif card.get("status") != "ready_to_issue":
                errors.append(f"Строка {idx}: Карта {card_number} имеет статус '{CARD_STATUSES.get(card.get('status'), card.get('status'))}'")
            else:
                update("cards", lambda c: c.get("id") == card["id"],
                       {"status": "issued", "updated_at": now_iso()})

        elif doc_type == "transfer_region":
            # Передача в другой регион
            if not card:
                errors.append(f"Строка {idx}: Карта {card_number} не числится в системе")
            elif card.get("status") != "ready_to_print":
                errors.append(f"Строка {idx}: Карта {card_number} имеет статус '{CARD_STATUSES.get(card.get('status'), card.get('status'))}'")
            else:
                update("cards", lambda c: c.get("id") == card["id"],
                       {"status": "transferred_region", "updated_at": now_iso()})

        elif doc_type == "return_mfc":
            # Возврат из МФЦ
            if not card:
                errors.append(f"Строка {idx}: Карта {card_number} не числится в системе")
            elif card.get("status") != "issued":
                errors.append(f"Строка {idx}: Карта {card_number} имеет статус '{CARD_STATUSES.get(card.get('status'), card.get('status'))}'")
            else:
                update("cards", lambda c: c.get("id") == card["id"],
                       {"status": "ready_to_issue", "updated_at": now_iso()})

    if errors:
        return False, "; ".join(errors)

    # Mark document as posted
    update("documents", lambda d: d.get("id") == doc_id,
           {"status": "posted", "posted_at": now_iso(), "posted_by": user_id})

    if user_id:
        log_action(user_id, "POST_DOC", f"Posted document {doc.get('doc_number')} ({doc_type})")

    return True, "Документ проведен успешно"


# ============== REPORTS ==============
def get_stock_report():
    """Report: stock of cards by type (ready_to_print and ready_to_issue)."""
    cards = load_all("cards")
    card_types = get_card_types()
    # Initialize counters for all card types
    result = {}
    for ct in card_types:
        result[ct["id"]] = {
            "card_type_name": ct.get("name", "Не указан"),
            "ready_to_print": 0,
            "ready_to_issue": 0
        }
    # Count cards
    for card in cards:
        ct_id = card.get("card_type_id", "")
        status = card.get("status", "")
        if ct_id in result and status in ("ready_to_print", "ready_to_issue"):
            result[ct_id][status] += 1
    # Build list, filter out rows with zero counts
    report = []
    for ct_id in sorted(result.keys(), key=lambda k: result[k]["card_type_name"]):
        row = result[ct_id]
        report.append(row)
    return report


def get_cards_report_as_of(date_str):
    """Report cards status as of specific date."""
    # For JSON storage, we use current state (simplified)
    # In SQL version, this would query historical state
    cards = load_all("cards")
    result = {}
    for card in cards:
        ct_id = card.get("card_type_id", "")
        status = card.get("status", "")
        key = (ct_id, status)
        result[key] = result.get(key, 0) + 1

    # Format for display
    report = []
    for (ct_id, status), count in result.items():
        ct = get_card_type_by_id(ct_id)
        report.append({
            "card_type_name": ct.get("name", "Не указан") if ct else "Не указан",
            "status": CARD_STATUSES.get(status, status),
            "status_code": status,
            "count": count
        })
    return report


def get_period_report(start_date, end_date):
    """Report for period: rows = card types, cols = print | issue+transfer_mfc."""
    docs = load_all("documents")

    # Collect print docs
    print_docs = [d for d in docs
                  if d.get("status") == "posted"
                  and start_date <= d.get("doc_date", "") <= end_date
                  and d.get("doc_type") == "print"]

    # Collect issue + transfer_mfc docs
    issue_docs = [d for d in docs
                  if d.get("status") == "posted"
                  and start_date <= d.get("doc_date", "") <= end_date
                  and d.get("doc_type") in ["issue", "transfer_mfc"]]

    # Group by card type
    print_counts = {}
    issue_counts = {}

    for doc in print_docs:
        for line in doc.get("lines", []):
            card = get_card_by_number(line.get("card_number"))
            if card:
                ct_id = card.get("card_type_id", "")
                print_counts[ct_id] = print_counts.get(ct_id, 0) + 1

    for doc in issue_docs:
        for line in doc.get("lines", []):
            card = get_card_by_number(line.get("card_number"))
            if card:
                ct_id = card.get("card_type_id", "")
                issue_counts[ct_id] = issue_counts.get(ct_id, 0) + 1

    # Build report: all card types that appear in either column
    all_ct_ids = set(list(print_counts.keys()) + list(issue_counts.keys()))
    report = []
    for ct_id in sorted(all_ct_ids):
        ct = get_card_type_by_id(ct_id)
        report.append({
            "card_type_name": ct.get("report_name", "") or ct.get("name", "Не указан") if ct else "Не указан",
            "print_count": print_counts.get(ct_id, 0),
            "issue_count": issue_counts.get(ct_id, 0)
        })
    return report


def get_period_report_detail(start_date, end_date):
    """Detailed period report: card numbers grouped by card type for print and issue docs."""
    docs = load_all("documents")

    print_docs = [d for d in docs
                  if d.get("status") == "posted"
                  and start_date <= d.get("doc_date", "") <= end_date
                  and d.get("doc_type") == "print"]

    issue_docs = [d for d in docs
                  if d.get("status") == "posted"
                  and start_date <= d.get("doc_date", "") <= end_date
                  and d.get("doc_type") in ["issue", "transfer_mfc"]]

    # Group card numbers by card type
    print_numbers = {}
    issue_numbers = {}

    for doc in print_docs:
        for line in doc.get("lines", []):
            card = get_card_by_number(line.get("card_number"))
            if card:
                ct_id = card.get("card_type_id", "")
                if ct_id not in print_numbers:
                    print_numbers[ct_id] = []
                print_numbers[ct_id].append(card.get("card_number", ""))

    for doc in issue_docs:
        for line in doc.get("lines", []):
            card = get_card_by_number(line.get("card_number"))
            if card:
                ct_id = card.get("card_type_id", "")
                if ct_id not in issue_numbers:
                    issue_numbers[ct_id] = []
                issue_numbers[ct_id].append(card.get("card_number", ""))

    # Build report with all card types
    all_ct_ids = set(list(print_numbers.keys()) + list(issue_numbers.keys()))
    card_types = get_card_types()
    ct_map = {ct["id"]: ct for ct in card_types}

    report = []
    for ct_id in sorted(all_ct_ids, key=lambda k: ct_map.get(k, {}).get("name", "")):
        ct = ct_map.get(ct_id)
        report.append({
            "card_type_name": ct.get("name", "Не указан") if ct else "Не указан",
            "print_name": ct.get("print_name", ct.get("name", "")) if ct else "",
            "print_numbers": sorted(print_numbers.get(ct_id, [])),
            "issue_numbers": sorted(issue_numbers.get(ct_id, []))
        })
    return report


def get_edo_report(start_date, end_date):
    """Report for EDO (print and defect documents)."""
    docs = load_all("documents")
    filtered = [d for d in docs
                if d.get("status") == "posted"
                and start_date <= d.get("doc_date", "") <= end_date
                and d.get("doc_type") in ["print", "defect"]]

    result = {}
    for doc in filtered:
        for line in doc.get("lines", []):
            card = get_card_by_number(line.get("card_number"))
            if card:
                ct_id = card.get("card_type_id", "")
                if ct_id not in result:
                    result[ct_id] = []
                result[ct_id].append(card.get("card_number"))

    report = []
    for ct_id, numbers in result.items():
        ct = get_card_type_by_id(ct_id)
        report.append({
            "card_type_name": ct.get("name", "Не указан") if ct else "Не указан",
            "numbers": ", ".join(sorted(numbers))
        })
    return report


def get_summary_report(start_date, end_date):
    """Summary report for period (print and defect)."""
    docs = load_all("documents")
    filtered = [d for d in docs
                if d.get("status") == "posted"
                and start_date <= d.get("doc_date", "") <= end_date
                and d.get("doc_type") in ["print", "defect"]]

    result = {}
    for doc in filtered:
        for line in doc.get("lines", []):
            card = get_card_by_number(line.get("card_number"))
            if card:
                ct_id = card.get("card_type_id", "")
                if ct_id not in result:
                    result[ct_id] = []
                result[ct_id].append(card.get("card_number"))

    report = []
    for ct_id, numbers in result.items():
        ct = get_card_type_by_id(ct_id)
        report.append({
            "card_type_name": ct.get("report_name", "") or ct.get("name", "Не указан") if ct else "Не указан",
            "print_name": ct.get("print_name", ct.get("name", "")) if ct else "",
            "numbers": sorted(numbers)
        })
    return report


def get_cards_as_of_report(as_of_date=None):
    """
    Report: карты на число.
    Rows = card types, columns = statuses, cells = count.
    Uses report_name from card_types.
    """
    cards = load_all("cards")
    card_types = get_card_types()
    
    # Initialize matrix: {ct_id: {status: count}}
    result = {}
    for ct in card_types:
        ct_id = ct["id"]
        result[ct_id] = {"card_type_name": ct.get("report_name", "") or ct.get("name", "Не указан"), "total": 0}
        for status in REPORT_STATUSES:
            result[ct_id][status] = 0
    
    # Count cards
    for card in cards:
        ct_id = card.get("card_type_id", "")
        status = card.get("status", "")
        if ct_id in result and status in REPORT_STATUSES:
            result[ct_id][status] += 1
            result[ct_id]["total"] += 1
    
    # Build report list
    report = []
    for ct_id in sorted(result.keys(), key=lambda k: result[k]["card_type_name"]):
        report.append(result[ct_id])
    
    return report
