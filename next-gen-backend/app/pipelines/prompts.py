# app/pipelines/prompts.py

import json
from typing import Any, Dict


FRAME_ANALYSIS_PROMPT = """
You are a security video analyst.
Analyze this surveillance frame carefully.

Identify:
1. Number of visible people.
2. Any dangerous or suspicious objects.
3. Any abnormal or suspicious behavior.
4. Overall risk level.
5. A short scene summary.

Rules:
- Do not invent objects that are not visible.
- If uncertain, say uncertain.
- Return only valid JSON.
- Do not include markdown.

Use this JSON schema:
{
  "people_count": integer,
  "dangerous_objects": array of strings,
  "suspicious_behavior": string,
  "risk_level": "low" | "medium" | "high",
  "scene_summary": string
}
"""


TEMPORAL_EVENT_PROMPT = """
You are analyzing a sequence of surveillance frames from the same camera.
Determine whether a security event occurs across the frame sequence.

Focus on:
- weapon handling
- intrusion
- violence
- running
- falling
- crowd panic
- restricted area violation
- suspicious loitering
- abnormal movement

Rules:
- Use only what is visible in the frames.
- Do not invent facts.
- If uncertain, lower confidence.
- Return only valid JSON.
- Do not include markdown.

Use this JSON schema:
{
  "event_detected": boolean,
  "event_type": string,
  "risk_level": "low" | "medium" | "high",
  "confidence": number between 0 and 1,
  "objects": array of strings,
  "people_count": integer,
  "explanation": string
}
"""


def build_alert_prompt(event: Dict[str, Any]) -> str:
    return f"""
You are a security operations assistant.
Write a concise security alert for a human operator.

Use only the provided event data.
Do not invent facts.
Do not mention model internals.

Event data:
{json.dumps(event, ensure_ascii=False, indent=2)}

Include:
1. Priority level
2. What happened
3. Who was detected, if known
4. When it happened
5. Recommended action

Return plain text only.
"""


def build_chat_prompt(question: str, context: Dict[str, Any]) -> str:
    return f"""
You are a security operations assistant.
Answer the operator's question using only the provided security analysis context.

If the answer is not present in the context, say that the information is not available.
Do not invent facts.

Operator question:
{question}

Security analysis context:
{json.dumps(context, ensure_ascii=False, indent=2)}
"""