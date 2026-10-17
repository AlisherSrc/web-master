"""Image classifiers.

* GeminiClassifier — sends the image to Google's Gemini API and forces a
  structured JSON answer restricted to the categories stored in the database.
* MockClassifier   — deterministic offline fallback so the whole stack works
  without an API key or internet access.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any, Protocol

from .config import Settings
from .models import Category

log = logging.getLogger("celestial.classifier")


class ClassifierError(Exception):
    """Raised when classification fails; carries an HTTP status for the API."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class Classifier(Protocol):
    mode: str
    model_name: str

    def classify(self, image: bytes, mime_type: str, categories: Sequence[Category]) -> dict[str, Any]: ...


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _clip(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _normalize(raw: dict[str, Any], categories: Sequence[Category], model_used: str) -> dict[str, Any]:
    """Validate/sanitize the classifier output before it is written to the DB."""
    slugs = {c.slug for c in categories}
    category = str(raw.get("category", "")).strip().lower()
    if category not in slugs:
        log.warning("Unknown category %r returned; mapping to other_celestial", category)
        category = "other_celestial" if "other_celestial" in slugs else next(iter(slugs))

    try:
        confidence = float(raw.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence > 1:  # model answered in percent
        confidence /= 100
    confidence = round(min(max(confidence, 0.0), 1.0), 3)

    features = raw.get("visual_features") or []
    if not isinstance(features, list):
        features = [features]
    features = [f for f in (_clip(x, 120) for x in features) if f][:6]

    return {
        "category": category,
        "confidence": confidence,
        "object_name": _clip(raw.get("object_name"), 200),
        "description": _clip(raw.get("description"), 2000),
        "visual_features": features,
        "fun_fact": _clip(raw.get("fun_fact"), 1000),
        "model_used": model_used,
    }


# -----------------------------------------------------------------------------
# Gemini
# -----------------------------------------------------------------------------
PROMPT_TEMPLATE = """You are an expert astronomer and astrophotography analyst.
Look at the image and classify its MAIN subject into exactly ONE of these categories:

{category_lines}

Rules:
- If the image does not depict an astronomical object (pets, people, food, buildings,
  street lamps, everyday objects, etc.) choose "not_celestial".
- Artistic renderings of celestial objects are classified by what they depict; mention
  in the description that it appears to be an illustration/render.
- confidence: a number from 0 to 1 reflecting how certain you are.
- object_name: the specific object if recognizable (e.g. "Andromeda Galaxy (M31)",
  "Saturn", "Pillars of Creation in M16"), otherwise a short generic name.
- description: 2-3 clear sentences explaining what is shown.
- visual_features: 3-5 short phrases describing the visual evidence you used.
- fun_fact: one accurate, interesting fact about this kind of object
  (or a playful remark if the image is not celestial).
"""


class GeminiClassifier:
    mode = "gemini"

    def __init__(self, api_key: str, model_name: str) -> None:
        self.model_name = model_name
        self._api_key = api_key
        self._client = None
        if api_key:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=60_000),  # ms
            )

    @staticmethod
    def _schema(slugs: list[str]) -> dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "enum": slugs},
                "confidence": {"type": "NUMBER"},
                "object_name": {"type": "STRING"},
                "description": {"type": "STRING"},
                "visual_features": {"type": "ARRAY", "items": {"type": "STRING"}},
                "fun_fact": {"type": "STRING"},
            },
            "required": ["category", "confidence", "object_name", "description", "visual_features", "fun_fact"],
            "propertyOrdering": ["category", "confidence", "object_name", "description", "visual_features", "fun_fact"],
        }

    def classify(self, image: bytes, mime_type: str, categories: Sequence[Category]) -> dict[str, Any]:
        if self._client is None:
            raise ClassifierError(503, "Gemini mode is enabled but GEMINI_API_KEY is not configured.")

        from google.genai import errors, types

        slugs = [c.slug for c in categories]
        prompt = PROMPT_TEMPLATE.format(
            category_lines="\n".join(f'- "{c.slug}" ({c.label}): {c.description}' for c in categories)
        )

        models_to_try = [self.model_name]
        for fallback in ("gemini-3.5-flash", "gemini-3.1-flash-lite"):
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        response = None
        last_error: Exception | None = None
        used_model = self.model_name

        for candidate_model in models_to_try:
            used_model = candidate_model
            try:
                response = self._client.models.generate_content(
                    model=candidate_model,
                    contents=[types.Part.from_bytes(data=image, mime_type=mime_type), prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=self._schema(slugs),
                    ),
                )
                break
            except errors.ClientError as exc:
                code = getattr(exc, "code", None)
                log.warning("Gemini client error on %s (code %s): %s", candidate_model, code, exc)
                last_error = exc
                if code in (401, 403):
                    raise ClassifierError(502, "Gemini rejected the API key. Check GEMINI_API_KEY in your .env file.") from exc
                if code == 429:
                    raise ClassifierError(429, "Gemini free-tier rate limit reached — please wait a minute and try again.") from exc
                if code == 404:
                    log.info("Model %s returned 404; trying fallback...", candidate_model)
                    continue
                raise ClassifierError(502, f"Gemini rejected the request: {getattr(exc, 'message', exc)}") from exc
            except errors.ServerError as exc:
                log.warning("Gemini server error on %s: %s (will try fallback)", candidate_model, exc)
                last_error = exc
                continue
            except Exception as exc:
                log.exception("Unexpected error reaching %s", candidate_model)
                last_error = exc
                continue

        if response is None:
            if isinstance(last_error, errors.ServerError):
                raise ClassifierError(503, "Gemini servers are currently experiencing high demand across flash models. Please try again in a few moments.") from last_error
            raise ClassifierError(502, f"Could not get response from Gemini: {last_error}")

        text = (response.text or "").strip()
        if not text:
            raise ClassifierError(502, "Gemini returned an empty answer (the image may have been blocked by safety filters).")
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON from Gemini: %s", text[:500])
            raise ClassifierError(502, "Gemini returned an unreadable answer — please try again.") from exc

        return _normalize(raw, categories, model_used=used_model)


