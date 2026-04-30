"""AI Help Desk Assistant

Turns a raw user issue into a structured Tier 1 help desk triage response.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

TICKET_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "ticket_number": {"type": "integer", "minimum": 1, "maximum": 99, "description": "Ticket number in the current run cycle."},
        "status": {"type": "string", "enum": ["open", "in_progress", "resolved", "escalated"], "description": "Current ticket status."},
        "created_at": {"type": "string", "description": "Ticket creation timestamp in ISO 8601 format."},
        "updated_at": {"type": "string", "description": "Last update timestamp in ISO 8601 format."},
        "category": {"type": "string", "description": "Primary technical category."},
        "urgency": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "summary": {"type": "string"},
        "clarifying_questions": {"type": "array", "items": {"type": "string"}},
        "troubleshooting_steps": {"type": "array", "items": {"type": "string"}},
        "ticket_note": {"type": "string"},
        "notes": {"type": "string", "description": "Optional additional ticket notes."},
        "escalation_needed": {"type": "boolean"},
        "escalation_reason": {"type": "string"},
    },
    "required": [
        "ticket_number", "status", "created_at", "updated_at", "category", "urgency", "summary", "clarifying_questions",
        "troubleshooting_steps", "ticket_note", "notes", "escalation_needed", "escalation_reason",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """
