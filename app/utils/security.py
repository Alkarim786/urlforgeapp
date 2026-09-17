"""Security, privacy, and anonymization utilities for URLForge."""

import hashlib
import re
from typing import Optional


def hash_ip(ip_address: Optional[str], salt: str = "urlforge-privacy-salt-2026") -> Optional[str]:
    """Generate a one-way, salted SHA-256 hash of client IP for privacy-compliant analytics.

    Raw IP addresses are discarded immediately and never persisted.
    """
    if not ip_address:
        return None
    raw = f"{salt}:{ip_address.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def classify_user_agent(user_agent: Optional[str]) -> str:
    """Categorize user-agent header into standard client family."""
    if not user_agent:
        return "Direct / Unknown"

    ua = user_agent.lower()

    if any(bot in ua for bot in ("bot", "spider", "crawler", "curl", "postman", "http-client")):
        return "Bot / Tool"
    if "python" in ua or "httpx" in ua or "requests" in ua:
        return "Python / API"
    if "edg" in ua:
        return "Microsoft Edge"
    if "chrome" in ua and "safari" in ua and "edg" not in ua:
        return "Google Chrome"
    if "safari" in ua and "chrome" not in ua:
        return "Apple Safari"
    if "firefox" in ua:
        return "Mozilla Firefox"
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "Mobile Browser"

    return "Other Browser"
