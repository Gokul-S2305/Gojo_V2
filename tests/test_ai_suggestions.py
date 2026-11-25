import json
from datetime import datetime, timedelta, timezone

from google.genai import types

from app.routers import maps


class FakeModels:
    def __init__(self, response_text=None, error=None):
        self.response_text = response_text
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return type("Response", (), {"text": self.response_text})()


class FakeClient:
    def __init__(self, models):
        self.models = models


def test_recommendations_use_current_json_api_and_backend_fields(monkeypatch):
    payload = {
        "hotels": [{"name": "Harbor House", "area": "Old Port", "price_range": "₹₹", "description": "Near the waterfront."}],
        "restaurants": [{"name": "Market Table", "area": "Market", "cuisine": "Local", "description": "Seasonal dishes."}],
        "attractions": [{"name": "Coastal Trail", "area": "North Bay", "category": "Nature", "description": "A scenic walk."}],
        "travel_tips": [{"title": "Transit", "advice": "Check the local bus schedule."}],
    }
    models = FakeModels(json.dumps(payload))
    monkeypatch.setattr(maps, "genai_client", FakeClient(models))

    result = maps.get_gemini_recommendations("North Bay", "mid")

    assert result["hotels"][0]["name"] == "Harbor House"
    assert result["is_fallback"] is False
    call = models.calls[0]
    assert call["model"] == "gemini-2.5-flash"
    assert isinstance(call["config"], types.GenerateContentConfig)
    assert call["config"].response_mime_type == "application/json"


def test_ai_failure_does_not_return_or_cache_made_up_suggestions(monkeypatch):
    monkeypatch.setattr(maps, "genai_client", None)
    assert maps.get_gemini_recommendations("North Bay", "mid") is None

    models = FakeModels(error=RuntimeError("provider unavailable"))
    monkeypatch.setattr(maps, "genai_client", FakeClient(models))
    assert maps.get_gemini_recommendations("North Bay", "mid") is None


def test_ai_itinerary_uses_current_json_api(monkeypatch):
    itinerary = [{"day": 1, "theme": "Coast and cuisine", "items": [{"time": "09:00", "activity": "Coastal walk"}]}]
    models = FakeModels(json.dumps(itinerary))
    monkeypatch.setattr(maps, "genai_client", FakeClient(models))

    result = maps.get_gemini_itinerary("North Bay", 2)

    assert result == itinerary
    assert models.calls[0]["model"] == "gemini-2.5-flash"
    assert models.calls[0]["config"].response_mime_type == "application/json"


def test_cached_recommendations_reject_placeholders_and_expired_data():
    fresh = datetime.now(timezone.utc)
    valid_data = {
        "hotels": [{"name": "Harbor House"}],
        "restaurants": [],
        "attractions": [],
        "travel_tips": [],
    }
    placeholder_data = {
        **valid_data,
        "hotels": [{"name": "Central Heritage Stay (North Bay)"}],
    }

    assert maps._cached_recommendations_are_usable(valid_data, fresh)
    assert not maps._cached_recommendations_are_usable(placeholder_data, fresh)
    assert not maps._cached_recommendations_are_usable(valid_data, fresh - timedelta(days=1))
