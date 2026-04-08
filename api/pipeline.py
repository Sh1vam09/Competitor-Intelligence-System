"""
Full Pipeline Orchestrator.

Orchestrates the complete competitor intelligence pipeline:
    1. Crawl the input website
    2. Process content (clean text, extract DOM features)
    3. Visual analysis via OpenRouter vision
    4. Structured business extraction via OpenRouter
    5. Generate embeddings
    6. Discover competitors via Tavily
    7. Crawl and analyze each competitor
    8. Generate comparative intelligence analysis
    9. Generate PDF report
"""

import asyncio
import json
import time
import traceback
from typing import Optional, Callable

from crawler.crawler import AdaptiveCrawler
from processing.text_processor import remove_boilerplate, chunk_text
from processing.dom_analyzer import extract_dom_features
from vision.visual_analyzer import analyze_screenshot
from extraction.business_extractor import extract_business_profile
from embedding.embedder import EmbeddingEngine
from competitor_discovery.discovery import (
    discover_competitors,
    validate_competitor_relevance,
)
from analysis.comparator import (
    generate_comparative_analysis,
    generate_executive_summary,
)
from reporting.report_generator import generate_report
from database.models import Company, Competitor, Report
from database.session import get_db
from utils.config import (
    MAX_COMPETITORS,
    MIN_SIMILARITY_THRESHOLD,
    MAX_COMPETITOR_CANDIDATES,
    MAX_LOCAL_COMPETITORS,
    MAX_GLOBAL_COMPETITORS,
    MAX_LOCAL_CANDIDATES,
    MAX_GLOBAL_CANDIDATES,
    COMPETITOR_CRAWL_DELAY,
    COMPETITOR_CRAWL_CONCURRENCY,
)
from utils.helpers import extract_domain
from utils.logger import get_logger

logger = get_logger(__name__)


def _has_target_segment_conflict(source_profile: dict, competitor_profile: dict) -> bool:
    """Reject obvious audience mismatches such as men's vs women's brands."""
    source_blob = " ".join(
        str(source_profile.get(key, ""))
        for key in ("industry", "target_customer", "positioning_statement")
    ).lower()
    competitor_blob = " ".join(
        str(competitor_profile.get(key, ""))
        for key in ("industry", "target_customer", "positioning_statement")
    ).lower()

    mens_terms = (" men", " men's", "mens", "male", "gentlemen", "guys")
    womens_terms = (" women", " women's", "womens", "female", "ladies", "girls")

    source_mens = any(term in source_blob for term in mens_terms)
    source_womens = any(term in source_blob for term in womens_terms)
    competitor_mens = any(term in competitor_blob for term in mens_terms)
    competitor_womens = any(term in competitor_blob for term in womens_terms)

    if source_mens and competitor_womens and not competitor_mens:
        return True
    if source_womens and competitor_mens and not competitor_womens:
        return True
    return False


