# app/integrations/qwen.py

import json
import re
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings


class QwenClient:
    def __init__(self):
        self.api_key = settings.dashscope_api_key

        self.vl_model = settings.qwen_vl_model
        self.text_model = settings.qwen_text_model
        self.temporal_model = settings.qwen_temporal_model

        self.enabled = False
        self._dashscope = None

        self._successful_vl_model: Optional[str] = None
        self._successful_text_model: Optional[str] = None
        self._successful_temporal_model: Optional[str] = None

        if self.api_key:
            try:
                import dashscope

                dashscope.api_key = self.api_key
                self._dashscope = dashscope
                self.enabled = True
            except Exception as e:
                print(f"[qwen] DashScope initialization failed: {e}")
                self.enabled = False

    # -----------------------------
    # Basic helpers
    # -----------------------------
    def _model_candidates(
        self,
        preferred: Optional[str],
        fallbacks: List[str],
    ) -> List[str]:
        models = []

        if preferred:
            models.append(preferred)

        for model in fallbacks:
            if model and model not in models:
                models.append(model)

        return models

    def _content_to_text(self, content: Any) -> str:
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []

            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        parts.append(str(item["text"]))
                    else:
                        parts.append(json.dumps(item, ensure_ascii=False))
                else:
                    parts.append(str(item))

            return "\n".join(parts)

        if isinstance(content, dict):
            return content.get("text", json.dumps(content, ensure_ascii=False))

        return str(content)

    def _extract_response_text(self, response: Any) -> Optional[str]:
        if response is None:
            return None

        status_code = getattr(response, "status_code", 200)
        if status_code != 200:
            return None

        output = getattr(response, "output", None)

        if output is None and isinstance(response, dict):
            output = response.get("output")

        choices = None

        if isinstance(output, dict):
            choices = output.get("choices")
        else:
            choices = getattr(output, "choices", None)

        if choices:
            choice = choices[0]

            if isinstance(choice, dict):
                message = choice.get("message", {})
            else:
                message = getattr(choice, "message", {})

            if isinstance(message, dict):
                content = message.get("content")
            else:
                content = getattr(message, "content", None)

            return self._content_to_text(content)

        text = getattr(output, "text", None)
        if text:
            return text

        if output:
            return str(output)

        return None

    def _parse_json_or_text(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}

        cleaned = text.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(r"```(?:json)?", "", cleaned)
            cleaned = cleaned.replace("```", "").strip()

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        return {"raw": text}

    def _sample_evenly(self, items: List[Any], max_items: int) -> List[Any]:
        if len(items) <= max_items:
            return items

        step = len(items) / float(max_items)
        sampled = []

        for i in range(max_items):
            idx = int(i * step)
            sampled.append(items[idx])

        return sampled

    # -----------------------------
    # Text generation
    # -----------------------------
    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
    ) -> Optional[str]:
        if not self.enabled:
            return None

        preferred = model or self._successful_text_model or self.text_model
        models = self._model_candidates(
            preferred,
            settings.qwen_text_fallback_list,
        )

        for candidate in models:
            try:
                response = self._dashscope.Generation.call(
                    model=candidate,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    result_format="message",
                )

                text = self._extract_response_text(response)

                if text and text.strip():
                    self._successful_text_model = candidate
                    return text

            except Exception as e:
                print(f"[qwen] Text generation failed with model {candidate}: {e}")
                time.sleep(0.5)
                continue

        return None

    # -----------------------------
    # Multimodal internals
    # -----------------------------
    def _call_multimodal(
        self,
        model: str,
        content: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not self.enabled:
            return None

        response = self._dashscope.MultiModalConversation.call(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            result_format="message",
        )

        return self._extract_response_text(response)

    # -----------------------------
    # Single-image analysis
    # -----------------------------
    def analyze_image(
        self,
        image_ref: str,
        prompt: str,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        if not image_ref:
            return None

        preferred = model or self._successful_vl_model or self.vl_model
        models = self._model_candidates(
            preferred,
            settings.qwen_vl_fallback_list,
        )

        content = [
            {"image": image_ref},
            {"text": prompt},
        ]

        for candidate in models:
            try:
                text = self._call_multimodal(candidate, content)

                if text and text.strip():
                    parsed = self._parse_json_or_text(text)

                    if parsed:
                        self._successful_vl_model = candidate
                        return parsed

            except Exception as e:
                print(f"[qwen] Image analysis failed with model {candidate}: {e}")
                time.sleep(0.5)
                continue

        return None

    # -----------------------------
    # Multi-frame temporal analysis
    # -----------------------------
    def analyze_video_frames(
        self,
        image_refs: List[str],
        prompt: str,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        if not image_refs:
            return None

        max_images = settings.qwen_max_images_per_temporal_call
        image_refs = self._sample_evenly(image_refs, max_images)

        preferred = model or self._successful_temporal_model or self.temporal_model
        models = self._model_candidates(
            preferred,
            settings.qwen_temporal_fallback_list,
        )

        content = []

        for ref in image_refs:
            content.append({"image": ref})

        content.append({"text": prompt})

        for candidate in models:
            try:
                text = self._call_multimodal(candidate, content)

                if text and text.strip():
                    parsed = self._parse_json_or_text(text)

                    if parsed:
                        self._successful_temporal_model = candidate
                        return parsed

            except Exception as e:
                print(
                    f"[qwen] Temporal analysis failed with model {candidate}: {e}"
                )
                time.sleep(0.5)
                continue

        # Fallback:
        # If multi-image temporal call fails, try single-image analysis.
        return self.analyze_image(
            image_refs[0],
            prompt,
            model=self._successful_vl_model or self.vl_model,
        )