You are a Tier 1 help desk triage assistant. Convert the user's raw issue into a structured support response.
Be practical, calm, and concise. Do not invent facts. Ask clarifying questions when details are missing.
Only suggest safe troubleshooting steps appropriate for a first-level support technician.
For security issues, prioritize verification, containment, documentation, and escalation.
""".strip()

TICKET_COUNTER_FILE = ".ticket_counter"
TICKET_DB_FILE = ".tickets.json"


def get_ticket_counter_path() -> str:
    base_dir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_dir, TICKET_COUNTER_FILE)


def get_ticket_db_path() -> str:
    base_dir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_dir, TICKET_DB_FILE)


def load_ticket_db() -> Dict[str, Dict[str, Any]]:
    path = get_ticket_db_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_ticket_db(db: Dict[str, Dict[str, Any]]) -> None:
    path = get_ticket_db_path()
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(db, handle, indent=2)
    except Exception:
        pass


def get_next_ticket_number() -> int:
    path = get_ticket_counter_path()
    number = 0
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read().strip()
                number = int(raw) if raw.isdigit() else 0
    except Exception:
        number = 0

    number = number + 1 if 1 <= number < 99 else 1
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(number))
    except Exception:
        pass
    return number


def save_ticket_entry(result: Dict[str, Any]) -> None:
    ticket_db = load_ticket_db()
    ticket_number = str(result.get("ticket_number", ""))
    if ticket_number.isdigit():
        ticket_db[ticket_number] = result
        save_ticket_db(ticket_db)


def update_ticket_entry(ticket_number: int, note: str = "", status: str | None = None, manual_help: bool = False) -> Dict[str, Any]:
    ticket_db = load_ticket_db()
    key = str(ticket_number)
    ticket = ticket_db.get(key)
    if ticket is None:
        raise ValueError(f"Ticket {ticket_number} not found.")

    now = datetime.now(timezone.utc).isoformat()
    if not ticket.get("created_at"):
        ticket["created_at"] = now
    ticket["updated_at"] = now

    if status:
        ticket["status"] = status

    if manual_help:
        manual_message = (
            "If these troubleshooting steps do not resolve the issue, consult the support manual "
            "or request additional help from a specialist."
        )
        if isinstance(ticket.get("troubleshooting_steps"), list) and manual_message not in ticket["troubleshooting_steps"]:
            ticket["troubleshooting_steps"].append(manual_message)
        ticket["ticket_note"] = f"{ticket.get('ticket_note', '').strip()} {manual_message}".strip()

    if note:
        if ticket.get("notes"):
            ticket["notes"] = f"{ticket['notes']} | {note}"
        else:
            ticket["notes"] = note
        if note not in ticket.get("ticket_note", ""):
            ticket["ticket_note"] = f"{ticket.get('ticket_note', '').strip()} Additional note: {note}".strip()

    ticket_db[key] = ticket
    save_ticket_db(ticket_db)
    return ticket


def list_tickets() -> None:
    ticket_db = load_ticket_db()
    if not ticket_db:
        print("No saved tickets found.")
        return

    for ticket_number in sorted(ticket_db, key=lambda n: int(n)):
        ticket = ticket_db[ticket_number]
        print(f"{ticket_number}: [{ticket.get('status', 'open')}] {ticket.get('summary', '')} (urgency={ticket.get('urgency', '')})")


def export_tickets(format: str) -> None:
    ticket_db = load_ticket_db()
    if format == "json":
        print(json.dumps(ticket_db, indent=2))
    elif format == "csv":
        print("ticket_number,status,urgency,category,summary,notes,updated_at")
        for ticket_number in sorted(ticket_db, key=lambda n: int(n)):
            ticket = ticket_db[ticket_number]
            values = [
                ticket_number,
                ticket.get("status", "open"),
                ticket.get("urgency", ""),
                ticket.get("category", ""),
                ticket.get("summary", ""),
                ticket.get("notes", ""),
                ticket.get("updated_at", ""),
            ]
            print(",".join(f'"{str(value).replace("\"", "\"\"")}"' for value in values))


def enrich_ticket(result: Dict[str, Any], note: str = "", manual_help: bool = False, status: str = "open") -> Dict[str, Any]:
    result.setdefault("ticket_number", get_next_ticket_number())
    result.setdefault("notes", "")
    result.setdefault("status", status)

    now = datetime.now(timezone.utc).isoformat()
    if not result.get("created_at"):
        result["created_at"] = now
    result["updated_at"] = now

    if manual_help:
        manual_message = (
            "If these troubleshooting steps do not resolve the issue, consult the support manual "
            "or request additional help from a specialist."
        )
        if isinstance(result.get("troubleshooting_steps"), list) and manual_message not in result["troubleshooting_steps"]:
            result["troubleshooting_steps"].append(manual_message)
        result["ticket_note"] = f"{result.get('ticket_note', '').strip()} {manual_message}".strip()

    if note:
        if result.get("notes"):
            result["notes"] = f"{result['notes']} | {note}"
        else:
            result["notes"] = note
        if note not in result.get("ticket_note", ""):
            result["ticket_note"] = f"{result.get('ticket_note', '').strip()} Additional note: {note}".strip()

    save_ticket_entry(result)
    return result


def demo_response(issue: str, note: str = "", manual_help: bool = False) -> Dict[str, Any]:
    lower = issue.lower()
    urgency = "medium"
    if "password" in lower or "login" in lower or "locked" in lower:
        category = "account_access"
        summary = "User is experiencing an account login or password access issue."
        steps = [
            "Verify the user's identity according to the organization's support policy.",
            "Confirm the exact error message and whether the account is locked or the password is expired.",
            "Check account status in the identity system or Active Directory if available.",
            "Reset password or unlock account if authorized, then confirm successful login.",
            "Document the resolution and advise the user to update saved passwords if needed.",
        ]
    elif "internet" in lower or "wifi" in lower or "network" in lower:
        category = "network"
        summary = "User is reporting a network connectivity issue."
        steps = [
            "Confirm whether the issue affects one user, one device, or multiple users.",
            "Check Wi-Fi/Ethernet connection status and whether other websites or services work.",
            "Have the user restart the affected application or device if appropriate.",
            "Run basic connectivity checks such as reconnecting to the network or testing another browser.",
            "Escalate if multiple users are affected or if there is evidence of an outage.",
        ]
    elif "security" in lower or "breach" in lower or "malware" in lower or "ransomware" in lower or "phishing" in lower:
        category = "security"
        summary = "User is reporting a security incident that requires urgent handling."
        steps = [
            "Contain the affected system and preserve evidence without making unapproved changes.",
            "Verify the scope of the incident and note any suspicious activity or data exposure.",
            "Notify the security operations team immediately according to incident response procedures.",
            "Avoid sharing sensitive details over insecure channels.",
            "Document all observed behavior and escalate to the appropriate security team.",
        ]
        urgency = "critical"
    elif "outage" in lower or "down" in lower or "unavailable" in lower or "critical" in lower or "urgent" in lower:
        category = "network"
        summary = "User is reporting a critical outage or service unavailability."
        steps = [
            "Confirm the affected service and whether multiple users or systems are impacted.",
            "Check for known incidents or outage notifications from infrastructure teams.",
            "Gather basic connectivity details without making configuration changes.",
            "Notify the operations team if the outage persists or if the issue appears widespread.",
            "Document the incident and escalate immediately if the service is critical to business operations.",
        ]
        urgency = "critical"
    else:
        category = "other"
        summary = "User reported an issue that requires additional triage."
        steps = [
            "Clarify what the user was trying to do and what happened instead.",
            "Collect screenshots, error messages, device details, and time of occurrence.",
            "Determine whether the issue is reproducible.",
            "Try safe first-level fixes such as restarting the app or checking permissions.",
            "Escalate if the issue cannot be resolved with standard Tier 1 steps.",
        ]

    response = {
        "category": category,
        "urgency": urgency,
        "summary": summary,
        "clarifying_questions": [
            "When did the issue start?",
            "What exact error message do you see?",
            "Is this affecting only you or other users too?",
        ],
        "troubleshooting_steps": steps,
        "ticket_note": f"User reported: {issue}. Initial triage completed; next step is to verify details and attempt approved Tier 1 troubleshooting.",
        "escalation_needed": urgency == "critical",
        "escalation_reason": "Critical issue detected and escalation is recommended." if urgency == "critical" else "Not needed based on current details.",
    }
    return enrich_ticket(response, note=note, manual_help=manual_help)


def find_ticket_by_number(number: int) -> Dict[str, Any] | None:
    ticket_db = load_ticket_db()
    return ticket_db.get(str(number))


def fallback_response(issue: str, reason: str, note: str = "", manual_help: bool = False) -> Dict[str, Any]:
    result = demo_response(issue, note=note, manual_help=manual_help)
    if result["urgency"] == "critical":
        result["escalation_needed"] = True
        result["escalation_reason"] = (
            "Critical issue detected during fallback. Escalation is recommended."
        )
    result["ticket_note"] = (
        f"{result['ticket_note']} Fallback applied because: {reason}."
    )
    return result


def analyze_issue(issue: str, demo: bool = False, note: str = "", manual_help: bool = False) -> Dict[str, Any]:
    if demo:
        return demo_response(issue, note=note, manual_help=manual_help)

    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'python-dotenv'. Install it with `pip install python-dotenv`."
        ) from exc

    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'openai'. Install it with `pip install openai`."
        ) from exc

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Set it in your environment or a .env file before running in non-demo mode."
        )

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": issue},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "helpdesk_ticket",
                    "strict": True,
                    "schema": TICKET_SCHEMA,
                }
            },
        )
    except Exception as exc:
        raise RuntimeError(
            "OpenAI API request failed. Check your API key, network connectivity, and model settings."
        ) from exc

    try:
        result = json.loads(response.output_text)
    except Exception as exc:
        raise RuntimeError(
            "Failed to parse OpenAI response. The API returned unexpected output."
        ) from exc

    return enrich_ticket(result, note=note, manual_help=manual_help)


def print_result(result: Dict[str, Any]) -> None:
    print(f"\nAI Help Desk Assistant: {result['summary']}\n")
    print("Triage")
    print(f"- Ticket number: {result['ticket_number']}")
    print(f"- Status: {result.get('status', 'open')}")
    print(f"- Category: {result['category']}")
    print(f"- Urgency: {result['urgency']}")
    print(f"- Escalation needed: {result['escalation_needed']}")
    print(f"- Escalation reason: {result['escalation_reason']}")
    print(f"- Created at: {result.get('created_at', '')}")
    print(f"- Updated at: {result.get('updated_at', '')}")
    if result.get('notes'):
        print(f"- Notes: {result['notes']}")

    print("\nClarifying Questions")
    for question in result["clarifying_questions"]:
        print(f"- {question}")

    print("\nTroubleshooting Steps")
    for step in result["troubleshooting_steps"]:
        print(f"- {step}")

    print("\nTicket Note")
    print(result["ticket_note"])


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-powered Tier 1 help desk triage assistant.")
    parser.add_argument("issue", nargs="*", help="User issue to analyze")
    parser.add_argument("--demo", action="store_true", help="Run without an OpenAI API key using a local mock response")
    parser.add_argument("--json", action="store_true", help="Print raw JSON only")
    parser.add_argument("--note", "-n", default="", help="Add an additional note to the ticket")
    parser.add_argument("--manual", action="store_true", help="Append guidance to consult the support manual if troubleshooting steps fail")
    parser.add_argument("--ticket", "-t", type=int, help="Show a saved ticket by ticket number")
    parser.add_argument("--list", action="store_true", help="List saved tickets")
    parser.add_argument("--export", choices=["json", "csv"], help="Export saved tickets")
    parser.add_argument("--update", type=int, help="Update an existing ticket by ticket number")
    parser.add_argument("--status", choices=["open", "in_progress", "resolved", "escalated"], help="Update ticket status")
    args = parser.parse_args()

    if args.list:
        list_tickets()
        return

    if args.export:
        export_tickets(args.export)
        return

    if args.update is not None:
        try:
            ticket = update_ticket_entry(args.update, note=args.note, status=args.status, manual_help=args.manual)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(ticket, indent=2))
        else:
            print_result(ticket)
        return

    if args.ticket is not None:
        ticket = find_ticket_by_number(args.ticket)
        if not ticket:
            print(f"Ticket {args.ticket} not found.", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(ticket, indent=2))
        else:
            print_result(ticket)
        return

    issue = " ".join(args.issue).strip()
    if not issue:
        issue = input("Describe the user's issue: ")

    try:
        result = analyze_issue(issue, demo=args.demo, note=args.note, manual_help=args.manual)
    except RuntimeError as exc:
        print(f"Warning: {exc}. Falling back to local response.", file=sys.stderr)
        result = fallback_response(issue, str(exc), note=args.note, manual_help=args.manual)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_result(result)


if __name__ == "__main__":
    main()