def _dedupe_competitors_across_scopes(
    local_candidates: list[dict],
    global_candidates: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Prevent the same competitor from appearing in both local and global pools."""
    def base_domain(value: str) -> str:
        parts = (value or "").lower().split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else value.lower()

    local_seen_domains = set()
    local_seen_names = set()

    for candidate in local_candidates:
        domain = extract_domain(candidate.get("url", "") or candidate.get("domain", ""))
        name = (candidate.get("name") or "").strip().lower()
        if domain:
            local_seen_domains.add(base_domain(domain))
        if name:
            local_seen_names.add(name)

    filtered_global = []
    for candidate in global_candidates:
        domain = extract_domain(candidate.get("url", "") or candidate.get("domain", ""))
        name = (candidate.get("name") or "").strip().lower()
        if domain and base_domain(domain) in local_seen_domains:
            continue
        if name and name in local_seen_names:
            continue
        filtered_global.append(candidate)

    return local_candidates, filtered_global


class PipelineOrchestrator:
    """
    Coordinates the full intelligence pipeline from URL to report.
    Tracks progress via a status callback for real-time updates.
    """

    def __init__(self, status_callback: Optional[Callable] = None):
        """
        Initialize the pipeline.

        Args:
            status_callback: Optional callable(status_str) for progress updates.
        """
        self.status_callback = status_callback or (lambda s: None)
        self.embedding_engine = EmbeddingEngine()
        self.embedding_engine.create_index()

    def _update_status(self, status: str) -> None:
        """Update pipeline status."""
        logger.info("Pipeline: %s", status)
        self.status_callback(status)

    async def run(self, url: str) -> dict:
        """
        Execute the full pipeline for a given URL.

        Args:
            url: The website URL to analyze.

        Returns:
            Dictionary with company_id, report_path, and status.
        """
        try:
            pipeline_start = time.time()
            # ── Step 1: Crawl the input website ────────────────────────────
            self._update_status("Crawling website...")
            crawler = AdaptiveCrawler()
            pages = await crawler.crawl(url)

            if not pages:
                raise ValueError(f"No pages could be crawled from {url}")

            self._update_status(f"Crawled {len(pages)} pages")

            # ── Step 2: Process content ────────────────────────────────────
            self._update_status("Processing content...")
            all_text_chunks, combined_dom_features = self._process_pages(pages)

            if not all_text_chunks:
                raise ValueError("No usable text content extracted")

            # ── Step 3: Visual analysis ────────────────────────────────────
            self._update_status("Analyzing visual design...")
            visual_profile = self._analyze_visuals(pages)

            # ── Step 4: Business extraction ────────────────────────────────
            self._update_status("Extracting business profile via OpenRouter...")
            business_profile = extract_business_profile(
                all_text_chunks, combined_dom_features
            )

            brand_name = business_profile.get("brand_name", extract_domain(url))
            self._update_status(f"Profile extracted: {brand_name}")

            # ── Step 5: Generate embeddings ────────────────────────────────
            self._update_status("Generating embeddings...")
            profile_embedding = self.embedding_engine.build_profile_embedding(
                business_profile
            )

            # ── Step 6: Save to database ───────────────────────────────────
            self._update_status("Saving company profile...")
            db = get_db()
            try:
                company = self._save_company(
                    db,
                    url,
                    brand_name,
                    business_profile,
                    visual_profile,
                    combined_dom_features,
                    profile_embedding,
                )

                # Add to FAISS index
                self.embedding_engine.add_to_index(
                    profile_embedding,
                    {
                        "company_id": company.id,
                        "name": brand_name,
                        "url": url,
                    },
                )

                # ── Step 7a: Discover LOCAL competitors ────────────────────
                self._update_status("Discovering local (Indian) competitors...")
                local_candidates = discover_competitors(
                    business_profile=business_profile,
                    source_url=url,
                    profile_embedding=profile_embedding,
                    embedding_engine=self.embedding_engine,
                    max_competitors=MAX_LOCAL_CANDIDATES,
                    scope="local",
                )
                logger.info("Found %d local candidates", len(local_candidates))

                # ── Pause between scopes to avoid search rate limits ───────
                await asyncio.sleep(5)

                # ── Step 7b: Discover GLOBAL competitors ───────────────────
                self._update_status("Discovering global (international) competitors...")
                global_candidates = discover_competitors(
                    business_profile=business_profile,
                    source_url=url,
                    profile_embedding=profile_embedding,
                    embedding_engine=self.embedding_engine,
                    max_competitors=MAX_GLOBAL_CANDIDATES,
                    scope="global",
                )
                logger.info("Found %d global candidates", len(global_candidates))

                local_candidates, global_candidates = _dedupe_competitors_across_scopes(
                    local_candidates,
                    global_candidates,
                )
                logger.info(
                    "After cross-scope dedupe: %d local, %d global candidates",
                    len(local_candidates),
                    len(global_candidates),
                )

                all_competitor_data = []

                # Clear old competitors for fresh re-analysis
                db.query(Competitor).filter_by(
                    parent_company_id=company.id,
                ).delete()
                db.commit()

                # ── Step 8a: Analyze LOCAL competitors ─────────────────────
                if local_candidates:
                    self._update_status(
                        f"Analyzing {len(local_candidates)} local competitors..."
                    )
                    local_data = await self._analyze_competitors(
                        db,
                        company,
                        local_candidates,
                        scope="local",
                        max_valid=MAX_LOCAL_COMPETITORS,
                    )
                    all_competitor_data.extend(local_data)
                else:
                    self._update_status("No local competitors discovered.")

                # ── Step 8b: Analyze GLOBAL competitors ────────────────────
                if global_candidates:
                    self._update_status(
                        f"Analyzing {len(global_candidates)} global competitors..."
                    )
                    global_data = await self._analyze_competitors(
                        db,
                        company,
                        global_candidates,
                        scope="global",
                        max_valid=MAX_GLOBAL_COMPETITORS,
                    )
                    all_competitor_data.extend(global_data)
                else:
                    self._update_status("No global competitors discovered.")

                # ── Step 9: Comparative analysis ───────────────────────────
                if all_competitor_data:
                    self._update_status("Generating comparative intelligence...")
                    comparison = generate_comparative_analysis(
                        input_profile=business_profile,
                        input_visual_profile=visual_profile,
                        competitor_profiles=all_competitor_data,
                    )

                    executive_summary = generate_executive_summary(
                        input_profile=business_profile,
                        comparison=comparison,
                        num_competitors=len(all_competitor_data),
                    )
                else:
                    comparison = {}
                    executive_summary = "No competitors were discovered for analysis."

                # ── Step 10: Generate PDF report ───────────────────────────
                self._update_status("Generating PDF report...")

                # Split saved competitors by scope for report
                local_for_report = []
                global_for_report = []
                for comp in (
                    db.query(Competitor)
                    .filter_by(parent_company_id=company.id)
                    .order_by(Competitor.similarity_score.desc())
                    .all()
                ):
                    comp_data = {
                        "name": comp.name or "Unknown",
                        "url": comp.url,
                        "similarity_score": comp.similarity_score or 0.0,
                        "profile": comp.get_profile(),
                        "visual_profile": comp.get_visual_profile(),
                    }
                    if comp.scope == "local":
                        local_for_report.append(comp_data)
                    else:
                        global_for_report.append(comp_data)

                competitors_for_report = local_for_report + global_for_report

                report_path = generate_report(
                    company_name=brand_name,
                    company_url=url,
                    business_profile=business_profile,
                    visual_profile=visual_profile,
                    dom_features=combined_dom_features,
                    competitors=competitors_for_report,
                    comparison=comparison,
                    executive_summary=executive_summary,
                    local_competitors=local_for_report,
                    global_competitors=global_for_report,
                )

                # Save report to database
                report = Report(
                    company_id=company.id,
                    report_json=json.dumps(comparison),
                    report_pdf_path=report_path,
                )
                db.add(report)
                db.commit()

                # Save vector index (Pinecone is cloud-based and persists automatically)
                self.embedding_engine.save_index(f"company_{company.id}")

                pipeline_duration = time.time() - pipeline_start
                logger.info(
                    "Pipeline completed in %.1fs — %d competitors found for %s",
                    pipeline_duration,
                    len(competitors_for_report),
                    brand_name,
                )
                self._update_status(
                    f"Analysis complete! ({len(competitors_for_report)} competitors, {pipeline_duration:.0f}s)"
                )
                return {
                    "status": "completed",
                    "company_id": company.id,
                    "company_name": brand_name,
                    "report_path": report_path,
                    "competitors_found": len(competitors_for_report),
                    "duration_seconds": round(pipeline_duration, 1),
                }
            finally:
                db.close()

        except Exception as e:
            logger.error("Pipeline failed: %s\n%s", e, traceback.format_exc())
            self._update_status(f"Failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
            }

    def _process_pages(self, pages) -> tuple[list[str], dict]:
        """Process crawled pages: clean text, chunk, extract DOM."""
        all_chunks = []
        combined_dom = {}

        for i, page in enumerate(pages):
            # Clean and chunk text
            cleaned = remove_boilerplate(page.raw_html)
            if cleaned:
                chunks = chunk_text(cleaned)
                all_chunks.extend(chunks)

            # Extract DOM features (aggregate from first few pages)
            if i < 5:
                page_dom = extract_dom_features(page.raw_html)
                page.dom_structure_features = page_dom
                if not combined_dom:
                    combined_dom = page_dom
                else:
                    # Sum numeric features, OR boolean features
                    for k, v in page_dom.items():
                        if isinstance(v, bool):
                            combined_dom[k] = combined_dom.get(k, False) or v
                        elif isinstance(v, (int, float)):
                            combined_dom[k] = combined_dom.get(k, 0) + v

        return all_chunks, combined_dom

    def _analyze_visuals(self, pages) -> dict:
        """Run visual analysis on the first available screenshot."""
        for page in pages:
            if page.screenshot_path:
                try:
                    return analyze_screenshot(page.screenshot_path)
                except Exception as e:
                    logger.warning("Visual analysis failed: %s", e)

        from vision.visual_analyzer import _empty_visual_profile

        return _empty_visual_profile()

    def _save_company(
        self,
        db,
        url,
        name,
        profile,
        visual_profile,
        dom_features,
        embedding,
    ) -> Company:
        """Save or update the company in the database."""
        # Check for existing
        existing = db.query(Company).filter_by(url=url).first()
        if existing:
            existing.name = name
            existing.industry = profile.get("industry")
            existing.json_profile = json.dumps(profile)
            existing.visual_profile = json.dumps(visual_profile)
            existing.dom_features = json.dumps(dom_features)
            existing.embedding_vector = EmbeddingEngine.embedding_to_bytes(embedding)
            db.commit()
            return existing

        company = Company(
            url=url,
            name=name,
            industry=profile.get("industry"),
            json_profile=json.dumps(profile),
            visual_profile=json.dumps(visual_profile),
            dom_features=json.dumps(dom_features),
            embedding_vector=EmbeddingEngine.embedding_to_bytes(embedding),
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    async def _analyze_single_competitor(
        self,
        db,
        parent_company: Company,
        candidate: dict,
        scope: str,
        source_profile: dict,
        seen_names: set,
        max_valid: int,
        parent_embedding,
        idx: int,
        total: int,
    ) -> dict:
        """
        Analyze a single competitor (helper function for parallel processing).

        Returns:
            Dict with 'success' (bool), 'data' (dict), or 'error' (str).
        """
        comp_url = candidate.get("url", "")
        comp_domain = candidate.get("domain", "")

        try:
            # Crawl competitor
            comp_crawler = AdaptiveCrawler(max_pages=15, max_depth=2)
            comp_pages = await comp_crawler.crawl(comp_url)

            if not comp_pages:
                return {"success": False, "error": f"No pages crawled: {comp_url}"}

            # Process content
            comp_chunks, comp_dom = self._process_pages(comp_pages)
            if not comp_chunks:
                return {"success": False, "error": f"No content extracted: {comp_url}"}

            # Visual analysis
            comp_visual = self._analyze_visuals(comp_pages)

            # Business extraction (retries 3× internally, then raises)
            comp_profile = extract_business_profile(comp_chunks, comp_dom)
            comp_name = comp_profile.get("brand_name", comp_domain)

            # Deduplicate by name within this run
            name_key = comp_name.strip().lower()
            if name_key in seen_names:
                return {"success": False, "error": f"Duplicate competitor: {comp_name}"}

            # Keyword relevance check (zero LLM calls)
            source_industry = source_profile.get("industry", "").lower()
            comp_industry = comp_profile.get("industry", "").lower()
            if source_industry and comp_industry:
                source_words = set(source_industry.split())
                comp_words = set(comp_industry.split())
                overlap = source_words & comp_words
                filler_words = {"and", "the", "of", "for", "in", "a", "an", "to", "or"}
                meaningful_overlap = overlap - filler_words
                if not meaningful_overlap and len(source_words) > 1:
                    return {
                        "success": False,
                        "error": f"Industry mismatch: {comp_industry} vs {source_industry}",
                    }

            if _has_target_segment_conflict(source_profile, comp_profile):
                return {
                    "success": False,
                    "error": "Target customer mismatch with source brand",
                }

            relevance = validate_competitor_relevance(source_profile, comp_profile)
            if not relevance.get("relevant", False):
                return {
                    "success": False,
                    "error": f"Irrelevant competitor: {relevance.get('reason', 'rejected')}",
                }

            seen_names.add(name_key)

            # Embedding
            comp_embedding = self.embedding_engine.build_profile_embedding(comp_profile)

            # Compute similarity with parent
            similarity = self.embedding_engine.compute_similarity(
                parent_embedding,
                comp_embedding,
            )

            # Skip competitors below similarity threshold
            if similarity < MIN_SIMILARITY_THRESHOLD:
                return {
                    "success": False,
                    "error": f"Low similarity: {similarity:.2f} < {MIN_SIMILARITY_THRESHOLD}",
                }

            # Save to database
            competitor = Competitor(
                parent_company_id=parent_company.id,
                url=comp_url,
                name=comp_name,
                similarity_score=float(similarity),
                json_profile=json.dumps(comp_profile),
                visual_profile=json.dumps(comp_visual),
                dom_features=json.dumps(comp_dom),
                embedding_vector=EmbeddingEngine.embedding_to_bytes(comp_embedding),
                scope=scope,
            )
            db.add(competitor)
            db.commit()

            # Add to Pinecone
            self.embedding_engine.add_to_index(
                comp_embedding,
                {
                    "company_id": parent_company.id,
                    "competitor_id": competitor.id,
                    "name": comp_name,
                    "url": comp_url,
                },
            )

            return {
                "success": True,
                "data": {
                    "name": comp_name,
                    "url": comp_url,
                    "similarity_score": float(similarity),
                    "profile": comp_profile,
                    "visual_profile": comp_visual,
                },
                "status": f"Competitor {idx + 1}/{total}: {comp_name} (similarity: {similarity:.2f})",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _analyze_competitors(
        self,
        db,
        parent_company: Company,
        candidates: list[dict],
        scope: str = "global",
        max_valid: int = MAX_COMPETITORS,
    ) -> list[dict]:
        """
        Crawl and analyze competitors in parallel batches.

        Args:
            scope: "local" or "global" — saved to each competitor record.
            max_valid: Maximum number of valid competitors to keep.

        Returns:
            List of competitor profile dictionaries.
        """
        competitor_data = []
        seen_names: set[str] = set()
        source_profile = json.loads(parent_company.json_profile)
        parent_embedding = EmbeddingEngine.bytes_to_embedding(
            parent_company.embedding_vector
        )

        # Limit concurrent Chromium instances to avoid piling up headless shells.
        BATCH_SIZE = max(1, COMPETITOR_CRAWL_CONCURRENCY)
        semaphore = asyncio.Semaphore(BATCH_SIZE)

        async def process_with_semaphore(idx: int, candidate: dict, total: int) -> dict:
            async with semaphore:
                self._update_status(
                    f"Analyzing {scope} competitor {idx + 1}/{total}: {candidate.get('domain', '')}..."
                )
                return await self._analyze_single_competitor(
                    db,
                    parent_company,
                    candidate,
                    scope,
                    source_profile,
                    seen_names,
                    max_valid,
                    parent_embedding,
                    idx,
                    total,
                )

        # Process candidates in batches
        for batch_start in range(0, len(candidates), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(candidates))
            batch = candidates[batch_start:batch_end]

            logger.info(
                "Processing batch %d-%d of %d competitors",
                batch_start + 1,
                batch_end,
                len(candidates),
            )

            # Run batch in parallel
            tasks = [
                process_with_semaphore(i, candidate, len(candidates))
                for i, candidate in enumerate(batch, start=batch_start)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, Exception):
                    logger.warning("Batch task exception: %s", result)
                    continue

                if not isinstance(result, dict):
                    continue

                if result.get("success"):
                    competitor_data.append(result["data"])
                    if result.get("status"):
                        self._update_status(result["status"])

                    # Check if we've reached max valid
                    if len(competitor_data) >= max_valid:
                        logger.info(
                            "Reached %d valid %s competitors, stopping.",
                            max_valid,
                            scope,
                        )
                        return competitor_data
                else:
                    logger.warning(
                        "Competitor analysis failed: %s", result.get("error")
                    )

            # Pace batches to avoid rate limits
            if batch_end < len(candidates):
                await asyncio.sleep(COMPETITOR_CRAWL_DELAY)

        return competitor_data
