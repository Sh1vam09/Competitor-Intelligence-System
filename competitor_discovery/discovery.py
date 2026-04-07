"""
Competitor Discovery Module.

Uses a two-pronged approach to discover competitors:
1. LLM-based discovery (Groq via LangChain) — asks the LLM to identify competitors
   based on the business profile. Fast and reliable.
2. Tavily web search — used to search with brand features
   to find competitors with enhanced queries.
"""

import json
import re
import sys
import time
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

from langchain_core.messages import HumanMessage

from utils.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    MAX_COMPETITORS,
    MAX_SEARCH_RESULTS,
    SEARCH_RATE_LIMIT_DELAY,
    TAVILY_API_KEY,
    TAVILY_SEARCH_DEPTH,
)
from utils.helpers import (
    extract_domain,
    safe_json_parse,
    retry_with_backoff,
)
from utils.llm_wrapper import call_llm_with_fallback
from utils.logger import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    """Run async coroutine in a separate thread to avoid nested loop issues."""
    import asyncio
    import concurrent.futures
    import sys

    def run_in_thread():
        # On Windows, ProactorEventLoop is required for subprocess support
        # (Playwright spawns browser processes via asyncio subprocesses)
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result()


_EXCLUDED_COMPETITOR_DOMAINS = {
    "booking.com",
    "www.booking.com",
    "similarweb.com",
    "www.similarweb.com",
    "owler.com",
    "www.owler.com",
    "tracxn.com",
    "www.tracxn.com",
    "wikipedia.org",
    "www.wikipedia.org",
    "crunchbase.com",
    "www.crunchbase.com",
    "linkedin.com",
    "www.linkedin.com",
}

_EXCLUDED_DOMAIN_SUFFIXES = (
    ".vercel.app",
    ".netlify.app",
    ".pages.dev",
    ".webflow.io",
    ".notion.site",
)

_EXCLUDED_URL_FRAGMENTS = (
    "booking.com/hotel",
    "/hotel/",
    "/wiki/",
    "/company/",
    "/website/",
    "/alternatives/",
    "/competitors/",
)

_COMPETITOR_LISTING_DOMAINS = (
    "tracxn.com",
    "owler.com",
    "similarweb.com",
    "ahrefs.com",
    "growjo.com",
    "craft.co",
    "cbinsights.com",
)


def _get_base_domain(domain: str) -> str:
    """Strip subdomains to get base domain (e.g., us.puma.com -> puma.com)."""
    parts = domain.lower().split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain.lower()


def _is_excluded_candidate_domain(domain: str, url: str = "") -> bool:
    """Reject non-brand destinations such as aggregators, previews, and listings."""
    domain = (domain or "").strip().lower()
    url = (url or "").strip().lower()
    if not domain:
        return True
    if domain in _EXCLUDED_COMPETITOR_DOMAINS:
        return True
    if any(domain.endswith(suffix) for suffix in _EXCLUDED_DOMAIN_SUFFIXES):
        return True
    if any(fragment in url for fragment in _EXCLUDED_URL_FRAGMENTS):
        return True
    return False


def _filter_candidate_pool(candidates: list[dict], source_domain: str) -> list[dict]:
    """Normalize, filter, and deduplicate candidate competitors."""
    filtered: list[dict] = []
    seen_names: set[str] = set()
    seen_base_domains: set[str] = set()
    source_base = _get_base_domain(source_domain)

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        name = (candidate.get("name") or "").strip()
        url = (candidate.get("url") or "").strip()
        domain = (candidate.get("domain") or extract_domain(url) or "").strip().lower()
        if not name or not domain:
            continue
        if _is_excluded_candidate_domain(domain, url):
            continue

        base_domain = _get_base_domain(domain)
        name_key = name.lower()
        if base_domain == source_base or base_domain in seen_base_domains:
            continue
        if name_key in seen_names:
            continue

        normalized = dict(candidate)
        normalized["domain"] = domain
        normalized["url"] = url if url.startswith("http") else f"https://{domain}"

        seen_names.add(name_key)
        seen_base_domains.add(base_domain)
        filtered.append(normalized)

    return filtered


def _is_competitor_listing_page(url: str, title: str = "") -> bool:
    """Heuristic for pages likely to list competitors or alternatives."""
    haystack = f"{url} {title}".lower()
    return any(domain in haystack for domain in _COMPETITOR_LISTING_DOMAINS) or any(
        token in haystack
        for token in (
            " competitor",
            " competitors",
            " alternative",
            " alternatives",
            " similar companies",
            " similar brands",
        )
    )


def _normalize_company_name(name: str) -> str:
    """Normalize noisy extracted company names from listing pages."""
    name = re.sub(r"\s+", " ", (name or "")).strip()
    name = re.sub(
        r"^(compare|view|visit|get|see|read|explore|top|best|vs|and|or)\s+",
        "",
        name,
        flags=re.I,
    )
    name = re.sub(
        r"\s+(competitors?|alternatives?|website|reviews?)$", "", name, flags=re.I
    )
    return name.strip(" -|:;,")


def _looks_like_company_name(name: str, source_brand: str) -> bool:
    """Filter generic text and keep likely company/brand names."""
    if not name:
        return False
    lowered = name.lower()
    if lowered == source_brand.lower():
        return False
    if lowered in {"and", "or", "the", "a", "an", "with", "view all", "compare"}:
        return False
    if len(name) < 2 or len(name) > 60:
        return False
    if not re.search(r"[A-Za-z]", name):
        return False
    if len(name.split()) > 6:
        return False
    blocked_terms = (
        "competitor",
        "alternative",
        "compare",
        "similar companies",
        "pricing",
        "founded",
        "employees",
        "funding",
        "revenue",
        "overview",
        "industry",
    )
    if any(term in lowered for term in blocked_terms):
        return False
    return True


