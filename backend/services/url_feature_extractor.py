"""
services/url_feature_extractor.py
----------------------------------
Extracts the 50 features expected by the XGBoost phishing-detection model
from a raw URL string.

Feature extraction is done in two phases:
  1. URL-string analysis   – purely lexical, no network call needed.
  2. Page-content analysis – fetches the page HTML (with a short timeout),
     parses it with BeautifulSoup, and counts HTML elements.

LIMITATIONS (documented honestly):
  - URLSimilarityIndex: computed as character-overlap against the domain name
    (no third-party brand-database comparison).
  - TLDLegitimateProb / URLCharProb: approximated from a hand-curated TLD
    table; not derived from the PhiUSIIL training distribution.
  - Robots: checks whether /robots.txt returns HTTP 200.
  - IsResponsive: checks for <meta name="viewport"> in HTML.
  - NoOfURLRedirect / NoOfSelfRedirect: counted from the requests redirect
    history; does not cover JavaScript-based redirects.
  - If the page cannot be fetched (timeout, SSL error, etc.) all
    page-content features default to 0 / safe values, and
    `fetch_error` is set in the returned metadata dict.

These approximations may reduce model accuracy for individual URLs.
The model was originally trained on the PhiUSIIL dataset where features were
computed by the dataset authors using more complete tooling.
"""

from __future__ import annotations

import ipaddress
import math
import re
import socket
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TLD probability table (hand-curated subset of the most common TLDs)
# Legitimacy probability = fraction of legitimate sites in the PhiUSIIL
# training set that use this TLD (approximated from public domain statistics).
# ---------------------------------------------------------------------------
_TLD_LEGIT_PROB: Dict[str, float] = {
    "com": 0.82, "org": 0.88, "net": 0.75, "edu": 0.99, "gov": 0.99,
    "io": 0.78, "co": 0.74, "uk": 0.85, "de": 0.87, "fr": 0.86,
    "jp": 0.85, "au": 0.87, "ca": 0.86, "in": 0.72, "us": 0.80,
    "info": 0.55, "biz": 0.45, "ru": 0.60, "cn": 0.58, "br": 0.75,
    "nl": 0.87, "it": 0.86, "es": 0.84, "se": 0.88, "ch": 0.92,
    "be": 0.88, "at": 0.90, "pl": 0.81, "cz": 0.84, "nz": 0.89,
    "mx": 0.74, "ar": 0.73, "za": 0.76, "xyz": 0.38, "top": 0.30,
    "site": 0.40, "online": 0.42, "club": 0.35, "tech": 0.55,
    "live": 0.45, "shop": 0.48, "store": 0.45, "app": 0.65,
    "dev": 0.70, "ai": 0.68, "gg": 0.72, "me": 0.62, "cc": 0.40,
    "tk": 0.10, "ml": 0.12, "ga": 0.12, "cf": 0.12, "gq": 0.12,
    "xsph": 0.05, "ru": 0.55,
}
_DEFAULT_TLD_LEGIT_PROB = 0.50  # unknown TLD

# Social-network keywords
_SOCIAL_KEYWORDS = {
    "facebook", "twitter", "instagram", "linkedin", "youtube",
    "tiktok", "pinterest", "snapchat", "reddit", "whatsapp",
    "telegram", "discord",
}

# Obfuscation patterns (percent-encoding and other URL tricks)
_OBFUSCATION_RE = re.compile(r'%[0-9a-fA-F]{2}|0x[0-9a-fA-F]+')

