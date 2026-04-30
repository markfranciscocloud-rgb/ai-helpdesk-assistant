# AI Help Desk Assistant

A small AI engineering portfolio project that turns a raw user support issue into a structured Tier 1 help desk triage response.

This project connects entry-level IT support skills with AI engineering concepts: prompt design, API integration, structured JSON output, and practical user-facing automation.

## What it does

Given a user issue, the assistant returns:

- issue category
- urgency level
- concise ticket summary
- clarifying questions
- safe Tier 1 troubleshooting steps
- internal ticket note
- escalation recommendation

## Why I built it

I built this to demonstrate how AI can support real help desk workflows by improving ticket quality, standardizing troubleshooting, and helping technicians document issues clearly.

## Tech stack

- Python
- OpenAI API
- Structured Outputs / JSON schema
- Rich CLI formatting
- python-dotenv

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/ai-helpdesk-assistant.git
cd ai-helpdesk-assistant
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Add your API key to `.env`:

```bash
OPENAI_API_KEY=ADD_OPENAPI_KEY_HERE
OPENAI_MODEL=gpt-4.1-mini
```

## Run with the OpenAI API

```bash
python helpdesk_ai.py "User cannot log in and says their account may be locked."
```

## Run without an API key

```bash
python helpdesk_ai.py --demo "User cannot log in and says their account may be locked."
```

## JSON output

```bash
python helpdesk_ai.py --demo --json "User cannot connect to Wi-Fi."
```

## Example output

```json
{
  "category": "account_access",
  "urgency": "medium",
  "summary": "User is experiencing an account login or password access issue.",
  "clarifying_questions": [
    "When did the issue start?",
    "What exact error message do you see?",
    "Is this affecting only you or other users too?"
  ],
  "troubleshooting_steps": [
    "Verify the user's identity according to the organization's support policy.",
    "Confirm the exact error message and whether the account is locked or the password is expired.",
    "Check account status in the identity system or Active Directory if available.",
    "Reset password or unlock account if authorized, then confirm successful login.",
    "Document the resolution and advise the user to update saved passwords if needed."
  ],
  "ticket_note": "User reported: User cannot log in and says their account may be locked. Initial triage completed; next step is to verify details and attempt approved Tier 1 troubleshooting.",
  "escalation_needed": false,
  "escalation_reason": "Not needed based on current details."
}
```

## Interview talking points

- I used a structured JSON schema so the model returns predictable output instead of free-form text.
- I designed the prompt around Tier 1 support boundaries: clarify, troubleshoot safely, document, and escalate when needed.
- I added a demo mode so the project can be reviewed without requiring an API key.
- This could be extended into a web app, ticketing-system integration, or internal support tool.

## Future improvements

- Add a Streamlit or Flask interface
- Save tickets to SQLite
- Add categories for healthcare, security, and account access workflows
- Add basic evaluation tests for output quality
- Integrate with a ticketing system API