def _tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web via Tavily and normalize the response shape."""
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not configured, skipping Tavily search")
        return []

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": TAVILY_SEARCH_DEPTH,
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        logger.warning("Tavily search failed for '%s': %s", query, e)
        return []

    normalized = []
    for item in payload.get("results", []):
        url = item.get("url", "")
        if not url:
            continue
        normalized.append(
            {
                "href": url,
                "title": item.get("title", ""),
                "body": item.get("content", ""),
            }
        )
    return normalized


# Country code TLD mapping for geographic detection
_COUNTRY_TLD_MAP = {
    ".in": "India",
    ".co.in": "India",
    ".uk": "United Kingdom",
    ".co.uk": "United Kingdom",
    ".de": "Germany",
    ".fr": "France",
    ".jp": "Japan",
    ".co.jp": "Japan",
    ".cn": "China",
    ".br": "Brazil",
    ".com.br": "Brazil",
    ".au": "Australia",
    ".com.au": "Australia",
    ".ca": "Canada",
    ".kr": "South Korea",
    ".co.kr": "South Korea",
    ".it": "Italy",
    ".es": "Spain",
    ".nl": "Netherlands",
    ".se": "Sweden",
    ".sg": "Singapore",
    ".ae": "UAE",
    ".sa": "Saudi Arabia",
    ".za": "South Africa",
    ".mx": "Mexico",
    ".id": "Indonesia",
    ".co.id": "Indonesia",
    ".ru": "Russia",
    ".tr": "Turkey",
    ".pl": "Poland",
    ".ng": "Nigeria",
}


def _detect_country(source_url: str, source_domain: str, profile: dict) -> str:
    """Detect the company's country from URL TLD and profile geography."""
    country = None

    # 1. Check URL TLD
    domain_lower = source_domain.lower()
    # Check longer TLDs first (e.g., .co.in before .in)
    for tld, country_name in sorted(_COUNTRY_TLD_MAP.items(), key=lambda x: -len(x[0])):
        if domain_lower.endswith(tld):
            country = country_name
            break

    # 2. Fall back to profile's geography_focus
    if not country:
        geo = profile.get("geography_focus", "")
        if (
            isinstance(geo, str)
            and geo
            and geo.lower() not in ("global", "worldwide", "not detected", "n/a", "")
        ):
            country = geo

    # 3. Build the hint string
    if country:
        return f"\nDETECTED COUNTRY/REGION: {country}\nPrioritize competitors that operate in {country} first. At least 5-6 should be {country}-based or have strong presence in {country}."
    return "\nNo specific country detected. Include a mix of global competitors."


# ── LLM-based competitor discovery prompt ──────────────────────────────────────

COMPETITOR_DISCOVERY_PROMPT = """You are a competitive intelligence analyst. Analyze this business profile and identify real competitors.

BUSINESS PROFILE:
{profile}

SOURCE COMPANY URL: {source_url}
{country_hint}
{scope_instruction}

Identify {max_competitors} real, UNIQUE competitor companies. Each must be a DIFFERENT company — do NOT repeat the same company with a different URL or regional subdomain.

CRITICAL — INDUSTRY & NICHE RELEVANCE:
Every competitor MUST operate in the EXACT SAME industry, product category, and target customer niche as the source company.
- If the source sells men's clothing, competitors MUST also sell men's clothing (not women's clothing, not unisex-only, not accessories-only).
- If the source is a SaaS tool, competitors MUST also be SaaS tools in the same domain (not consulting firms, not AI agencies, not unrelated software).
- If the source is a food delivery app, competitors MUST also be food delivery apps (not restaurant management software, not grocery stores).
- Match the SPECIFIC sub-category, not just the broad industry. "Fashion" is too broad — match "men's streetwear" or "women's luxury handbags" etc.

STRICT EXCLUSION RULES — DO NOT return any company that:
- Operates in a DIFFERENT industry (e.g., an AI/tech company when the source is a clothing brand)
- Targets a DIFFERENT customer segment (e.g., women's clothing when the source targets men)
- Sells fundamentally different products/services even if the brand name sounds similar
- Is primarily a marketplace/aggregator unless the source company is also one
- Is a preview, booking, listing, directory, travel, or analytics domain rather than an official brand website

For each competitor, provide:
- name: Company/brand name
- url: Their main website URL (use the global domain like https://www.example.com, NOT regional subdomains)
- reasoning: Why they are a competitor — mention what products/services they offer and why they compete with the source company
- similarity: How similar they are to the input company (0.0 to 1.0) — score based on industry match, product overlap, AND target customer overlap

Look for:
1. Direct competitors offering the SAME type of products/services to the SAME target customer
2. Indirect competitors solving the same problem differently for the SAME target customer
3. Both large established players AND smaller emerging competitors IN THE SAME NICHE

Return ONLY a JSON array. No markdown, no code fences, no explanations.
Example:
[
    {{
        "name": "CompanyA",
        "url": "https://www.companya.com",
        "reasoning": "Direct competitor selling men's casual wear with similar price range",
        "similarity": 0.85
    }}
]"""

# Scope-specific instructions injected into the prompt
_SCOPE_INSTRUCTIONS = {
    "local": (
        "GEOGRAPHIC SCOPE: LOCAL / INDIA ONLY\n"
        "You MUST return ONLY Indian brands — companies that are headquartered in India, "
        "founded in India, or primarily target Indian consumers.\n"
        "Examples of Indian brands: Manyavar, FabIndia, Peter England, Allen Solly, "
        "Bewakoof, Campus Sutra, etc.\n"
        "DO NOT include any international/global brand (e.g., Zara, H&M, Nike, Uniqlo, "
        "Calvin Klein). Even if they have Indian operations, they are NOT Indian brands.\n"
        "Focus on brands with Indian origins and strong presence in the Indian market."
    ),
    "global": (
        "GEOGRAPHIC SCOPE: INTERNATIONAL / GLOBAL ONLY\n"
        "You MUST return ONLY international/global brands — companies headquartered "
        "OUTSIDE India or brands with a global presence.\n"
        "DO NOT include any Indian-origin brand.\n"
        "Focus on well-known global competitors in the same industry."
    ),
}


