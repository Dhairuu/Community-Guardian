from backend.models import Category

CHECKLISTS = {
    Category.PHISHING: {
        "full": [
            "Do NOT click any links in the suspicious message. If you already did, change your passwords immediately.",
            "Report the phishing attempt to the impersonated organization through their official website or helpline.",
            "Enable two-factor authentication on all important accounts if not already active.",
        ],
        "simple": "Do not click any links. Call your bank directly on their official number to verify.",
        "helpline": "Cyber Crime Helpline: 1930 | Report at cybercrime.gov.in",
    },
    Category.SCAM: {
        "full": [
            "Stop all communication with the suspected scammer immediately. Do not send any money or share OTPs.",
            "File a complaint at cybercrime.gov.in or call 1930 with screenshots and transaction details.",
            "Alert your bank to freeze any pending transactions linked to the scam.",
        ],
        "simple": "Stop talking to the caller. Call 1930 to report. Tell a family member what happened.",
        "helpline": "Cyber Crime Helpline: 1930 | Your bank's toll-free number",
    },
    Category.BREACH: {
        "full": [
            "Change passwords for any accounts associated with the breached service. Use unique passwords for each account.",
            "Monitor your bank statements and credit reports for any unauthorized activity in the next 30 days.",
            "Enable two-factor authentication and consider using a password manager.",
        ],
        "simple": "Change your password right now for the affected service. Ask a trusted person to help if needed.",
        "helpline": "CERT-In: incident@cert-in.org.in | 1800-11-4949",
    },
    Category.PHYSICAL: {
        "full": [
            "If you are in immediate danger, call 112 (Emergency) or 100 (Police) right away.",
            "Secure your home: lock doors, activate security cameras, and inform trusted neighbors.",
            "Document what happened with photos or notes and file an FIR at your nearest police station.",
        ],
        "simple": "If in danger, call 112 now. Lock your doors. Tell a neighbor.",
        "helpline": "Emergency: 112 | Police: 100 | Women Helpline: 181",
    },
    Category.NOISE: {
        "full": ["No action needed. This item does not appear to be a safety concern."],
        "simple": "No action needed.",
        "helpline": None,
    },
}

DAILY_TIP_TEMPLATES = [
    "Never share OTPs, PINs, or CVV numbers over the phone — even if the caller claims to be from your bank.",
    "If an offer sounds too good to be true, it probably is. Verify through official channels before acting.",
    "Keep your phone's operating system and apps updated. Security patches fix vulnerabilities that hackers exploit.",
    "Use different passwords for different accounts. A password manager can help you remember them all.",
    "Before clicking any link, check the actual URL carefully. Look for misspellings in domain names.",
    "Set up transaction alerts on all your bank accounts so you're notified of every debit in real time.",
    "Be cautious of unsolicited video calls — some scams now use screen-sharing to steal banking credentials.",
    "Regularly review app permissions on your phone. Remove access for apps you no longer use.",
    "Lock your Aadhaar biometrics at myaadhaar.uidai.gov.in when not in active use.",
    "Only call customer care numbers from official bank apps or the back of your card — never from Google search.",
]


def get_fallback_checklist(category: Category) -> dict:
    template = CHECKLISTS.get(category, CHECKLISTS[Category.NOISE])
    return {
        "checklist": template["full"],
        "simple_checklist": template["simple"],
        "helpline": template["helpline"],
    }


def get_fallback_daily_tip() -> str:
    from datetime import date
    today = date.today()
    index = today.day % len(DAILY_TIP_TEMPLATES)
    return DAILY_TIP_TEMPLATES[index]
