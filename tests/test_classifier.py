import pytest
from backend.models import RawReport, SignalType, Category, Severity
from backend.fallback.keyword_rules import classify_by_keywords


def test_keyword_classifier_scam_happy_path():
    """A clear UPI scam report should be classified as SIGNAL/SCAM."""
    signal, category, severity, confidence = classify_by_keywords(
        title="UPI Fraud Alert: Fake collect requests targeting Bengaluru residents",
        content="Multiple residents reported receiving unsolicited UPI collect requests "
                "from unknown accounts claiming to be refunds. Victims lost money when "
                "they approved the requests thinking they were receiving cashback.",
    )
    assert signal == SignalType.SIGNAL
    assert category == Category.SCAM
    assert severity in (Severity.HIGH, Severity.MEDIUM, Severity.CRITICAL)
    assert 0.3 <= confidence <= 0.6


def test_keyword_classifier_phishing():
    """A phishing report should be classified correctly."""
    signal, category, severity, confidence = classify_by_keywords(
        title="Fake KYC Update Scam Targets Bank Customers",
        content="Customers receiving SMS claiming KYC expiry with link to "
                "fake banking portal that steals login credentials.",
    )
    assert signal == SignalType.SIGNAL
    assert category == Category.PHISHING
    assert 0.3 <= confidence <= 0.6


def test_keyword_classifier_breach():
    """A data breach report should be classified correctly."""
    signal, category, severity, confidence = classify_by_keywords(
        title="Data Breach at Major Indian E-commerce Platform",
        content="Hackers exposed personal data of millions of users. "
                "The breach was confirmed by CERT-In. Passwords leaked on dark web.",
    )
    assert signal == SignalType.SIGNAL
    assert category == Category.BREACH


def test_keyword_classifier_noise_entertainment():
    """A cricket/entertainment article should be classified as NOISE."""
    signal, category, severity, confidence = classify_by_keywords(
        title="Virat Kohli's Aggressive Attack Stuns Cricket Fans",
        content="In an entertaining match, the celebrity batsman entertained "
                "fans with an aggressive batting display at the IPL.",
    )
    assert signal == SignalType.NOISE
    assert category == Category.NOISE


def test_keyword_classifier_noise_food():
    """A food/restaurant article should be classified as NOISE."""
    signal, category, severity, confidence = classify_by_keywords(
        title="Best Biryani Places in Koramangala",
        content="Exploring the newest cafe and restaurant openings in the "
                "city's thriving food scene. Best biryani recommendations.",
    )
    assert signal == SignalType.NOISE
    assert category == Category.NOISE


def test_keyword_classifier_empty_content():
    """Empty content should be classified as NOISE gracefully."""
    signal, category, severity, confidence = classify_by_keywords(
        title="",
        content="",
    )
    assert signal == SignalType.NOISE
    assert category == Category.NOISE
    assert confidence == 0.3


def test_keyword_classifier_physical_threat():
    """A physical safety report should be classified correctly."""
    signal, category, severity, confidence = classify_by_keywords(
        title="Chain Snatching Incidents Spike in South Delhi",
        content="Police report 15 chain snatching and theft cases in the "
                "past week. Robbery incidents on the rise. FIR filed.",
    )
    assert signal == SignalType.SIGNAL
    assert category == Category.PHYSICAL


def test_keyword_classifier_confidence_range():
    """Fallback confidence should always be between 0.3 and 0.6."""
    test_cases = [
        ("scam fraud upi otp", "fake collect request money doubling"),
        ("phishing", "click link verify"),
        ("", ""),
    ]
    for title, content in test_cases:
        _, _, _, confidence = classify_by_keywords(title, content)
        assert 0.3 <= confidence <= 0.6, f"Confidence {confidence} out of range for '{title}'"