def discover_competitors(
    business_profile: dict,
    source_url: str,
    profile_embedding=None,
    embedding_engine=None,
    max_competitors: int = MAX_COMPETITORS,
    scope: str = "global",
) -> list[dict]:
    """
    Discover and rank competitors using web search first,
    then validate and refine with LLM.

    Args:
        business_profile: Structured business profile of the input company.
        source_url: URL of the input company (to exclude from results).
        profile_embedding: Embedding vector of the input company profile.
        embedding_engine: EmbeddingEngine instance for similarity scoring.
        max_competitors: Maximum number of competitors to return.
        scope: "local" for Indian brands, "global" for international brands.

    Returns:
        List of competitor dictionaries sorted by ranking score.
    """
    source_domain = extract_domain(source_url)

    # Store all candidate sources
    all_candidates = []
    tracxn_competitors = []
    search_competitors = []

    # ── Step 1: Tracxn Search (LOCAL ONLY) ─────────────────────────────────────
    if scope == "local":
        logger.info("Discovering LOCAL competitors via Tracxn...")
        tracxn_competitors = _discover_via_tracxn(
            business_profile,
            source_domain,
            scope,
        )
        if tracxn_competitors:
            all_candidates.extend(tracxn_competitors)
            logger.info(
                "Tracxn discovered %d local candidates", len(tracxn_competitors)
            )
        else:
            logger.info("Tracxn found 0 local candidates, falling back to Tavily")

    # ── Step 2: Tavily Search ─────────────────────────────────────────────────
    logger.info("Discovering %s competitors via Tavily...", scope)
    search_competitors = _discover_via_tavily(
        business_profile,
        source_domain,
        scope,
    )
    if search_competitors:
        all_candidates.extend(search_competitors)
        logger.info(
            "Tavily discovered %d %s candidates", len(search_competitors), scope
        )

    # ── Step 3: LLM Fallback (if Tracxn/Tavily fail OR < 5 total candidates) ───
    if not all_candidates or (len(all_candidates) < 5):
        logger.info("Insufficient candidates, using LLM discovery fallback...")
        llm_fallback = _discover_via_llm(
            business_profile,
            source_url,
            source_domain,
            max_competitors * 2,  # Get more candidates
            scope,
        )
        all_candidates.extend(llm_fallback)
        all_candidates = _filter_candidate_pool(all_candidates, source_domain)
        logger.info(
            "LLM fallback discovered %d %s candidates", len(llm_fallback), scope
        )

    # ── LLM Validation: Validate all candidates ─────────────────────────────
    all_candidates = _filter_candidate_pool(all_candidates, source_domain)
    logger.info("Validating %s competitors via LLM...", scope)
    llm_validated, needs_fallback = _validate_via_llm(
        business_profile,
        source_url,
        source_domain,
        all_candidates,
        scope,
    )
    logger.info("LLM validated %d %s candidates", len(llm_validated), scope)

    # ── Step 4: LLM Fallback if validation failed (< 5 valid candidates) ──────
    if needs_fallback or len(llm_validated) < 5:
        logger.info("Validation insufficient (< 5 candidates), using LLM fallback...")
        llm_fallback = _discover_via_llm(
            business_profile,
            source_url,
            source_domain,
            max_competitors * 2,  # Get more candidates
            scope,
        )
        if llm_fallback:
            all_candidates.extend(llm_fallback)
            all_candidates = _filter_candidate_pool(all_candidates, source_domain)
            logger.info(
                "LLM fallback discovered %d %s candidates", len(llm_fallback), scope
            )

            # Re-validate with new candidates
            llm_validated, _ = _validate_via_llm(
                business_profile,
                source_url,
                source_domain,
                all_candidates,
                scope,
            )
            logger.info("Re-validated to %d %s candidates", len(llm_validated), scope)

    # ── Merge results (LLM takes priority with validation) ──────────────────
    merged = _merge_results(llm_validated, all_candidates, source_domain)

    # ── Semantic similarity scoring ────────────────────────────────────────
    if profile_embedding is not None and embedding_engine is not None:
        merged = _score_semantic_similarity(
            merged,
            profile_embedding,
            embedding_engine,
        )

    # ── Final ranking ──────────────────────────────────────────────────────
    ranked = _rank_candidates(merged)
    top_competitors = ranked[:max_competitors]

    logger.info(
        "Top %d %s competitors: %s",
        len(top_competitors),
        scope,
        [c["domain"] for c in top_competitors],
    )
    return top_competitors


@retry_with_backoff(max_retries=2, base_delay=2.0)
def _discover_via_llm(
    profile: dict,
    source_url: str,
    source_domain: str,
    max_competitors: int,
    scope: str = "global",
) -> list[dict]:
    """Use Groq via LangChain to identify competitors from business profile."""
    try:
        # Detect country from URL TLD and profile
        country_hint = _detect_country(source_url, source_domain, profile)

        # Select scope-specific instruction
        scope_instruction = _SCOPE_INSTRUCTIONS.get(scope, "")

        prompt = COMPETITOR_DISCOVERY_PROMPT.format(
            profile=json.dumps(profile, indent=2)[:4000],
            source_url=source_url,
            country_hint=country_hint,
            scope_instruction=scope_instruction,
            max_competitors=max_competitors,
        )

        # Use LangChain ChatGroq with fallback
        messages = [HumanMessage(content=prompt)]
        response = call_llm_with_fallback(messages, max_tokens=2048)

        text = response.content
        if not isinstance(text, str):
            text = str(text)
        result = safe_json_parse(text)

        # Handle both list and object with "competitors" key
        if isinstance(result, dict) and "competitors" in result:
            result = result["competitors"]

        if not isinstance(result, list):
            logger.warning("LLM returned non-list: %s", text[:200])
            return []

        # Normalize into our standard format with deduplication
        candidates = []
        seen_names: set[str] = set()
        seen_base_domains: set[str] = set()
        source_base = _get_base_domain(source_domain)

        for item in result:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            url = item.get("url", "")
            if not name or not url:
                continue

            domain = extract_domain(url)
            if (
                not domain
                or domain == source_domain
                or _is_excluded_candidate_domain(domain, url)
            ):
                continue

            # Deduplicate by normalized name and base domain
            name_key = name.strip().lower()
            base_domain = _get_base_domain(domain)
            if base_domain == source_base:
                continue
            if name_key in seen_names or base_domain in seen_base_domains:
                continue
            seen_names.add(name_key)
            seen_base_domains.add(base_domain)

            candidates.append(
                {
                    "domain": domain,
                    "url": url if url.startswith("http") else f"https://{domain}",
                    "name": name,
                    "frequency": 3,  # LLM results get a base frequency boost
                    "snippets": [item.get("reasoning", "")],
                    "titles": [name],
                    "llm_similarity": float(item.get("similarity", 0.5)),
                    "semantic_score": float(item.get("similarity", 0.5)),
                }
            )

        return candidates
    except Exception as e:
        logger.warning("LLM competitor discovery failed: %s", e)
        return []


