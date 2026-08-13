import json
import logging
from typing import List, Dict, Any, Optional
from core.llm import LLMProviderGateway
from core.research.source_manager import ProcessedSource

logger = logging.getLogger(__name__)

class ExtractedEvidence:
    def __init__(self, claim: str, supporting_text: str, source_url: str, confidence: str = "high"):
        self.claim = claim
        self.supporting_text = supporting_text
        self.source_url = source_url
        self.confidence = confidence

class EvidenceStore:
    def __init__(self, llm_gateway: LLMProviderGateway = None):
        self.llm_gateway = llm_gateway or LLMProviderGateway()

    async def extract_evidence_from_source(self, source: ProcessedSource) -> List[ExtractedEvidence]:
        """
        Extracts verifiable claims and supporting text quotes directly from a source excerpt.
        """
        if not source.content_excerpt or len(source.content_excerpt.strip()) < 50:
            return []

        prompt = (
            f"You are Cocoa's Evidence Analyst.\n"
            f"Extract up to 3 factual claims and exact supporting quote snippets from the source text below.\n"
            f"Source Title: {source.title}\n"
            f"Source URL: {source.url}\n\n"
            f"Source Content Excerpt:\n{source.content_excerpt[:1500]}\n\n"
            f"Respond strictly in valid JSON matching this schema:\n"
            f"[\n"
            f'  {{\n'
            f'    "claim": "Specific factual claim",\n'
            f'    "supporting_text": "Exact or closely matching supporting text from source"\n'
            f'  }}\n'
            f"]\n"
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
            if isinstance(parsed, list):
                evidence_list = []
                for item in parsed:
                    c = item.get("claim")
                    s = item.get("supporting_text")
                    if c and s:
                        evidence_list.append(
                            ExtractedEvidence(
                                claim=c,
                                supporting_text=s,
                                source_url=source.url,
                                confidence="high"
                            )
                        )
                if evidence_list:
                    return evidence_list
        except Exception as e:
            logger.warning(f"LLM evidence extraction failed for {source.url}: {e}")

        # Fallback evidence extraction from title & content snippet
        return [
            ExtractedEvidence(
                claim=f"Information regarding '{source.title}' retrieved from {source.domain}.",
                supporting_text=source.content_excerpt[:300],
                source_url=source.url,
                confidence="medium"
            )
        ]
