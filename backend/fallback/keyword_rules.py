from backend.models import Category, Severity, SignalType

CATEGORY_KEYWORDS = {
    Category.PHISHING: [
        "phishing", "fake link", "fake website", "kyc", "credential",
        "login page", "fake email", "impersonat", "verify your account",
        "click here to confirm", "fake portal", "spoofed", "fake sms",
        "verify aadhaar", "update kyc", "fake page",
    ],
    Category.SCAM: [
        "scam", "fraud", "upi", "otp", "lottery", "prize", "investment scheme",
        "ponzi", "money doubling", "quick money", "advance fee",
        "collect request", "qr code", "tech support call", "fake officer",
        "fake cbi", "fake police", "courier scam", "sim swap",
        "screen sharing", "teamviewer", "anydesk",
    ],
    Category.BREACH: [
        "breach", "data leak", "hack", "compromised", "exposed data",
        "database leak", "ransomware", "malware", "vulnerability",
        "passwords leaked", "dark web", "cert-in", "data exposed",
    ],
    Category.PHYSICAL: [
        "robbery", "theft", "break-in", "assault", "accident",
        "hit and run", "missing", "fire", "flood", "earthquake",
        "atm skimming", "chain snatching", "pickpocket", "stolen",
        "suspicious person", "suspicious van",
    ],
}

NOISE_INDICATORS = [
    "celebrity", "cricket", "bollywood", "entertainment",
    "movie", "recipe", "festival", "sale", "discount",
    "stock market", "ipo", "ipl", "premiere", "cafe",
    "restaurant", "food", "biryani", "metro route", "commute",
]

SEVERITY_INDICATORS = {
    Severity.CRITICAL: ["immediate", "urgent", "active now", "ongoing attack", "critical", "300%", "widespread"],
    Severity.HIGH: ["arrested", "warning", "alert", "multiple victims", "police", "fir", "advisory"],
    Severity.MEDIUM: ["reported", "suspected", "investigation", "potential", "complaint"],
    Severity.LOW: ["awareness", "tip", "reminder", "old", "resolved"],
}


def classify_by_keywords(title: str, content: str) -> tuple[SignalType, Category, Severity, float]:
    text = (title + " " + content).lower()

    noise_score = sum(1 for word in NOISE_INDICATORS if word in text)
    safety_score = sum(
        1
        for keywords in CATEGORY_KEYWORDS.values()
        for kw in keywords
        if kw in text
    )

    if noise_score >= 2 and safety_score == 0:
        return SignalType.NOISE, Category.NOISE, Severity.LOW, 0.4

    category_scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            category_scores[cat] = score

    if not category_scores:
        return SignalType.NOISE, Category.NOISE, Severity.LOW, 0.3

    best_category = max(category_scores, key=category_scores.get)

    severity = Severity.MEDIUM
    for sev, indicators in SEVERITY_INDICATORS.items():
        if any(ind in text for ind in indicators):
            severity = sev
            break

    confidence = min(0.6, 0.3 + (category_scores[best_category] * 0.05))
    return SignalType.SIGNAL, best_category, severity, confidence
