"""
services/url_feature_extractor.py
----------------------------------
Extracts the 50 features expected by the XGBoost phishing-detection model
from a raw URL string using the Public Suffix List (PSL) and SSRF-safe page fetching.

Feature extraction is done in two phases:
  1. URL-string analysis   – purely lexical, using PSL for domain parsing.
  2. Page-content analysis – SSRF-safe page HTML fetch (with a short timeout),
     parsing with BeautifulSoup, and counting HTML security features.

LIMITATIONS & DISCLOSURES:
  - URLSimilarityIndex: In the PhiUSIIL dataset, this was computed against the
    legitimate target brand's domain (often Alexa top rank). In live inference,
    we approximate this using brand-spoofing penalties and lexical Jaccard
    consistency against the registered domain.
  - TLDLegitimateProb / URLCharProb: Evaluated using curated frequency distributions.
  - Page-content features: If a domain is private/unreachable or blocks automated
    crawlers, HTML features safely default to 0 and a disclosure warning is attached.
"""

from __future__ import annotations

import ipaddress
import math
import re
import socket
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import logging
import tldextract

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public Suffix List Extractor & Brand Knowledge
# ---------------------------------------------------------------------------
_psl_extractor = tldextract.TLDExtract()

_COMMON_TARGETED_BRANDS = {
    "google", "microsoft", "apple", "amazon", "facebook", "paypal", "netflix",
    "chase", "wellsfargo", "bankofamerica", "citi", "yahoo", "instagram",
    "whatsapp", "linkedin", "dropbox", "ebay", "adobe", "walmart", "twitter",
    "binance", "coinbase", "metamask", "steam", "roblox", "outlook", "office365",
    "icloud", "bofa", "usps", "dhl", "fedex", "ups", "irs", "gov", "bank",
}

# TLD probability table (PhiUSIIL distribution aligned)
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
    "xsph": 0.05,
}
_DEFAULT_TLD_LEGIT_PROB = 0.50

_SOCIAL_KEYWORDS = {
    "facebook", "twitter", "instagram", "linkedin", "youtube",
    "tiktok", "pinterest", "snapchat", "reddit", "whatsapp",
    "telegram", "discord",
}

_OBFUSCATION_RE = re.compile(r'%[0-9a-fA-F]{2}|0x[0-9a-fA-F]+')
_SPECIAL_CHARS_RE = re.compile(r'[^a-zA-Z0-9.\-_~:/?#\[\]@!$&\'()*+,;=%]')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_ip(hostname: str) -> bool:
    """Return True if hostname is an IPv4 or IPv6 address."""
    if not hostname:
        return False
    try:
        ipaddress.ip_address(hostname.strip("[]"))
        return True
    except ValueError:
        return False


def extract_registered_domain(url_or_host: str) -> str:
    """
    Extract the registered domain (e.g. example.co.uk) using the Public Suffix List.
    Handles subdomains, multi-part suffixes, punycode, and IP addresses.
    """
    if not url_or_host:
        return "unknown"
    try:
        norm = url_or_host.strip()
        if "://" not in norm:
            norm = "http://" + norm
        parsed = urllib.parse.urlsplit(norm)
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            return "unknown"
        if _is_ip(hostname):
            return hostname
        ext = _psl_extractor(hostname)
        reg_domain = getattr(ext, "top_domain_under_public_suffix", None) or ext.registered_domain
        if reg_domain:
            return reg_domain.lower()
        if ext.domain:
            return f"{ext.domain}.{ext.suffix}".strip(".").lower()
        return hostname
    except Exception:
        return "unparseable"


def _tld_from_hostname(hostname: str) -> str:
    """Extract TLD or multi-part public suffix from hostname."""
    if not hostname:
        return ""
    h = hostname.strip().lower()
    ext = _psl_extractor(h)
    if ext.suffix:
        return ext.suffix.lower()
    parts = h.rstrip(".").split(".")
    return parts[-1] if len(parts) > 1 else h



