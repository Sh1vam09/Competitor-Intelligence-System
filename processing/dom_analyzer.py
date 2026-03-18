"""
DOM Structure Analyzer.

Extracts structural features from HTML to identify:
    - CTA button counts
    - Form elements
    - Testimonial blocks
    - Pricing tables
    - Navigation hierarchy
    - Section counts
    - Video presence
    - Social proof elements
"""

from bs4 import BeautifulSoup

from utils.logger import get_logger

logger = get_logger(__name__)


def extract_dom_features(html: str) -> dict:
    """
    Analyze HTML DOM structure and extract key structural features.

    Args:
        html: Raw HTML string.

    Returns:
        Dictionary of DOM structural features.
    """
    soup = BeautifulSoup(html, "lxml")

    features = {
        "cta_button_count": _count_cta_buttons(soup),
        "forms_detected": _count_forms(soup),
        "testimonial_blocks": _count_testimonials(soup),
        "pricing_tables": _count_pricing_elements(soup),
        "navigation_depth": _analyze_navigation(soup),
        "section_count": _count_sections(soup),
        "video_presence": _detect_videos(soup),
        "social_proof_elements": _count_social_proof(soup),
        "image_count": len(soup.find_all("img")),
        "heading_count": len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])),
        "link_count": len(soup.find_all("a")),
        "has_chat_widget": _detect_chat_widget(soup),
    }

    logger.debug("DOM features extracted: %s", features)
    return features


def _count_cta_buttons(soup: BeautifulSoup) -> int:
    """Count buttons and links that appear to be calls-to-action."""
    cta_keywords = [
        "sign up", "get started", "try free", "start", "buy", "subscribe",
        "join", "register", "download", "book", "demo", "contact",
        "free trial", "learn more", "shop now", "order",
    ]
    count = 0

    # Check buttons
    for button in soup.find_all(["button", "a"]):
        text = button.get_text(strip=True).lower()
        classes = " ".join(button.get("class", [])).lower()
        if any(kw in text for kw in cta_keywords) or "cta" in classes:
            count += 1

    # Check input[type=submit]
    for inp in soup.find_all("input", {"type": "submit"}):
        count += 1

    return count


def _count_forms(soup: BeautifulSoup) -> int:
    """Count form elements in the page."""
    return len(soup.find_all("form"))


def _count_testimonials(soup: BeautifulSoup) -> int:
    """Count elements that appear to be testimonials."""
    testimonial_keywords = ["testimonial", "review", "quote", "feedback", "customer-story"]
    count = 0

    for element in soup.find_all(True):
        classes = " ".join(element.get("class", [])).lower()
        el_id = (element.get("id") or "").lower()
        combined = f"{classes} {el_id}"
        if any(kw in combined for kw in testimonial_keywords):
            count += 1

    # Also check for blockquote elements (common for testimonials)
    count += len(soup.find_all("blockquote"))

    return count


def _count_pricing_elements(soup: BeautifulSoup) -> int:
    """Count pricing-related sections or tables."""
    pricing_keywords = ["pricing", "price", "plan", "tier", "subscription"]
    count = 0

    for element in soup.find_all(True):
        classes = " ".join(element.get("class", [])).lower()
        el_id = (element.get("id") or "").lower()
        text = element.get_text(strip=True).lower()[:200]
        combined = f"{classes} {el_id}"
        if any(kw in combined for kw in pricing_keywords):
            count += 1

    # Check for table elements with pricing content
    for table in soup.find_all("table"):
        table_text = table.get_text(strip=True).lower()
        if any(kw in table_text for kw in ["$", "€", "£", "/mo", "/yr", "free", "enterprise"]):
            count += 1

    return count


def _analyze_navigation(soup: BeautifulSoup) -> int:
    """Analyze navigation structure depth (nested ul/li counts)."""
    nav = soup.find("nav")
    if not nav:
        return 0

    # Count max nesting depth of lists in nav
    max_depth = 0

    def _get_depth(element, current_depth):
        nonlocal max_depth
        max_depth = max(max_depth, current_depth)
        for child_ul in element.find_all("ul", recursive=False):
            _get_depth(child_ul, current_depth + 1)

    for ul in nav.find_all("ul", recursive=False):
        _get_depth(ul, 1)

    return max_depth


def _count_sections(soup: BeautifulSoup) -> int:
    """Count distinct content sections."""
    sections = soup.find_all(["section", "article"])
    if not sections:
        # Fallback: count major div containers
        main = soup.find("main") or soup.find("body")
        if main:
            return len(main.find_all("div", recursive=False))
    return len(sections)


def _detect_videos(soup: BeautifulSoup) -> bool:
    """Detect presence of video elements or embedded videos."""
    # Direct video tags
    if soup.find("video"):
        return True

    # YouTube / Vimeo embeds
    for iframe in soup.find_all("iframe"):
        src = (iframe.get("src") or "").lower()
        if "youtube" in src or "vimeo" in src or "wistia" in src:
            return True

    return False


def _count_social_proof(soup: BeautifulSoup) -> int:
    """Count social proof elements (logos, badges, counters)."""
    keywords = [
        "social-proof", "trusted", "partners", "clients", "logos",
        "as-seen", "featured", "badge", "certification", "award",
    ]
    count = 0

    for element in soup.find_all(True):
        classes = " ".join(element.get("class", [])).lower()
        el_id = (element.get("id") or "").lower()
        combined = f"{classes} {el_id}"
        if any(kw in combined for kw in keywords):
            count += 1

    return count


def _detect_chat_widget(soup: BeautifulSoup) -> bool:
    """Detect if the page has a chat widget."""
    chat_keywords = ["intercom", "drift", "crisp", "zendesk", "tawk", "livechat", "chat-widget"]

    for script in soup.find_all("script"):
        src = (script.get("src") or "").lower()
        text = script.string or ""
        combined = f"{src} {text}".lower()
        if any(kw in combined for kw in chat_keywords):
            return True

    return False