def _validate_via_llm(
    profile: dict,
    source_url: str,
    source_domain: str,
    search_candidates: list[dict],
    scope: str = "global",
) -> tuple[list[dict], bool]:
    """
    Use LLM to validate, refine, and enrich search results.

    Takes search candidates and uses LLM to:
    - Validate relevance
    - Extract/confirm business details
    - Add reasoning and similarity scores
    - Filter out irrelevant results

    Args:
        profile: Business profile of the source company.
        source_url: URL of the source company.
        source_domain: Domain of the source company.
        search_candidates: List of candidate competitor dictionaries from web search.
        scope: "local" or "global" scope.

    Returns:
        Tuple of (validated competitor dictionaries, needs_fallback flag).
        needs_fallback is True if validation found <3 valid competitors or >50% are invalid.
    """
    if not search_candidates:
        return [], False

    try:
        country_hint = _detect_country(source_url, source_domain, profile)
        scope_instruction = _SCOPE_INSTRUCTIONS.get(scope, "")

        # Build a prompt that asks the LLM to validate the search candidates
        candidates_text = "\n".join(
            [
                f"- {c.get('name', 'Unknown')} ({c.get('domain', 'unknown')})"
                for c in search_candidates[:15]  # Limit to top 15 candidates
            ]
        )

        prompt = f"""You are a competitive intelligence analyst. Analyze these web search results and determine which are VALID competitors for the source brand.

BUSINESS PROFILE:
{json.dumps(profile, indent=2)[:3000]}

SOURCE COMPANY URL: {source_url}
{country_hint}
{scope_instruction}

SEARCH RESULTS:
{candidates_text}

CRITICAL REJECTION RULES - REJECT candidates if they are:
- NEWS sites (zeenews, timesofindia, hindustantimes, news portals)
- Q&A / KNOWLEDGE sites (zhihu, baidu zhidao, quora, wikipedia, stackexchange, ell.stackexchange)
- BLOG sites (medium, blogger, blogspot)
- GENERIC information domains (skincare.com, beauty.com, wellness.com - too broad, not a real brand)
- CLINICS / HOSPITALS (unless they sell consumer products in your niche)
- ANY site that is NOT a company selling products/services similar to source
- PREVIEW / LISTING / TRAVEL / ANALYTICS domains (vercel previews, Booking.com listings, Similarweb, Owler, etc.)

For EACH candidate above, determine:
1. Is this a VALID competitor (SAME industry, SAME niche products, SAME target customer)?
2. What is the SPECIFIC reason for rejection if invalid (e.g., "news site", "Q&A site", "different industry", "generic domain")?
3. What is their similarity to the source company (0.0 to 1.0) if valid?

Return ONLY a JSON array - NO markdown, NO extra text, NO wrapper objects:
[
    {{
        "name": "Company Name",
        "url": "https://website.com",
        "reasoning": "Why they are a competitor (1-2 sentences)",
        "similarity": 0.85,
        "is_relevant": true,
        "rejection_reason": null
    }}
]

IMPORTANT:
- Only include RELEVANT competitors (same industry niche, similar products)
- Return empty array [] if no valid competitors found
- DO NOT include the source company
- Be strict - only accept companies that sell similar products to the source brand
- Return ONLY the JSON array, no other text"""

        # Use LangChain ChatGroq with fallback
        messages = [HumanMessage(content=prompt)]
        response = call_llm_with_fallback(messages, max_tokens=3000, temperature=0.3)

        text = response.content
        if not isinstance(text, str):
            text = str(text)
        result = safe_json_parse(text)

        # Handle both list and object with "competitors" key
        if isinstance(result, dict) and "competitors" in result:
            result = result["competitors"]

        if not isinstance(result, list):
            logger.warning("LLM validation returned non-list: %s", text[:200])
            return search_candidates[
                :10
            ], True  # Fallback to top search results + trigger fallback

        # Process validated results
        validated = []
        for item in result:
            if not isinstance(item, dict):
                continue

            name = item.get("name", "")
            url = item.get("url", "")
            if not name or not url:
                continue

            domain = extract_domain(url)
            if (
                not domain
                or domain == source_domain
                or _is_excluded_candidate_domain(domain, url)
            ):
                continue

            # Only keep relevant candidates
            if not item.get("is_relevant", True):
                logger.debug("Skipping irrelevant candidate: %s", name)
                continue

            validated.append(
                {
                    "domain": domain,
                    "url": url if url.startswith("http") else f"https://{domain}",
                    "name": name,
                    "frequency": 2,  # Validation gets moderate frequency boost
                    "snippets": [item.get("reasoning", "")],
                    "titles": [name],
                    "llm_similarity": float(item.get("similarity", 0.5)),
                    "semantic_score": float(item.get("similarity", 0.5)),
                }
            )

        logger.info(
            "LLM validated %d out of %d search candidates",
            len(validated),
            len(search_candidates),
        )

        # Determine if we need fallback
        invalid_count = len(search_candidates) - len(validated)
        needs_fallback = len(validated) < 3

        return validated, needs_fallback
    except Exception as e:
        logger.warning("LLM validation failed: %s", e)
        # Fallback: return top search candidates and trigger fallback
        return search_candidates[:10], True


def _generate_search_queries(
    profile: dict,
    scope: str = "global",
) -> list[str]:
    """
    Use LLM to generate dynamic web search queries based on brand features.

    Args:
        profile: Business profile dictionary.
        scope: "local" for Indian brands, "global" for international brands.

    Returns:
        List of search query strings.
    """
    try:
        # Select scope-specific instruction
        scope_instruction = _SCOPE_INSTRUCTIONS.get(scope, "")

        prompt = f"""You are a competitive intelligence researcher. Based on the brand profile below, generate {5 if scope == "local" else 4} effective web search queries to find competitors.

BRAND PROFILE:
{json.dumps(profile, indent=2)[:3000]}

SCOPE: {scope.upper()}
{scope_instruction}

Generate search queries that will find direct competitors. Include:
- Brand name (if applicable)
- Industry and product categories
- Target customer
- Price range/positioning
- Geographic context (if local)

Rules:
1. For LOCAL (India): Include "India", "Indian", "online" in most queries
2. For GLOBAL: Use broader terms without geographic restriction
3. Each query should be 5-10 words
4. Include variations: direct brand searches, industry searches, product-specific searches
5. DO NOT include the source brand as a competitor

Return ONLY a JSON array of query strings:
[
    "query 1",
    "query 2",
    "query 3",
    "query 4",
    "query 5"
]

Example for a men's clothing brand (India):
[
    "muffynn men's clothing brand competitors India",
    "premium Indian menswear brands online",
    "best men's formal wear brands India 2024",
    "Indian ethnic fusion menswear companies",
    "urban professional men's clothing brands India"
]"""

        # Use LangChain ChatGroq with fallback
        messages = [HumanMessage(content=prompt)]
        response = call_llm_with_fallback(messages, max_tokens=1024, temperature=0.4)

        text = response.content
        if not isinstance(text, str):
            text = str(text)
        result = safe_json_parse(text)

        if not isinstance(result, list) or len(result) == 0:
            logger.warning("LLM failed to generate queries, using fallback")
            return _fallback_queries(profile, scope)

        # Ensure we have at least 3 queries
        queries = [q for q in result if isinstance(q, str) and q.strip()]
        if len(queries) < 3:
            queries = queries + _fallback_queries(profile, scope)[: (3 - len(queries))]

        logger.info("LLM generated %d %s search queries", len(queries), scope)
        return queries
    except Exception as e:
        logger.warning("LLM query generation failed: %s", e)
        return _fallback_queries(profile, scope)


def _fallback_queries(profile: dict, scope: str) -> list[str]:
    """
    Fallback hardcoded queries if LLM generation fails.
    """
    brand_name = profile.get("brand_name", "")
    industry = profile.get("industry", "")
    target_customer = profile.get("target_customer", "")
    products = profile.get("products_services", [])

    if scope == "local":
        geo_suffix = "India"
        geo_context = "Indian brands, local Indian market"
    else:
        geo_suffix = "global"
        geo_context = "worldwide international market"

    queries = []

    if brand_name:
        if industry and target_customer:
            queries.append(
                f'"{brand_name}" {industry} competitors for {target_customer} {geo_suffix}'
            )
        elif industry:
            queries.append(f'"{brand_name}" {industry} brand competitors {geo_suffix}')
        else:
            queries.append(f'"{brand_name}" competitors {geo_suffix}')

    if industry:
        industry_query_parts = [industry]
        if target_customer:
            industry_query_parts.append(f"for {target_customer}")
        if products and isinstance(products, list) and len(products) > 0:
            industry_query_parts.append(
                f"with {', '.join(str(p) for p in products[:2])}"
            )
        industry_query_parts.append(geo_context)
        queries.append(" ".join(industry_query_parts))

    if brand_name and industry:
        queries.append(f"{brand_name} and {industry} companies {geo_suffix}")

    return queries[:5]