def _char_continuation_rate(url: str) -> float:
    if len(url) <= 1:
        return 0.0
    consecutive = sum(1 for i in range(1, len(url)) if url[i] == url[i - 1])
    return consecutive / len(url)


def _url_char_prob(url: str) -> float:
    if not url:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in url:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(url)
    entropy = -sum((c / n) * math.log2(c / n) for c in freq.values() if c > 0)
    normalized = min(entropy / 5.0, 1.0)
    return round(1.0 - normalized, 6)


def _similarity_index(url: str, hostname: str, reg_domain: str, subdomain_str: str) -> float:
    """
    Live approximation of URLSimilarityIndex.
    PhiUSIIL benchmark computed similarity against the true target brand.
    In live inference:
    - If a known brand is present in subdomains or path while the registered domain
      is NOT that brand (brand spoofing), similarity is heavily penalized.
    - Otherwise, returns character Jaccard consistency between domain and URL.
    """
    if not reg_domain or reg_domain in ("unknown", "unparseable"):
        return 0.0

    url_lower = url.lower()
    reg_clean = reg_domain.lower().replace(".", "")
    sub_lower = (subdomain_str or "").lower()

    # Check for brand spoofing
    spoofed_brand = None
    for brand in _COMMON_TARGETED_BRANDS:
        if (brand in sub_lower) or (f"/{brand}" in url_lower) or (f"-{brand}" in sub_lower):
            # Is this actually the brand's registered domain?
            if not reg_domain.startswith(brand + ".") and reg_domain != f"{brand}.com":
                spoofed_brand = brand
                break

    if spoofed_brand:
        # Distance between registered domain and spoofed brand (typically 20-55%)
        common_chars = set(reg_clean) & set(spoofed_brand)
        ratio = len(common_chars) / max(len(set(spoofed_brand)), 1) * 100.0
        return round(min(ratio, 50.0), 4)

    # General Jaccard consistency
    url_chars = set(url_lower)
    domain_chars = set(reg_clean)
    if not domain_chars or not url_chars:
        return 0.0

    jaccard = len(url_chars & domain_chars) / len(url_chars | domain_chars) * 100.0
    return round(jaccard, 4)


# ---------------------------------------------------------------------------
# SSRF Protection
# ---------------------------------------------------------------------------