# Characters considered "special" in the URL (excluding alphanumerics and safe chars)
_SPECIAL_CHARS_RE = re.compile(r'[^a-zA-Z0-9.\-_~:/?#\[\]@!$&\'()*+,;=%]')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_ip(hostname: str) -> bool:
    """Return True if hostname is an IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(hostname.strip("[]"))
        return True
    except ValueError:
        return False


def _tld_from_hostname(hostname: str) -> str:
    """
    Best-effort TLD extraction.
    Handles country-code second-level domains like co.uk.
    """
    parts = hostname.rstrip(".").split(".")
    if len(parts) >= 2:
        # Detect ccSLD patterns like co.uk, com.au, org.uk …
        if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "gov", "edu"):
            return f"{parts[-2]}.{parts[-1]}"
        return parts[-1]
    return hostname


def _char_continuation_rate(url: str) -> float:
    """
    Ratio of consecutive repeated characters to total URL length.
    High value suggests obfuscation / gibberish domains.
    """
    if len(url) <= 1:
        return 0.0
    consecutive = sum(1 for i in range(1, len(url)) if url[i] == url[i - 1])
    return consecutive / len(url)


def _url_char_prob(url: str) -> float:
    """
    Shannon entropy-based character probability score (normalized 0-1).
    Lower entropy → more predictable → more likely legitimate.
    Invert so that high value = legitimate.
    """
    if not url:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in url:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(url)
    entropy = -sum((c / n) * math.log2(c / n) for c in freq.values() if c > 0)
    # Normalize to [0, 1]; max useful entropy ~5 bits for typical URL charset
    normalized = min(entropy / 5.0, 1.0)
    return round(1.0 - normalized, 6)  # inverted: high = more legitimate


def _similarity_index(url: str, domain: str) -> float:
    """
    Simple character-overlap similarity between the URL and the domain name.
    Acts as a proxy for whether the URL consistently represents a single brand.
    """
    if not domain:
        return 0.0
    url_chars = set(url.lower())
    domain_chars = set(domain.lower().replace(".", ""))
    if not domain_chars:
        return 0.0
    overlap = len(url_chars & domain_chars)
    return round(overlap / len(domain_chars) * 100.0, 4)


# ---------------------------------------------------------------------------
# URL-string feature extraction (no network required)
# ---------------------------------------------------------------------------

def _extract_url_features(url: str) -> Dict[str, Any]:
    parsed = urllib.parse.urlparse(url if "://" in url else "http://" + url)
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname or ""
    path = parsed.path or ""
    query = parsed.query or ""
    full_url = url

    tld = _tld_from_hostname(hostname)
    is_ip = _is_ip(hostname)

    # Domain length excludes TLD
    domain_part = hostname.removesuffix("." + tld) if not is_ip else hostname
    domain_length = len(domain_part)

    # Sub-domain count: parts between scheme and registered domain
    host_parts = hostname.split(".")
    # e.g. a.b.example.co.uk → subdomains = [a, b]
    tld_parts = tld.split(".")
    n_tld = len(tld_parts)
    # registered domain = last (n_tld + 1) parts
    reg_domain_depth = n_tld + 1
    sub_parts = host_parts[:-reg_domain_depth] if len(host_parts) > reg_domain_depth else []
    n_subdomains = len(sub_parts)

    # Obfuscation
    obfuscated_matches = _OBFUSCATION_RE.findall(full_url)
    n_obfuscated = len(obfuscated_matches)
    has_obfuscation = 1 if n_obfuscated > 0 else 0
    obfuscation_ratio = round(n_obfuscated / len(full_url), 6) if full_url else 0.0

    # Letter counts
    letters_in_url = sum(1 for c in full_url if c.isalpha())
    letter_ratio = round(letters_in_url / len(full_url), 6) if full_url else 0.0

    digits_in_url = sum(1 for c in full_url if c.isdigit())
    digit_ratio = round(digits_in_url / len(full_url), 6) if full_url else 0.0

    n_equals = full_url.count("=")
    n_qmark = full_url.count("?")
    n_ampersand = full_url.count("&")

    special_matches = _SPECIAL_CHARS_RE.findall(full_url)
    n_special = len(special_matches)
    special_ratio = round(n_special / len(full_url), 6) if full_url else 0.0

    tld_legit_prob = _TLD_LEGIT_PROB.get(tld.lower(), _DEFAULT_TLD_LEGIT_PROB)

    return {
        "URLLength": len(full_url),
        "DomainLength": domain_length,
        "IsDomainIP": 1 if is_ip else 0,
        "URLSimilarityIndex": _similarity_index(full_url, hostname),
        "CharContinuationRate": round(_char_continuation_rate(full_url), 6),
        "TLDLegitimateProb": tld_legit_prob,
        "URLCharProb": _url_char_prob(full_url),
        "TLDLength": len(tld),
        "NoOfSubDomain": n_subdomains,
        "HasObfuscation": has_obfuscation,
        "NoOfObfuscatedChar": n_obfuscated,
        "ObfuscationRatio": obfuscation_ratio,
        "NoOfLettersInURL": letters_in_url,
        "LetterRatioInURL": letter_ratio,
        "NoOfDegitsInURL": digits_in_url,
        "DegitRatioInURL": digit_ratio,
        "NoOfEqualsInURL": n_equals,
        "NoOfQMarkInURL": n_qmark,
        "NoOfAmpersandInURL": n_ampersand,
        "NoOfOtherSpecialCharsInURL": n_special,
        "SpacialCharRatioInURL": special_ratio,
        "IsHTTPS": 1 if scheme == "https" else 0,
        # Page features: defaults – overwritten if fetch succeeds
        "LineOfCode": 0,
        "LargestLineLength": 0,
        "HasTitle": 0,
        "DomainTitleMatchScore": 0.0,
        "URLTitleMatchScore": 0.0,
        "HasFavicon": 0,
        "Robots": 0,
        "IsResponsive": 0,
        "NoOfURLRedirect": 0,
        "NoOfSelfRedirect": 0,
        "HasDescription": 0,
        "NoOfPopup": 0,
        "NoOfiFrame": 0,
        "HasExternalFormSubmit": 0,
        "HasSocialNet": 0,
        "HasSubmitButton": 0,
        "HasHiddenFields": 0,
        "HasPasswordField": 0,
        "Bank": 0,
        "Pay": 0,
        "Crypto": 0,
        "HasCopyrightInfo": 0,
        "NoOfImage": 0,
        "NoOfCSS": 0,
        "NoOfJS": 0,
        "NoOfSelfRef": 0,
        "NoOfEmptyRef": 0,
        "NoOfExternalRef": 0,
        # metadata
        "_hostname": hostname,
        "_tld": tld,
        "_scheme": scheme,
        "_parsed_url": parsed,
    }


# ---------------------------------------------------------------------------
# Page-content feature extraction
# ---------------------------------------------------------------------------

def _extract_page_features(
    url: str,
    hostname: str,
    scheme: str,
    parsed_url: urllib.parse.ParseResult,
    timeout: float = 8.0,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Fetch the URL and extract HTML-based features.

    Returns:
        (features_dict, fetch_error_string_or_None)
    """
    feats: Dict[str, Any] = {}
    fetch_error: Optional[str] = None

    try:
        import requests  # type: ignore
        from bs4 import BeautifulSoup  # type: ignore

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        session = requests.Session()
        resp = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=False,  # some phishing sites have invalid certs; we want to reach them
        )

        # --- Redirect counts ---
        redirect_history = resp.history  # list of redirects
        n_url_redirect = len(redirect_history)
        n_self_redirect = sum(
            1 for r in redirect_history
            if urllib.parse.urlparse(r.headers.get("Location", "")).hostname == hostname
        )

        # --- Robots.txt check ---
        robots_ok = 0
        try:
            base = f"{scheme}://{hostname}"
            r2 = session.get(f"{base}/robots.txt", headers=headers, timeout=4, verify=False)
            robots_ok = 1 if r2.status_code == 200 else 0
        except Exception:
            robots_ok = 0

        # --- Parse HTML ---
        html = resp.text
        lines = html.splitlines()
        line_of_code = len(lines)
        largest_line_length = max((len(l) for l in lines), default=0)

        soup = BeautifulSoup(html, "html.parser")

        # Title
        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True).lower() if title_tag else ""
        has_title = 1 if title_text else 0

        # Title similarity to domain
        domain_clean = hostname.lower().replace("www.", "").split(".")[0]
        domain_title_match = (
            100.0 if domain_clean in title_text else
            round(sum(1 for c in domain_clean if c in title_text) / len(domain_clean) * 100, 2)
            if domain_clean else 0.0
        )
        url_lower = url.lower()
        url_title_match = (
            100.0 if domain_clean in title_text else
            round(sum(1 for c in domain_clean if c in url_lower) / len(domain_clean) * 100, 2)
            if domain_clean else 0.0
        )

        # Favicon
        favicon_tags = soup.find_all("link", rel=lambda r: r and "icon" in " ".join(r).lower())
        has_favicon = 1 if favicon_tags else 0

        # Responsive (viewport meta)
        viewport = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "viewport"})
        is_responsive = 1 if viewport else 0

        # Description meta
        desc_meta = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "description"})
        has_description = 1 if desc_meta else 0

        # Popups (window.open calls in scripts)
        scripts = soup.find_all("script")
        script_text = " ".join(s.get_text() for s in scripts).lower()
        n_popup = script_text.count("window.open")

        # iFrames
        iframes = soup.find_all("iframe")
        n_iframe = len(iframes)

        # Forms with external action
        forms = soup.find_all("form")
        n_external_form = 0
        for form in forms:
            action = form.get("action", "")
            if action and action.startswith("http"):
                action_host = urllib.parse.urlparse(action).hostname or ""
                if action_host and action_host != hostname:
                    n_external_form += 1
        has_external_form_submit = 1 if n_external_form > 0 else 0

        # Social network links
        all_links_text = " ".join(
            str(a.get("href", "")) for a in soup.find_all("a", href=True)
        ).lower()
        has_social_net = 1 if any(kw in all_links_text for kw in _SOCIAL_KEYWORDS) else 0

        # Submit buttons
        submit_btns = soup.find_all(
            lambda tag: (
                (tag.name == "input" and tag.get("type", "").lower() == "submit") or
                (tag.name == "button" and tag.get("type", "submit") is not None)
            )
        )
        has_submit_button = 1 if submit_btns else 0

        # Hidden fields
        hidden_fields = soup.find_all("input", attrs={"type": "hidden"})
        has_hidden_fields = 1 if hidden_fields else 0

        # Password fields
        password_fields = soup.find_all("input", attrs={"type": "password"})
        has_password_field = 1 if password_fields else 0

        # Keyword features (in visible text + HTML)
        full_text_lower = soup.get_text().lower() + html.lower()
        bank_kws = {"bank", "banking", "account", "transfer", "wire"}
        pay_kws = {"payment", "paypal", "pay", "checkout", "billing", "invoice"}
        crypto_kws = {"bitcoin", "crypto", "ethereum", "wallet", "blockchain", "nft"}
        copyright_kws = {"©", "copyright", "all rights reserved"}
        has_bank = 1 if any(k in full_text_lower for k in bank_kws) else 0
        has_pay = 1 if any(k in full_text_lower for k in pay_kws) else 0
        has_crypto = 1 if any(k in full_text_lower for k in crypto_kws) else 0
        has_copyright = 1 if any(k in full_text_lower for k in copyright_kws) else 0

        # Count elements
        n_images = len(soup.find_all("img"))
        n_css = len(soup.find_all("link", rel=lambda r: r and "stylesheet" in " ".join(r).lower()))
        n_js = len(soup.find_all("script", src=True))

        # Self-ref vs external ref (anchor tags)
        anchors = soup.find_all("a", href=True)
        n_self_ref = 0
        n_empty_ref = 0
        n_external_ref = 0
        for a in anchors:
            href = a.get("href", "").strip()
            if not href or href in ("#", "javascript:void(0)", "javascript:;", ""):
                n_empty_ref += 1
            elif href.startswith("http"):
                ref_host = urllib.parse.urlparse(href).hostname or ""
                if ref_host == hostname:
                    n_self_ref += 1
                else:
                    n_external_ref += 1
            else:
                n_self_ref += 1  # relative links are self-refs

        feats = {
            "LineOfCode": line_of_code,
            "LargestLineLength": largest_line_length,
            "HasTitle": has_title,
            "DomainTitleMatchScore": domain_title_match,
            "URLTitleMatchScore": url_title_match,
            "HasFavicon": has_favicon,
            "Robots": robots_ok,
            "IsResponsive": is_responsive,
            "NoOfURLRedirect": n_url_redirect,
            "NoOfSelfRedirect": n_self_redirect,
            "HasDescription": has_description,
            "NoOfPopup": n_popup,
            "NoOfiFrame": n_iframe,
            "HasExternalFormSubmit": has_external_form_submit,
            "HasSocialNet": has_social_net,
            "HasSubmitButton": has_submit_button,
            "HasHiddenFields": has_hidden_fields,
            "HasPasswordField": has_password_field,
            "Bank": has_bank,
            "Pay": has_pay,
            "Crypto": has_crypto,
            "HasCopyrightInfo": has_copyright,
            "NoOfImage": n_images,
            "NoOfCSS": n_css,
            "NoOfJS": n_js,
            "NoOfSelfRef": n_self_ref,
            "NoOfEmptyRef": n_empty_ref,
            "NoOfExternalRef": n_external_ref,
        }

    except Exception as exc:
        fetch_error = f"{type(exc).__name__}: {str(exc)[:200]}"
        logger.warning("Page fetch failed for %s: %s", url, fetch_error)

    return feats, fetch_error


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_features(url: str, timeout: float = 8.0) -> Dict[str, Any]:
    """
    Extract all 50 PhiUSIIL features from a URL.

    Returns a dict with keys matching FEATURE_NAMES (in order), plus:
        "_fetch_error": str | None   – error message if page fetch failed
        "_warnings": list[str]       – non-fatal approximation notes

    Raises:
        ValueError  – if the URL is blank or unparseable
    """
    url = url.strip()
    if not url:
        raise ValueError("URL must not be blank")

    # Normalise: add scheme if missing
    if not re.match(r'^https?://', url, re.I):
        url = "http://" + url

    warnings: List[str] = []

    # Phase 1: URL-string features
    url_feats = _extract_url_features(url)
    hostname: str = url_feats.pop("_hostname")
    tld: str = url_feats.pop("_tld")
    scheme: str = url_feats.pop("_scheme")
    parsed_url: urllib.parse.ParseResult = url_feats.pop("_parsed_url")

    warnings.append(
        "URLSimilarityIndex is approximated using character overlap; live predictions may produce false positives."
    )
    if url_feats["IsDomainIP"]:
        warnings.append("Hostname is an IP address; TLD-based features are approximated.")
    if url_feats["TLDLegitimateProb"] == _DEFAULT_TLD_LEGIT_PROB:
        warnings.append(
            f"TLD '{tld}' not in local probability table; using default {_DEFAULT_TLD_LEGIT_PROB}."
        )

    # Phase 2: Page-content features
    page_feats, fetch_error = _extract_page_features(
        url, hostname, scheme, parsed_url, timeout=timeout
    )

    if fetch_error:
        warnings.append(
            "Page could not be fetched; HTML-based features (LineOfCode, HasTitle, etc.) "
            "are defaulted to 0. Prediction accuracy may be reduced."
        )

    # Merge page features into url_feats
    url_feats.update(page_feats)

    url_feats["_fetch_error"] = fetch_error
    url_feats["_warnings"] = warnings

    return url_feats


def features_to_vector(feature_dict: Dict[str, Any]) -> List[float]:
    """
    Convert the feature dict returned by extract_features() into the ordered
    50-element float list expected by the model.
    """
    from services.feature_schema import FEATURE_NAMES  # type: ignore

    vector = []
    for name in FEATURE_NAMES:
        val = feature_dict.get(name, 0)
        try:
            vector.append(float(val))
        except (TypeError, ValueError):
            vector.append(0.0)
    return vector
