"""
HELIOS / Hikari — Multi-Model Deliberation Engine (LLM Council)
Adapted from Karpathy's llm-council methodology.
Orchestrates:
1. Stage 1: Independent Opinion Generation (Concurrent candidates)
2. Stage 2: Anonymous Peer Ranking & Critique
3. Stage 3: Chairman Synthesis into definitive recommendation

Supports dynamic hybrid topology: Local models (PAIR / Ollama) + External APIs (OpenRouter / Gemini).
Discloses same-model persona variations when single local weights are utilized.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from core.quality_contracts import (
    CouncilCandidateOpinion,
    CouncilRanking,
    CouncilResult,
    CouncilStatus,
)
from providers.base import BaseProvider

logger = logging.getLogger("helios.llm_council")


class LLMCouncilEngine:
    """
    Executes a structured 3-stage deliberation process.
    The Council is ADVISORY only; it provides recommendations, never directly mutating code.
    """

    def __init__(
        self,
        primary_provider: BaseProvider,
        additional_providers: Optional[List[BaseProvider]] = None,
        chairman_model: Optional[str] = None,
        timeout_seconds: float = 45.0,
    ):
        self.primary_provider = primary_provider
        self.additional_providers = additional_providers or []
        self.chairman_model = chairman_model
        self.timeout_seconds = timeout_seconds

    async def get_available_candidate_specs(self) -> List[Dict[str, Any]]:
        """
        Discovers candidate models available for deliberation.
        If only one model is loaded, generates differentiated persona perspectives
        and flags 'is_same_model_variant = True' for truthful disclosure.
        """
        candidates = []
        try:
            prov_models = await self.primary_provider.list_models()
        except Exception as e:
            logger.warning(f"Failed to list primary models: {e}")
            prov_models = []

        # If we have 2+ distinct models locally
        if len(prov_models) >= 2:
            for idx, m in enumerate(prov_models[:3]):
                name = m if isinstance(m, str) else m.get("name", str(m))
                candidates.append({
                    "id": f"candidate_{chr(ord('A') + idx)}",
                    "model": name,
                    "provider": getattr(self.primary_provider, "name", "local"),
                    "is_variant": False,
                    "persona": "General Senior Engineer",
                })
        else:
            # Fallback: same model with 3 distinct architectural stances
            base_model = prov_models[0] if prov_models else "qwen2.5-coder:14b"
            if isinstance(base_model, dict):
                base_model = base_model.get("name", "local-model")
            
            personas = [
                ("Candidate A", "Principal Systems Architect (prioritizing modularity, reliability, clean contracts)"),
                ("Candidate B", "Performance & Low-Level Specialist (prioritizing low overhead, memory, concurrency)"),
                ("Candidate C", "Defensive Security & Reliability Reviewer (prioritizing failure modes, exploitability, boundary checks)")
            ]
            for idx, (label, persona) in enumerate(personas):
                candidates.append({
                    "id": f"candidate_{chr(ord('A') + idx)}",
                    "model": base_model,
                    "provider": getattr(self.primary_provider, "name", "local"),
                    "is_variant": True,
                    "persona": persona,
                })

        return candidates

    async def run_deliberation(
        self,
        task_id: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> CouncilResult:
        """Runs the complete 3-stage council workflow."""
        start_time = time.time()
        context = context or {}
        candidate_specs = await self.get_available_candidate_specs()

        # ─── Stage 1: Independent Opinions ──────────────────────────────────
        opinions: List[CouncilCandidateOpinion] = []
        opinion_tasks = [
            self._generate_opinion(spec, query, context)
            for spec in candidate_specs
        ]
        results = await asyncio.gather(*opinion_tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, CouncilCandidateOpinion):
                opinions.append(res)
            elif isinstance(res, Exception):
                logger.warning(f"Candidate opinion failed: {res}")

        if not opinions:
            return CouncilResult(
                task_id=task_id,
                status=CouncilStatus.FAILED,
                decision="Deliberation failed: All candidate models timed out or failed to respond.",
                confidence=0.0,
                candidate_count=0,
                limitations=["Total provider failure in Stage 1"],
            )

        is_same_model = any(op.is_same_model_variant for op in opinions)
        same_model_note = (
            "Deliberation conducted using differentiated expert perspectives over shared model weights."
            if is_same_model else None
        )

        # ─── Stage 2: Anonymous Peer Ranking ────────────────────────────────
        rankings: List[CouncilRanking] = []
        if len(opinions) >= 2:
            rank_tasks = [
                self._generate_ranking(op, opinions, query)
                for op in opinions
            ]
            rank_res = await asyncio.gather(*rank_tasks, return_exceptions=True)
            for r in rank_res:
                if isinstance(r, CouncilRanking):
                    rankings.append(r)

        # ─── Stage 3: Chairman Synthesis ────────────────────────────────────
        synthesis_result = await self._synthesize_consensus(query, opinions, rankings, context)
        synthesis_result.task_id = task_id
        synthesis_result.candidates = opinions
        synthesis_result.rankings = rankings
        synthesis_result.candidate_count = len(opinions)
        synthesis_result.same_model_disclosure = same_model_note
        synthesis_result.budget_used = {
            "elapsed_seconds": round(time.time() - start_time, 3),
            "candidates_participated": len(opinions),
        }

        return synthesis_result

    async def _generate_opinion(
        self,
        spec: Dict[str, Any],
        query: str,
        context: Dict[str, Any],
    ) -> CouncilCandidateOpinion:
        t0 = time.time()
        persona = spec.get("persona", "Senior Software Architect")
        prompt = f"""You are acting as an independent expert panelist on the Technical Council.