def _is_restricted_ip(ip_str: str) -> bool:
    """Return True if IP is private, loopback, link-local, multicast, or metadata."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


def _check_ssrf(hostname: str) -> Tuple[bool, str]:
    """Validate that hostname does not resolve to internal or restricted IP ranges."""
    if not hostname:
        return True, "Empty hostname"
    h_clean = hostname.strip("[]").lower()
    if h_clean in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
        return True, f"Hostname '{hostname}' refers to local or cloud metadata."
    if _is_ip(h_clean) and _is_restricted_ip(h_clean):
        return True, f"IP '{hostname}' is within a private or restricted network range."

    try:
        addr_info = socket.getaddrinfo(h_clean, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_val = sockaddr[0]
            if _is_restricted_ip(ip_val):
                return True, f"Hostname '{hostname}' resolves to private IP {ip_val}."
    except socket.gaierror:
        # Domain name does not resolve
        pass
    except Exception:
        pass

    return False, ""


# ---------------------------------------------------------------------------
# URL-string feature extraction
# ---------------------------------------------------------------------------

def _extract_url_features(url: str) -> Dict[str, Any]:
    norm = url if "://" in url else "http://" + url
    parsed = urllib.parse.urlsplit(norm)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    full_url = url

    is_ip = _is_ip(hostname)

    # PSL extraction
    ext = _psl_extractor(hostname)
    reg_domain = getattr(ext, "top_domain_under_public_suffix", None) or ext.registered_domain
    if not reg_domain:
        reg_domain = hostname if is_ip else (f"{ext.domain}.{ext.suffix}".strip(".") if ext.suffix else hostname)

    tld = ext.suffix if ext.suffix else (hostname.split(".")[-1] if "." in hostname else "")
    domain_label = ext.domain if ext.domain else reg_domain
    domain_length = len(domain_label)

    subdomain_str = ext.subdomain
    n_subdomains = len(subdomain_str.split(".")) if subdomain_str else 0

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
    sim_index = _similarity_index(full_url, hostname, reg_domain, subdomain_str)

    return {
        "URLLength": len(full_url),
        "DomainLength": domain_length,
        "IsDomainIP": 1 if is_ip else 0,
        "URLSimilarityIndex": sim_index,
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
        # Page feature defaults (0 values)
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
        # Internal metadata
        "_hostname": hostname,
        "_registered_domain": reg_domain,
        "_tld": tld,
        "_scheme": scheme,
    }


# ---------------------------------------------------------------------------
# Page-content feature extraction (SSRF-protected)
# ---------------------------------------------------------------------------

def _extract_page_features(
    url: str,
    hostname: str,
    scheme: str,
    timeout: float = 8.0,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    SSRF-safe HTML fetch and content feature extraction.
    """
    feats: Dict[str, Any] = {}

    # SSRF verification
    is_ssrf, ssrf_reason = _check_ssrf(hostname)
    if is_ssrf:
        return {}, f"Blocked by SSRF security policy: {ssrf_reason}"

    try:
        import requests
        from bs4 import BeautifulSoup
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36 PhishGuard-Scanner/1.1"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        }

        session = requests.Session()
        resp = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=False,
        )

        redirect_history = resp.history
        n_url_redirect = len(redirect_history)
        n_self_redirect = sum(
            1 for r in redirect_history
            if urllib.parse.urlsplit(r.headers.get("Location", "")).hostname == hostname
        )

        robots_ok = 0
        try:
            base = f"{scheme}://{hostname}"
            r2 = session.get(f"{base}/robots.txt", headers=headers, timeout=3, verify=False)
            robots_ok = 1 if r2.status_code == 200 else 0
        except Exception:
            robots_ok = 0

        html = resp.text
        lines = html.splitlines()
        line_of_code = len(lines)
        largest_line_length = max((len(l) for l in lines), default=0)

        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True).lower() if title_tag else ""
        has_title = 1 if title_text else 0

        domain_clean = hostname.replace("www.", "").split(".")[0]
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

        favicon_tags = soup.find_all("link", rel=lambda r: r and "icon" in " ".join(r).lower())
        has_favicon = 1 if favicon_tags else 0

        viewport = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "viewport"})
        is_responsive = 1 if viewport else 0

        desc_meta = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "description"})
        has_description = 1 if desc_meta else 0

        scripts = soup.find_all("script")
        script_text = " ".join(s.get_text() for s in scripts).lower()
        n_popup = script_text.count("window.open")

        iframes = soup.find_all("iframe")
        n_iframe = len(iframes)

        forms = soup.find_all("form")
        n_external_form = 0
        for form in forms:
            action = form.get("action", "")
            if action and action.startswith("http"):
                action_host = urllib.parse.urlsplit(action).hostname or ""
                if action_host and action_host != hostname:
                    n_external_form += 1
        has_external_form_submit = 1 if n_external_form > 0 else 0

        all_links_text = " ".join(
            str(a.get("href", "")) for a in soup.find_all("a", href=True)
        ).lower()
        has_social_net = 1 if any(kw in all_links_text for kw in _SOCIAL_KEYWORDS) else 0

        submit_btns = soup.find_all(
            lambda tag: (
                (tag.name == "input" and tag.get("type", "").lower() == "submit") or
                (tag.name == "button" and tag.get("type", "submit") is not None)
            )
        )
        has_submit_button = 1 if submit_btns else 0

        hidden_fields = soup.find_all("input", attrs={"type": "hidden"})
        has_hidden_fields = 1 if hidden_fields else 0

        password_fields = soup.find_all("input", attrs={"type": "password"})
        has_password_field = 1 if password_fields else 0

        full_text_lower = soup.get_text().lower() + html.lower()
        bank_kws = {"bank", "banking", "account", "transfer", "wire"}
        pay_kws = {"payment", "paypal", "pay", "checkout", "billing", "invoice"}
        crypto_kws = {"bitcoin", "crypto", "ethereum", "wallet", "blockchain", "nft"}
        copyright_kws = {"©", "copyright", "all rights reserved"}
        has_bank = 1 if any(k in full_text_lower for k in bank_kws) else 0
        has_pay = 1 if any(k in full_text_lower for k in pay_kws) else 0
        has_crypto = 1 if any(k in full_text_lower for k in crypto_kws) else 0
        has_copyright = 1 if any(k in full_text_lower for k in copyright_kws) else 0

        n_images = len(soup.find_all("img"))
        n_css = len(soup.find_all("link", rel=lambda r: r and "stylesheet" in " ".join(r).lower()))
        n_js = len(soup.find_all("script", src=True))

        anchors = soup.find_all("a", href=True)
        n_self_ref = 0
        n_empty_ref = 0
        n_external_ref = 0
        for a in anchors:
            href = a.get("href", "").strip()
            if not href or href in ("#", "javascript:void(0)", "javascript:;", ""):
                n_empty_ref += 1
            elif href.startswith("http"):
                ref_host = urllib.parse.urlsplit(href).hostname or ""
                if ref_host == hostname:
                    n_self_ref += 1
                else:
                    n_external_ref += 1
            else:
                n_self_ref += 1

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
        return feats, None
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {str(exc)[:180]}"
        return {}, err_msg


