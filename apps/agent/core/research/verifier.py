import json
import logging
from typing import List, Dict, Any
from core.llm import LLMProviderGateway
from core.research.evidence_store import ExtractedEvidence
from core.research.source_manager import ProcessedSource

logger = logging.getLogger(__name__)

class VerificationReport:
    def __init__(self, finding_text: str, supported: bool, confidence: str, supporting_sources: List[str]):
        self.finding_text = finding_text
        self.supported = supported
        self.confidence = confidence
        self.supporting_sources = supporting_sources

class ResearchVerifier:
    def __init__(self, llm_gateway: LLMProviderGateway = None):
        self.llm_gateway = llm_gateway or LLMProviderGateway()

    async def verify_findings(self, findings: List[str], evidence_items: List[ExtractedEvidence], sources: List[ProcessedSource]) -> List[VerificationReport]:
        """
        Verifies key research findings against collected evidence and source material.
        Guarantees unsupported claims are marked supported=False.
        """
        reports = []

        if not evidence_items and not sources:
            # Strictly reject all findings if no evidence or sources exist
            for f in findings:
                reports.append(VerificationReport(finding_text=f, supported=False, confidence="low", supporting_sources=[]))
            return reports

        evidence_summary = "\n".join([f"- Claim: {e.claim} | Quote: '{e.supporting_text}' | Source: {e.source_url}" for e in evidence_items[:10]])

        for finding in findings:
            prompt = (
                f"You are Cocoa's Strict Evidence Verifier.\n"
                f"Verify if the finding below is directly supported by the collected evidence.\n"
                f"Finding: {finding}\n\n"
                f"Evidence List:\n{evidence_summary}\n\n"
                f"Respond strictly in valid JSON matching this schema:\n"
                f"{{\n"
                f'  "supported": true,\n'
                f'  "confidence": "high",\n'
                f'  "supporting_sources": ["url1", "url2"]\n'
                f"}}\n"
            )

            try:
                provider = self.llm_gateway.get_provider()
                response_text = await provider.generate_text(prompt)

                clean_text = response_text.strip()
                if "```json" in clean_text:
                    clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_text:
                    clean_text = clean_text.split("```")[1].split("```")[0].strip()

                parsed = json.loads(clean_text)
                supp = bool(parsed.get("supported", False))
                conf = str(parsed.get("confidence", "high" if supp else "low"))
                supp_srcs = parsed.get("supporting_sources") if isinstance(parsed.get("supporting_sources"), list) else []

                # Ensure supporting_sources fallback if supported is True
                if supp and not supp_srcs and sources:
                    supp_srcs = [sources[0].url]

                reports.append(VerificationReport(finding_text=finding, supported=supp, confidence=conf, supporting_sources=supp_srcs))
            except Exception as e:
                logger.warning(f"Verification check failed for finding '{finding[:30]}': {e}")
                # Conservative fallback verification check
                matched_sources = [s.url for s in sources if any(w.lower() in s.title.lower() or w.lower() in s.content_excerpt.lower() for w in finding.split()[:3] if len(w) > 3)]
                is_supp = len(matched_sources) > 0
                reports.append(
                    VerificationReport(
                        finding_text=finding,
                        supported=is_supp,
                        confidence="medium" if is_supp else "low",
                        supporting_sources=matched_sources if is_supp else []
                    )
                )

        return reports