Role / Stance: {persona}

Evaluate the following technical query or design task thoroughly:
{query}

Additional Context:
{json.dumps(context, indent=2) if context else "None provided"}

Provide your independent proposal, technical breakdown, edge cases, and rationale.
Do not hedge or seek consensus; provide your genuine technical evaluation.
"""
        resp = await asyncio.wait_for(
            self.primary_provider.generate(
                model=spec["model"],
                prompt=prompt,
                stream=False,
            ),
            timeout=self.timeout_seconds,
        )
        text = resp.get("response", "").strip()
        latency = (time.time() - t0) * 1000.0

        return CouncilCandidateOpinion(
            candidate_id=spec["id"],
            model_name=spec["model"],
            provider=spec["provider"],
            opinion_text=text,
            is_same_model_variant=spec.get("is_variant", False),
            latency_ms=latency,
        )

    async def _generate_ranking(
        self,
        reviewer: CouncilCandidateOpinion,
        all_opinions: List[CouncilCandidateOpinion],
        query: str,
    ) -> CouncilRanking:
        # Anonymize candidates and shuffle order
        shuffled = list(all_opinions)
        random.shuffle(shuffled)
        
        proposals_text = ""
        anon_map = {}
        for idx, cand in enumerate(shuffled):
            anon_id = f"Proposal_{idx+1}"
            anon_map[anon_id] = cand.candidate_id
            proposals_text += f"\n### {anon_id}:\n{cand.opinion_text}\n"

        prompt = f"""You are reviewing technical proposals anonymously for the query:
{query}

Here are the candidate proposals:
{proposals_text}

Critique each proposal. Rank them strictly from best to worst based on correctness, scalability, robustness, and architectural clarity.
You MUST output valid JSON:
{{
  "ranked_order": ["Proposal_1", "Proposal_2", ...],
  "rationales": {{"Proposal_1": "reason", ...}},
  "trade_offs": {{"Proposal_1": "downside/risk", ...}}
}}
"""
        resp = await asyncio.wait_for(
            self.primary_provider.generate(
                model=reviewer.model_name,
                prompt=prompt,
                stream=False,
                format="json",
            ),
            timeout=self.timeout_seconds,
        )
        raw = resp.get("response", "{}")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {}

        ranked_order = []
        for prop in parsed.get("ranked_order", []):
            if prop in anon_map:
                ranked_order.append(anon_map[prop])

        # Map back rationales and tradeoffs
        rationales = {anon_map.get(k, k): v for k, v in parsed.get("rationales", {}).items()}
        trade_offs = {anon_map.get(k, k): v for k, v in parsed.get("trade_offs", {}).items()}

        return CouncilRanking(
            ranker_candidate_id=reviewer.candidate_id,
            ranked_order=ranked_order or [c.candidate_id for c in all_opinions],
            rationales=rationales,
            trade_offs=trade_offs,
        )

    async def _synthesize_consensus(
        self,
        query: str,
        opinions: List[CouncilCandidateOpinion],
        rankings: List[CouncilRanking],
        context: Dict[str, Any],
    ) -> CouncilResult:
        chair_model = self.chairman_model or opinions[0].model_name
        opinions_block = "\n".join([f"[{op.candidate_id}]: {op.opinion_text}" for op in opinions])
        rankings_block = "\n".join([
            f"Reviewer {r.ranker_candidate_id} ranking: {r.ranked_order} (rationales: {r.rationales})"
            for r in rankings
        ])

        prompt = f"""You are the Chairman of the Technical Council.
Your role is to synthesize a definitive, production-grade technical recommendation from panel deliberation.

ORIGINAL QUERY:
{query}

CANDIDATE PROPOSALS:
{opinions_block}

PEER RANKINGS & CRITIQUES:
{rankings_block or "No peer rankings available."}

Synthesize the final decision.
- Identify the strongest consensus path.
- Highlight significant disagreements or trade-offs.
- Identify assumptions and remaining limitations.

You MUST reply with valid JSON matching:
{{
  "status": "consensus" | "no_consensus" | "insufficient_evidence",
  "decision": "Definitive synthesized recommendation",
  "alternatives": ["Alternative 1", "Alternative 2"],
  "disagreements": ["Point of contention 1"],
  "confidence": 0.85,
  "limitations": ["Assumption or unknown"]
}}
"""
        resp = await asyncio.wait_for(
            self.primary_provider.generate(
                model=chair_model,
                prompt=prompt,
                stream=False,
                format="json",
            ),
            timeout=self.timeout_seconds,
        )
        raw = resp.get("response", "{}")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "status": "consensus",
                "decision": raw or "Recommendation synthesized from candidate opinions.",
                "confidence": 0.8,
            }

        status_str = parsed.get("status", "consensus")
        try:
            status = CouncilStatus(status_str)
        except Exception:
            status = CouncilStatus.CONSENSUS

        return CouncilResult(
            status=status,
            decision=parsed.get("decision", "No clear decision produced."),
            alternatives=parsed.get("alternatives", []),
            disagreements=parsed.get("disagreements", []),
            confidence=float(parsed.get("confidence", 0.8)),
            limitations=parsed.get("limitations", []),
        )
