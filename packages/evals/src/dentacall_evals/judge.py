"""LLM judge and heuristic evaluator for tone, clarity, and voice suitability."""

import json
import logging
import re
from typing import Any

from dentacall_agent.providers.base import ChatMessage, LLMProvider

from dentacall_evals.models import Scenario, TurnRecord

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are an expert QA evaluator for conversational AI voice agents in healthcare.
You evaluate transcripts between a caller and a dental clinic voice receptionist at Grand Canal Dental Clinic in Dublin, Ireland.

RUBRIC FOR EVALUATION:

TONE (1 to 5):
5 - Exemplary: Warm, courteous, empathetic, spoken Irish dental clinic receptionist tone. Patient and professional.
4 - Good: Polite, respectful, clear, minor formal stiffness.
3 - Acceptable: Serviceable, but somewhat mechanical or robotic.
2 - Poor: Terse, dismissive, impatient, or inappropriate for healthcare.
1 - Unacceptable: Rude, hostile, argumentative, or aggressive.

CLARITY (1 to 5):
5 - Exemplary: Concise spoken language (1-2 sentences), natural phrasing, zero markdown/formatting, sounds like real speech.
4 - Good: Easy to understand, clear spoken sentences, minor unnecessary words.
3 - Acceptable: Understandable, but too long or slightly structured like written text.
2 - Poor: Confusing, disjointed, contains raw code, JSON snippets, or bullet points.
1 - Unacceptable: Broken sentences, hallucinated nonsensical output, or unintelligible.

Output your evaluation in strict JSON format:
{
  "tone_score": <float between 1.0 and 5.0>,
  "clarity_score": <float between 1.0 and 5.0>,
  "explanation": "<1-2 sentence summary of tone and clarity findings>"
}
"""


class LLMJudge:
    """Evaluates conversation tone and clarity using LLM or rule-based heuristics."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider

    async def evaluate(
        self,
        scenario: Scenario,
        turns: list[TurnRecord],
    ) -> tuple[float, float, str]:
        """Evaluate dialogue turns for tone (1-5) and clarity (1-5)."""
        agent_turns = [t for t in turns if t.speaker == "agent"]
        if not agent_turns:
            return 1.0, 1.0, "No agent responses in conversation."

        # If LLM provider is available, use LLM Judge
        if self.provider is not None:
            try:
                transcript_lines = []
                for t in turns:
                    transcript_lines.append(f"{t.speaker.upper()}: {t.text}")
                transcript_text = "\n".join(transcript_lines)

                prompt = (
                    f"Scenario: {scenario.name} ({scenario.category})\n"
                    f"Description: {scenario.description}\n\n"
                    f"TRANSCRIPT:\n{transcript_text}\n\n"
                    "Evaluate the AGENT's tone and clarity according to the rubric."
                )

                response = await self.provider.generate(
                    messages=[
                        ChatMessage(role="system", content=JUDGE_SYSTEM_PROMPT),
                        ChatMessage(role="user", content=prompt),
                    ],
                    temperature=0.1,
                    max_tokens=250,
                )

                content = (response.content or "").strip()
                # Extract JSON if enclosed in markdown blocks
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    data: dict[str, Any] = json.loads(json_match.group(0))
                    tone = float(data.get("tone_score", 4.5))
                    clarity = float(data.get("clarity_score", 4.5))
                    explanation = str(data.get("explanation", "Evaluated by LLM Judge."))
                    return tone, clarity, explanation
            except Exception as exc:
                logger.warning("LLM Judge call failed, using heuristic evaluator: %s", exc)

        # Deterministic heuristic fallback
        return self._heuristic_evaluate(agent_turns)

    def _heuristic_evaluate(self, agent_turns: list[TurnRecord]) -> tuple[float, float, str]:
        """Heuristic evaluation when LLM Judge is offline."""
        tone = 5.0
        clarity = 5.0
        reasons: list[str] = []

        all_text = " ".join(t.text for t in agent_turns)

        # Markdown syntax check (bad for voice)
        if any(marker in all_text for marker in ("```", "###", " - ", "* ", "__")):
            clarity -= 1.0
            reasons.append("Contains markdown formatting unsuitable for voice.")

        # Length check: voice sentences should ideally be under 35 words per turn
        long_turns = [t for t in agent_turns if len(t.text.split()) > 45]
        if long_turns:
            clarity -= 0.5
            reasons.append("One or more turns exceed spoken voice brevity guidelines.")

        # Politeness / warmth check
        polite_markers = [
            "please",
            "thank",
            "welcome",
            "happy to help",
            "good day",
            "certainly",
            "sorry",
        ]
        has_polite = any(pm in all_text.lower() for pm in polite_markers)
        if not has_polite:
            tone -= 0.5
            reasons.append("Lacks standard hospitality markers.")

        explanation = (
            " ".join(reasons)
            if reasons
            else "Natural spoken phrasing with courteous receptionist tone."
        )
        return max(1.0, min(5.0, tone)), max(1.0, min(5.0, clarity)), explanation