# -----------------------------------------------------------------------------
# Mock (offline)
# -----------------------------------------------------------------------------
MOCK_DETAILS: dict[str, tuple[str, list[str], str]] = {
    "black_hole": ("Supermassive black hole (simulated)", ["dark central shadow", "bright photon ring", "asymmetric glow"], "The first image of a black hole (M87*) was released in 2019 by the Event Horizon Telescope."),
    "galaxy": ("Spiral galaxy (simulated)", ["spiral arms", "bright galactic bulge", "dust lanes"], "The Milky Way and Andromeda will merge in roughly 4.5 billion years."),
    "star": ("Main-sequence star (simulated)", ["point-like source", "diffraction spikes", "warm colour"], "Our Sun converts about 4 million tonnes of mass into energy every second."),
    "planet": ("Gas giant (simulated)", ["banded atmosphere", "spherical disk", "terminator shadow"], "Jupiter's Great Red Spot is a storm larger than Earth."),
    "moon": ("Rocky moon (simulated)", ["cratered surface", "maria", "grey regolith"], "The Moon drifts about 3.8 cm farther from Earth every year."),
    "nebula": ("Emission nebula (simulated)", ["glowing gas clouds", "embedded young stars", "red H-alpha emission"], "The Orion Nebula is a stellar nursery visible to the naked eye."),
    "cosmic_dust": ("Interstellar dust field (simulated)", ["dark absorbing lanes", "diffuse glow", "dense star field"], "Most of the oxygen and carbon in your body was forged in stars and spread as stardust."),
    "star_cluster": ("Open star cluster (simulated)", ["many bright stars", "compact grouping", "blue hue"], "The Pleiades are only about 100 million years old — young for stars."),
    "supernova_remnant": ("Supernova remnant (simulated)", ["filamentary shell", "expanding structure", "multicolour emission"], "The Crab Nebula's supernova was recorded by Chinese astronomers in 1054 AD."),
    "comet": ("Long-period comet (simulated)", ["bright coma", "ion tail", "dust tail"], "A comet's tail always points away from the Sun, not behind its motion."),
    "asteroid": ("Near-Earth asteroid (simulated)", ["irregular shape", "craters", "rocky texture"], "The asteroid belt's total mass is only about 3% of our Moon's."),
    "quasar": ("Distant quasar (simulated)", ["extremely bright core", "relativistic jet", "host galaxy glow"], "Some quasars outshine their entire host galaxy by a factor of 1,000."),
    "other_celestial": ("Celestial phenomenon (simulated)", ["astronomical context", "unusual morphology", "deep-sky background"], "Gravitational lenses let us see galaxies that would otherwise be too faint."),
    "not_celestial": ("Earthly object (simulated)", ["terrestrial scene", "no deep-sky features", "everyday object"], "Even non-celestial things are made of atoms forged inside ancient stars."),
}


class MockClassifier:
    mode = "mock"
    model_name = "mock-classifier"

    def classify(self, image: bytes, mime_type: str, categories: Sequence[Category]) -> dict[str, Any]:
        digest = hashlib.sha256(image).digest()
        cat = categories[digest[0] % len(categories)]
        name, features, fact = MOCK_DETAILS.get(cat.slug, MOCK_DETAILS["other_celestial"])
        raw = {
            "category": cat.slug,
            "confidence": 0.55 + (digest[1] / 255) * 0.4,
            "object_name": name,
            "description": f"[Mock mode] {cat.description} This verdict is simulated — add a GEMINI_API_KEY to .env for real AI classification.",
            "visual_features": features,
            "fun_fact": fact,
        }
        return _normalize(raw, categories, model_used=self.model_name)


# -----------------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------------
def build_classifier(settings: Settings) -> Classifier:
    mode = settings.classifier_mode
    if mode == "mock" or (mode == "auto" and not settings.gemini_api_key):
        if mode == "auto":
            log.warning("GEMINI_API_KEY not set — falling back to MOCK classifier.")
        return MockClassifier()
    if not settings.gemini_api_key:
        log.error("CLASSIFIER_MODE=gemini but GEMINI_API_KEY is empty; classification requests will fail.")
    return GeminiClassifier(settings.gemini_api_key, settings.gemini_model)