def _simple_search_queries(profile: dict, scope: str) -> list[str]:
    """
    Generate simple, hardcoded web search queries.
    Uses basic brand + industry patterns without LLM involvement.
    """
    brand_name = profile.get("brand_name", "")
    industry = profile.get("industry", "")
    target_customer = profile.get("target_customer", "")
    products = profile.get("products_services", [])

    if scope == "local":
        geo_suffix = "India"
        geo_context = "Indian brands, local Indian market"
    else:
        geo_suffix = "global"
        geo_context = "worldwide international market"

    queries = []

    # Query 1: Brand-specific
    if brand_name:
        if industry:
            queries.append(f'"{brand_name}" {industry} competitors {geo_suffix}')
        else:
            queries.append(f'"{brand_name}" competitors {geo_suffix}')

    # Query 2: Industry-specific
    if industry:
        industry_query = industry
        if target_customer:
            industry_query += f" for {target_customer}"
        if products and isinstance(products, list) and len(products) > 0:
            industry_query += f" with {', '.join(str(p) for p in products[:2])}"
        industry_query += f" {geo_context}"
        queries.append(industry_query)

    # Query 3: Generic competitor search
    if brand_name and industry:
        queries.append(f"best {industry} brands {geo_suffix}")

    logger.info(
        "Generated %d simple search queries for %s %s",
        len(queries),
        brand_name or "unknown",
        scope,
    )
    return queries[:5]


def _discover_via_tavily(
    profile: dict,
    source_domain: str,
    scope: str = "global",
) -> list[dict]:
    """
    Tavily search for competitors.

    For GLOBAL scope: finds competitor listing pages and extracts competitors
    For LOCAL scope: also does the same (can be used as fallback after Tracxn)
    """
    brand_name = profile.get("brand_name", "")
    if not brand_name:
        logger.warning("No brand name found for Tavily search")
        return []

    generated_queries = _generate_search_queries(profile, scope)
    listing_queries = []
    if scope == "local":
        listing_queries = [
            f'site:tracxn.com "{brand_name}" competitors India',
            f'site:growjo.com "{brand_name}" competitors India',
            f'site:similarweb.com "{brand_name}" competitors India',
        ]
    else:
        listing_queries = [
            f'site:similarweb.com "{brand_name}" competitors',
            f'site:ahrefs.com "{brand_name}" competitors',
            f'site:growjo.com "{brand_name}" competitors',
        ]
    queries = list(dict.fromkeys(listing_queries + generated_queries))

    logger.info(
        "Tavily search queries for %s %s: %s",
        brand_name,
        scope,
        queries,
    )

    try:
        listing_pages: list[str] = []
        seen_listing_pages: set[str] = set()

        for query in queries:
            try:
                results = _tavily_search(query, max_results=8)

                for result in results:
                    href = result.get("href", "")
                    title = result.get("title", "").lower()
                    if not href or href in seen_listing_pages:
                        continue
                    if _is_competitor_listing_page(href, title):
                        seen_listing_pages.add(href)
                        listing_pages.append(href)
                        logger.info("Queued competitor listing page: %s", href)
                        if len(listing_pages) >= 5:
                            break

                if len(listing_pages) >= 5:
                    break

                time.sleep(SEARCH_RATE_LIMIT_DELAY)

            except Exception as e:
                err_str = str(e).lower()
                if "ratelimit" in err_str or "202" in err_str or "429" in err_str:
                    logger.warning("Tavily rate limited on '%s': %s", query, e)
                    break
                logger.warning("Tavily search failed for '%s': %s", query, e)

            time.sleep(SEARCH_RATE_LIMIT_DELAY)

    except Exception as e:
        logger.warning("Failed to initialize Tavily search flow: %s", e)
        return []

    aggregated_competitors: list[dict] = []
    seen_names: set[str] = set()
    for href in listing_pages:
        competitors = _crawl_and_extract_competitors(href, brand_name, scope)
        if competitors:
            for competitor in competitors:
                name_key = (competitor.get("name") or "").strip().lower()
                if name_key and name_key not in seen_names:
                    seen_names.add(name_key)
                    aggregated_competitors.append(competitor)

    for comp in aggregated_competitors:
        if comp.get("name") and not comp.get("domain"):
            website_url, domain = _find_company_website(comp["name"])
            if website_url:
                comp["url"] = website_url
                comp["domain"] = domain

    aggregated_competitors = _filter_candidate_pool(
        aggregated_competitors, source_domain
    )
    if aggregated_competitors:
        logger.info(
            "Resolved %d competitors from %d listing pages for %s",
            len(aggregated_competitors),
            len(listing_pages),
            brand_name,
        )
        return aggregated_competitors

    logger.info("No competitor listing pages found via Tavily for %s", brand_name)
    return []


def _discover_via_tracxn(
    profile: dict,
    source_domain: str,
    scope: str = "global",
) -> list[dict]:
    """
    Discover competitors via Tracxn platform.

    Uses Tavily to find tracxn.com page for the brand, then extracts
    competitors and alternatives from the Tracxn profile.

    Args:
        profile: Business profile dictionary.
        source_domain: Domain of the source company.
        scope: "local" for Indian brands, "global" for international brands.

    Returns:
        List of competitor dictionaries from Tracxn.
    """
    # Tracxn is only used for local competitors
    if scope == "global":
        logger.info("Tracxn search skipped for global scope")
        return []

    brand_name = profile.get("brand_name", "")
    if not brand_name:
        logger.warning("No brand name found for Tracxn search")
        return []

    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not configured, skipping Tracxn discovery")
        return []

    # Search for Tracxn page - more specific query
    tracxn_query = (
        f'site:tracxn.com "{brand_name}" competitors OR alternatives OR company profile'
    )
    logger.info("Searching Tracxn for %s (query: %s)", brand_name, tracxn_query)

    try:
        results = _tavily_search(tracxn_query, max_results=10)

        # Find the first tracxn.com result (but not login page)
        tracxn_url = None
        for result in results:
            href = result.get("href", "")
            if "tracxn.com" in href and "/login" not in href and "/signup" not in href:
                tracxn_url = href
                logger.info("Found Tracxn page: %s", tracxn_url)
                break

        if not tracxn_url:
            logger.info("No Tracxn page found for %s", brand_name)
            return []

        # Crawl the Tracxn page and extract competitors
        competitors = _crawl_and_extract_competitors(tracxn_url, brand_name, scope)

        # Try to find websites for each competitor
        for comp in competitors:
            if comp.get("name"):
                website_url, domain = _find_company_website(comp["name"])
                if website_url:
                    comp["url"] = website_url
                    comp["domain"] = domain

        # Filter out competitors without valid domains
        competitors = [
            c
            for c in competitors
            if c.get("domain")
            and not _is_excluded_candidate_domain(c.get("domain", ""), c.get("url", ""))
        ]

        return competitors
    except Exception as e:
        logger.warning("Tracxn discovery failed: %s", e)
        return []