# ---------------------------------------------------------------------------
# Public Extraction Interface
# ---------------------------------------------------------------------------

def extract_features(url: str, timeout: float = 8.0) -> Dict[str, Any]:
    """
    Extract all 50 features expected by the model from a URL.
    Validates URL scheme, applies SSRF prevention, uses Public Suffix List,
    and returns feature values plus operational metadata.
    """
    if not url or not url.strip():
        raise ValueError("URL must not be blank")

    url = url.strip()

    # Reject non-HTTP schemes
    if "://" in url:
        scheme_prefix = url.split("://")[0].lower()
        if scheme_prefix not in ("http", "https"):
            raise ValueError(
                f"Unsupported URL scheme '{scheme_prefix}://'. Only HTTP and HTTPS URLs are accepted."
            )
    else:
        url = "http://" + url

    warnings: List[str] = []

    # Phase 1: URL lexical analysis
    url_feats = _extract_url_features(url)
    hostname: str = url_feats.pop("_hostname")
    reg_domain: str = url_feats.pop("_registered_domain")
    tld: str = url_feats.pop("_tld")
    scheme: str = url_feats.pop("_scheme")

    warnings.append(
        "Notice: URLSimilarityIndex is approximated in live analysis. Offline PhiUSIIL benchmark computed "
        "similarity against the true targeted brand, which is unverified during real-time inference."
    )
    if url_feats["IsDomainIP"]:
        warnings.append("Hostname is an IP address; TLD features are approximated.")
    if url_feats["TLDLegitimateProb"] == _DEFAULT_TLD_LEGIT_PROB:
        warnings.append(f"TLD '{tld}' not in local probability table; using default {_DEFAULT_TLD_LEGIT_PROB}.")

    # Phase 2: SSRF-protected page content fetch
    page_feats, fetch_error = _extract_page_features(url, hostname, scheme, timeout=timeout)
    if fetch_error:
        warnings.append(f"Page fetch notice: {fetch_error}. HTML features defaulted to 0.")

    url_feats.update(page_feats)
    url_feats["_hostname"] = hostname
    url_feats["_registered_domain"] = reg_domain
    url_feats["_fetch_error"] = fetch_error
    url_feats["_warnings"] = warnings

    return url_feats


def features_to_vector(feature_dict: Dict[str, Any]) -> List[float]:
    """Convert feature dict to exact ordered 50-element float list."""
    from services.feature_schema import FEATURE_NAMES

    vector: List[float] = []
    for name in FEATURE_NAMES:
        val = feature_dict.get(name, 0.0)
        try:
            vector.append(float(val))
        except (TypeError, ValueError):
            vector.append(0.0)
    return vector