def _extract_competitors_from_tracxn(
    page_text: str,
    source_brand: str,
    scope: str,
) -> list[dict]:
    """
    Extract competitor names from Tracxn page text.

    Looks for patterns like:
    - "Competitors: BrandA, BrandB, BrandC"
    - "Alternatives to Brand: X, Y, Z"
    """
    competitors = []
    seen = set()

    # Patterns to look for competitor sections
    import re

    # Look for "Competitors:" or "Alternatives:" patterns
    # Common patterns in Tracxn pages
    patterns = [
        r"Competitors?\s*[:\-]\s*([^\n]+)",
        r"Alternatives?\s*[:\-]\s*([^\n]+)",
        r"similar companies?\s*[:\-]\s*([^\n]+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, page_text, re.IGNORECASE)
        for match in matches:
            # Split by comma, semicolon, or "and"
            parts = re.split(r"[,;]|\band\b", match)
            for part in parts:
                name = part.strip()
                # Clean up the name
                name = re.sub(r"[^a-zA-Z0-9\s\-&]", "", name).strip()
                if (
                    len(name) > 2
                    and name.lower() != source_brand.lower()
                    and name not in seen
                ):
                    seen.add(name)
                    competitors.append(
                        {
                            "domain": "",  # Will be resolved later
                            "url": "",
                            "name": name,
                            "frequency": 4,  # Tracxn results get high frequency boost
                            "snippets": ["Found via Tracxn"],
                            "titles": [name],
                            "llm_similarity": 0.7,
                            "semantic_score": 0.7,
                        }
                    )

    logger.info(
        "Extracted %d competitors from Tracxn for %s", len(competitors), source_brand
    )
    return competitors


_NON_BRAND_DOMAINS = {
    # Design / awards / portfolio sites
    "awwwards.com", "www.awwwards.com",
    "dribbble.com", "www.dribbble.com",
    "behance.net", "www.behance.net",
    "deviantart.com",
    # Developer / platform / hosting sites
    "developers.google.com", "developer.apple.com",
    "github.com", "www.github.com",
    "gitlab.com",
    "stackoverflow.com", "www.stackoverflow.com",
    # Website builders / SaaS platforms (not brands selling products)
    "wix.com", "www.wix.com",
    "wordpress.com", "www.wordpress.com",
    "wordpress.org",
    "shopify.com", "www.shopify.com",
    "squarespace.com", "www.squarespace.com",
    "webflow.com", "www.webflow.com",
    "godaddy.com", "www.godaddy.com",
    "notion.so", "notion.site",
    "vercel.com", "www.vercel.com",
    "netlify.com", "www.netlify.com",
    # Documentation / tools sites
    "readthedocs.io",
    "docs.google.com",
    "multicollab.com", "docs.multicollab.com",
    "realstack.com",
    # Art / niche / unrelated sites
    "streetartcities.com",
    "deepdive.headline.com",
    # Social / media
    "reddit.com", "www.reddit.com",
    "pinterest.com", "www.pinterest.com",
    "tumblr.com",
    "tiktok.com", "www.tiktok.com",
    "youtube.com", "www.youtube.com",
    "twitch.tv",
    # Marketplaces / aggregators (already in _EXCLUDED but reinforce)
    "amazon.com", "amazon.in", "www.amazon.com", "www.amazon.in",
    "ebay.com", "www.ebay.com",
    "etsy.com", "www.etsy.com",
    "alibaba.com", "aliexpress.com",
    "flipkart.com", "www.flipkart.com",
}


def _is_relevant_domain(domain: str) -> bool:
    """
    Quick filter to reject obviously non-relevant domains.
    Returns True if the domain should be kept, False if it should be rejected.
    """
    if not domain:
        return False

    domain_lower = domain.lower()

    # Check against hardcoded non-brand domains
    if domain_lower in _NON_BRAND_DOMAINS:
        return False

    # Reject news sites
    if any(
        x in domain_lower
        for x in ["news", "times", "herald", "post", "gazette", "zeenews"]
    ):
        return False

    # Reject Q&A / knowledge sites
    if any(
        x in domain_lower
        for x in ["zhihu", "quora", "baidu", "wiki", "stackexchange", "zhidao"]
    ):
        return False

    # Reject blog sites
    if any(x in domain_lower for x in ["blog", "medium", "blogger"]):
        return False

    # Reject docs.* subdomains
    if domain_lower.startswith("docs.") or domain_lower.startswith("developers."):
        return False

    # Reject generic one-word .com/.in domains (too generic - not real brands)
    if domain_lower.count(".") == 1:  # single-level domain like skincare.com
        generic_patterns = [
            "skincare",
            "beauty",
            "fashion",
            "health",
            "wellness",
            "clinic",
            "hospital",
        ]
        if any(p in domain_lower for p in generic_patterns):
            return False

    return True


def _crawl_and_extract_competitors(
    page_url: str,
    brand_name: str,
    scope: str,
) -> list[dict]:
    """
    Crawl a page and extract competitor names AND their website URLs
    from "Competitors" or "Alternatives" sections.

    On listing pages (Tracxn, etc.), competitor entries often have anchor
    links that point to either:
      - The competitor's Tracxn profile (internal link)
      - The competitor's actual website (external link)
    We extract both the name and any external website URL found nearby.

    Args:
        page_url: URL of the page to crawl
        brand_name: Name of the source brand
        scope: "local" or "global" scope

    Returns:
        List of competitor dictionaries with names and optional URLs/domains.
    """
    from crawler.crawler import AdaptiveCrawler

    try:
        crawler = AdaptiveCrawler(max_pages=1, max_depth=0)
        pages = _run_async(crawler.crawl(page_url))

        if not pages:
            logger.warning("Failed to crawl page: %s", page_url)
            return []

        page_text = "\n".join(
            [p.cleaned_text if hasattr(p, "cleaned_text") else str(p) for p in pages]
        )
        raw_html = "\n".join(
            [p.raw_html if hasattr(p, "raw_html") else "" for p in pages]
        )

        competitors = []
        seen = set()

        def add_candidate(
            candidate_name: str, snippet: str,
            website_url: str = "", website_domain: str = "",
        ) -> None:
            normalized = _normalize_company_name(candidate_name)
            if not _looks_like_company_name(normalized, brand_name):
                return
            name_key = normalized.lower()
            if name_key in seen:
                # If we already have this candidate but now found a website, update it
                if website_url:
                    for comp in competitors:
                        if comp.get("name", "").lower() == name_key and not comp.get("domain"):
                            comp["url"] = website_url
                            comp["domain"] = website_domain
                return
            seen.add(name_key)
            competitors.append(
                {
                    "domain": website_domain,
                    "url": website_url,
                    "name": normalized,
                    "frequency": 4,
                    "snippets": [snippet],
                    "titles": [normalized],
                    "llm_similarity": 0.7,
                    "semantic_score": 0.7,
                }
            )

        # ── Parse HTML for competitor entries ─────────────────────────────
        listing_domain = urlparse(page_url).netloc.lower()
        is_listing_site = any(
            d in listing_domain for d in _COMPETITOR_LISTING_DOMAINS
        )

        try:
            soup = BeautifulSoup(raw_html, "html.parser")

            if is_listing_site:
                # On listing sites (Tracxn, etc.), look for anchor links that
                # point to company profiles or external websites.
                # Build a map: competitor_name -> external_website_url
                name_to_website: dict[str, tuple[str, str]] = {}

                for anchor in soup.find_all("a", href=True):
                    href = anchor.get("href", "").strip()
                    anchor_text = " ".join(anchor.get_text(" ", strip=True).split())
                    if len(anchor_text) < 2 or len(anchor_text) > 60:
                        continue

                    parsed = urlparse(href)
                    href_domain = (parsed.netloc or "").lower()
                    href_lower = href.lower()

                    # Case 1: Link points to an external website (the competitor's site)
                    if (
                        href.startswith("http")
                        and href_domain
                        and listing_domain not in href_domain
                        and not _is_excluded_candidate_domain(href_domain, href)
                        and _is_relevant_domain(href_domain)
                    ):
                        name_to_website[anchor_text.lower()] = (href, href_domain)

                    # Case 2: Internal profile link (e.g., /d/companies/bewakoof/...)
                    if any(
                        token in href_lower
                        for token in ("/company", "/companies", "/d/companies", "/profile")
                    ):
                        add_candidate(
                            anchor_text,
                            f"Found via listing page link: {page_url}",
                        )

                # Now try to match extracted names to any external URLs found on the page
                for comp in competitors:
                    if comp.get("domain"):
                        continue  # Already has a website
                    name_lower = comp.get("name", "").lower()
                    for text_key, (url, domain) in name_to_website.items():
                        # Fuzzy match: name appears in anchor text or vice versa
                        if name_lower in text_key or text_key in name_lower:
                            comp["url"] = url
                            comp["domain"] = domain
                            break

            else:
                # Non-listing page: original anchor-based extraction
                for anchor in soup.find_all("a", href=True):
                    href = anchor.get("href", "")
                    anchor_text = " ".join(anchor.get_text(" ", strip=True).split())
                    if len(anchor_text) < 2:
                        continue
                    if _is_competitor_listing_page(page_url, anchor_text):
                        add_candidate(
                            anchor_text, f"Found via listing page link: {page_url}"
                        )
        except Exception as e:
            logger.debug(
                "Anchor-based competitor extraction failed for %s: %s", page_url, e
            )

        # ── Text-pattern extraction ───────────────────────────────────────
        patterns = [
            r"Competitors?\s*[:\-]\s*([^\n]+)",
            r"Alternatives?\s*[:\-]\s*([^\n]+)",
            r"similar companies?\s*[:\-]\s*([^\n]+)",
            r"companies like\s+([^\n]+)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                parts = re.split(r"[,;]|\band\b", match)
                for part in parts:
                    add_candidate(part, f"Found via text pattern on {page_url}")

        # ── Tracxn-specific: capture short lines after competitor heading ─
        if "tracxn.com" in page_url.lower():
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            for idx, line in enumerate(lines):
                if re.search(
                    r"competitors?|alternatives?|similar companies?", line, re.I
                ):
                    for neighbor in lines[idx + 1 : idx + 15]:
                        if re.search(
                            r"funding|revenue|employees|founded|hq|overview",
                            neighbor,
                            re.I,
                        ):
                            continue
                        add_candidate(
                            neighbor, f"Found near competitor heading on {page_url}"
                        )

        competitors = competitors[:12]

        logger.info(
            "Extracted %d competitors from %s for %s (with websites: %d)",
            len(competitors),
            page_url,
            brand_name,
            sum(1 for c in competitors if c.get("domain")),
        )
        return competitors
    except Exception as e:
        logger.warning("Failed to crawl and extract competitors: %s", e)
        return []


def _find_company_website(company_name: str) -> tuple[str, str]:
    """
    Find the official website for a company name using Tavily search.

    Args:
        company_name: Name of the company to find

    Returns:
        Tuple of (website_url, domain), or empty strings if not found
    """
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not configured, skipping website search")
        return "", ""

    try:
        # Search for company name + "official website"
        query = f'"{company_name}" official website'
        results = _tavily_search(query, max_results=10)

        for result in results:
            href = result.get("href", "")
            if href and "http" in href:
                domain = extract_domain(href)
                if not domain:
                    continue
                # Reject social media, excluded domains, and non-brand domains
                if any(
                    x in href
                    for x in [
                        "facebook.com",
                        "twitter.com",
                        "instagram.com",
                        "linkedin.com",
                        "wikipedia.org",
                        "quora.com",
                    ]
                ):
                    continue
                if _is_excluded_candidate_domain(domain, href):
                    continue
                if not _is_relevant_domain(domain):
                    continue
                return href, href.replace("https://", "").replace(
                    "http://", ""
                ).split("/")[0]

        # If no official website found, try just the company name
        query = f'"{company_name}"'
        results = _tavily_search(query, max_results=10)

        for result in results:
            href = result.get("href", "")
            if href and "http" in href:
                domain = (
                    href.replace("https://", "").replace("http://", "").split("/")[0]
                )
                if (
                    domain
                    and not any(
                        x in domain
                        for x in [
                            "facebook.com",
                            "twitter.com",
                            "instagram.com",
                            "linkedin.com",
                            "wikipedia.org",
                            "quora.com",
                        ]
                    )
                    and not _is_excluded_candidate_domain(domain, href)
                    and _is_relevant_domain(domain)
                ):
                    return href, domain
    except Exception as e:
        logger.warning("Failed to find website for %s: %s", company_name, e)

    return "", ""


def _aggregate_domains(
    results: list[dict],
    exclude_domain: str,
) -> list[dict]:
    """Aggregate search results by domain."""
    domain_data: dict[str, dict] = {}

    excluded_domains = {
        exclude_domain,
        "wikipedia.org",
        "reddit.com",
        "quora.com",
        "youtube.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "instagram.com",
        "tiktok.com",
        "medium.com",
        "forbes.com",
        "bloomberg.com",
        "techcrunch.com",
        "crunchbase.com",
        "g2.com",
        "capterra.com",
        "trustpilot.com",
        "glassdoor.com",
        "amazon.com",
        "amazon.in",
        "google.com",
        "bing.com",
        "flipkart.com",
        "myntra.com",
        "ajio.com",
        "snapdeal.com",
        "nykaa.com",
        "meesho.com",
        "ebay.com",
        "etsy.com",
        "alibaba.com",
        "aliexpress.com",
        "walmart.com",
        "pinterest.com",
        "yelp.com",
        "tripadvisor.com",
        "indeed.com",
        "naukri.com",
    }

    for result in results:
        href = result.get("href", "")
        if not href:
            continue

        domain = extract_domain(href)
        if not domain or domain in excluded_domains:
            continue

        if domain not in domain_data:
            domain_data[domain] = {
                "domain": domain,
                "url": f"https://{domain}",
                "frequency": 0,
                "snippets": [],
                "titles": [],
                "semantic_score": 0.0,
            }

        domain_data[domain]["frequency"] += 1
        snippet = result.get("body", "")
        if snippet and len(domain_data[domain]["snippets"]) < 5:
            domain_data[domain]["snippets"].append(snippet)
        title = result.get("title", "")
        if title and title not in domain_data[domain]["titles"]:
            domain_data[domain]["titles"].append(title)

    return list(domain_data.values())


def _merge_results(
    llm_candidates: list[dict],
    ddg_candidates: list[dict],
    source_domain: str,
) -> list[dict]:
    """Merge LLM-validated and search results, deduplicating by domain and name.

    When LLM-validated candidates exist, they are prioritised and raw search
    candidates are only used to fill gaps.  An additional _is_relevant_domain
    check prevents non-brand domains from leaking in.
    """
    seen_base_domains: set[str] = set()
    seen_names: set[str] = set()
    merged: list[dict] = []

    def _try_add(c: dict) -> bool:
        domain = c.get("domain", "")
        name_key = c.get("name", "").strip().lower()
        base_domain = _get_base_domain(domain) if domain else ""
        if (
            domain
            and domain != source_domain
            and not _is_excluded_candidate_domain(domain, c.get("url", ""))
            and _is_relevant_domain(domain)
            and base_domain not in seen_base_domains
            and name_key not in seen_names
        ):
            seen_base_domains.add(base_domain)
            if name_key:
                seen_names.add(name_key)
            merged.append(c)
            return True
        return False

    # LLM-validated results first (higher priority)
    for c in llm_candidates:
        _try_add(c)

    # Only add raw search candidates if LLM validation returned very few
    if len(merged) < 3:
        for c in ddg_candidates:
            _try_add(c)

    return merged


def _score_semantic_similarity(
    candidates: list[dict],
    profile_embedding,
    embedding_engine,
) -> list[dict]:
    """Score each candidate's snippet text against the source profile."""
    for candidate in candidates:
        combined_text = " ".join(candidate.get("snippets", []))
        if combined_text.strip():
            candidate_embedding = embedding_engine.encode_single(combined_text)
            score = embedding_engine.compute_similarity(
                profile_embedding,
                candidate_embedding,
            )
            candidate["semantic_score"] = max(
                candidate.get("semantic_score", 0.0),
                float(score),
            )

    return candidates


def _rank_candidates(candidates: list[dict]) -> list[dict]:
    """Rank candidates by combined score."""
    if not candidates:
        return []

    max_freq = max(c.get("frequency", 1) for c in candidates) or 1
    for c in candidates:
        norm_freq = c.get("frequency", 1) / max_freq
        semantic = c.get("semantic_score", 0.0)
        c["combined_score"] = 0.4 * norm_freq + 0.6 * semantic

    candidates.sort(key=lambda x: x["combined_score"], reverse=True)
    return candidates


# ── Post-crawl industry relevance validation ─────────────────────────────────

RELEVANCE_VALIDATION_PROMPT = """You are a competitive intelligence analyst. Determine whether the CANDIDATE company is a RELEVANT competitor to the SOURCE company.

SOURCE COMPANY:
- Industry: {source_industry}
- Products/Services: {source_products}
- Target Customer: {source_target}

CANDIDATE COMPANY:
- Name: {candidate_name}
- Industry: {candidate_industry}
- Products/Services: {candidate_products}
- Target Customer: {candidate_target}

A competitor is RELEVANT only if:
1. They operate in the SAME specific industry/niche (not just a broadly related one)
2. They sell similar types of products/services
3. They target a similar customer segment

A competitor is IRRELEVANT if:
- They are in a completely different industry (e.g., AI/tech vs clothing)
- They target a fundamentally different customer (e.g., women's fashion vs men's fashion)
- Their products/services don't overlap meaningfully with the source company

Return ONLY a JSON object:
{{"relevant": true/false, "reason": "One sentence explanation"}}"""


def validate_competitor_relevance(
    source_profile: dict,
    competitor_profile: dict,
) -> dict:
    """
    Validate whether a competitor is actually relevant to the source company
    by comparing their extracted business profiles via LLM.

    Args:
        source_profile: Business profile of the source company.
        competitor_profile: Business profile of the competitor.

    Returns:
        Dict with 'relevant' (bool) and 'reason' (str).
    """
    try:
        source_products = source_profile.get("products_services", [])
        candidate_products = competitor_profile.get("products_services", [])

        prompt = RELEVANCE_VALIDATION_PROMPT.format(
            source_industry=source_profile.get("industry", "Unknown"),
            source_products=", ".join(source_products)
            if isinstance(source_products, list)
            else str(source_products),
            source_target=source_profile.get("target_customer", "Unknown"),
            candidate_name=competitor_profile.get("brand_name", "Unknown"),
            candidate_industry=competitor_profile.get("industry", "Unknown"),
            candidate_products=", ".join(candidate_products)
            if isinstance(candidate_products, list)
            else str(candidate_products),
            candidate_target=competitor_profile.get("target_customer", "Unknown"),
        )

        # Use LangChain ChatGroq with fallback
        messages = [HumanMessage(content=prompt)]
        response = call_llm_with_fallback(messages, max_tokens=256, temperature=0.1)

        text = response.content
        if not isinstance(text, str):
            text = str(text)
        result = safe_json_parse(text)

        if result and isinstance(result, dict) and "relevant" in result:
            logger.info(
                "Relevance check for %s: %s — %s",
                competitor_profile.get("brand_name", "Unknown"),
                result.get("relevant"),
                result.get("reason", ""),
            )
            return result

        # If parsing fails, reject rather than silently accepting bad competitors.
        logger.warning(
            "Could not parse relevance response, rejecting candidate: %s", text[:200]
        )
        return {"relevant": False, "reason": "Could not validate relevance reliably"}

    except Exception as e:
        logger.warning("Relevance validation failed: %s — rejecting candidate", e)
        return {"relevant": False, "reason": f"Validation error: {e}"}
