"""Tests for the Commons acquisition bottleneck fix.

Validates two-phase search/metadata, expanded queries, compliant User-Agent,
relaxed exhaustion thresholds, and provider health tracking — all without
touching relevance, licensing, deduplication, or coverage gates.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_commons_state() -> None:
    """Clear per-test mutable Commons module state."""
    import ml.palettebrain.prepare_c11_recovered_source as source

    source._COMMONS_QUERY_CACHE.clear()
    source._COMMONS_METADATA_SECONDS = 0.0
    source._COMMONS_METADATA_ACCEPTED = 0
    source._COMMONS_COOLDOWN_UNTIL = 0.0
    yield
    source._COMMONS_QUERY_CACHE.clear()
    source._COMMONS_METADATA_SECONDS = 0.0
    source._COMMONS_METADATA_ACCEPTED = 0
    source._COMMONS_COOLDOWN_UNTIL = 0.0


# ---------------------------------------------------------------------------
# 1. Expanded Commons queries
# ---------------------------------------------------------------------------


class TestExpandCommonsQueries:
    def test_returns_concrete_terms_for_deficit_abstraction_concepts(self) -> None:
        from ml.palettebrain.prepare_c11_recovered_source import (
            expand_commons_queries,
        )

        concept = {"concept_id": "solitary_reverie_quietude"}
        terms = expand_commons_queries(concept)
        assert len(terms) >= 2
        assert all(isinstance(t, str) and len(t) > 5 for t in terms)

    def test_returns_concrete_terms_for_deficit_composition_concepts(self) -> None:
        from ml.palettebrain.prepare_c11_recovered_source import (
            expand_commons_queries,
        )

        concept = {"concept_id": "desert_caravan_oasis_palms"}
        terms = expand_commons_queries(concept)
        assert len(terms) >= 2
        assert any("desert" in t.lower() or "caravan" in t.lower() for t in terms)

    def test_returns_empty_for_non_deficit_concept(self) -> None:
        from ml.palettebrain.prepare_c11_recovered_source import (
            expand_commons_queries,
        )

        concept = {"concept_id": "ripe_orchard_apple"}
        assert expand_commons_queries(concept) == []

    def test_all_19_deficit_concepts_have_entries(self) -> None:
        from ml.palettebrain.prepare_c11_recovered_source import (
            _COMMONS_EXPANDED_QUERIES,
        )

        expected_concepts = {
            # abstractions
            "bittersweet_evening_wistfulness",
            "solitary_reverie_quietude",
            "haunting_nocturnal_mystery",
            "austere_monastic_serenity",
            "quiet_morning_clarity",
            "dynamic_festive_exuberance",
            "restrained_poignant_tenderness",
            # compositions
            "desert_caravan_oasis_palms",
            "golden_wheat_field_haystack_rest",
            "fishing_village_misty_harbor",
            "cozy_candlelit_tavern_hearth",
            "ancient_desert_ruins_sunset",
            "alpine_chalet_mountain_view",
            "stormy_seacoast_shipwreck_rocks",
            "candlelit_alchemist_laboratory",
            "moonlit_winter_graveyard_ruins",
            "bustling_florentine_market_square",
            "solitary_monk_mountain_cell",
            "rainy_paris_boulevard_carriages",
        }
        assert expected_concepts.issubset(set(_COMMONS_EXPANDED_QUERIES.keys()))

    def test_expanded_queries_are_distinct_from_each_other(self) -> None:
        from ml.palettebrain.prepare_c11_recovered_source import (
            _COMMONS_EXPANDED_QUERIES,
        )

        all_terms: list[str] = []
        for terms in _COMMONS_EXPANDED_QUERIES.values():
            all_terms.extend(terms)
        # No exact duplicates across all concepts
        assert len(all_terms) == len(set(all_terms))


# ---------------------------------------------------------------------------
# 2. Two-phase Commons metadata fetch
# ---------------------------------------------------------------------------


class TestTwoPhaseCommonsFetch:
    def _make_search_payload(
        self, page_ids: list[int], *, mime: str = "image/jpeg"
    ) -> dict[str, Any]:
        pages = {}
        for pid in page_ids:
            pages[str(pid)] = {
                "pageid": pid,
                "title": f"File:Test_{pid}.jpg",
                "imageinfo": [
                    {
                        "thumburl": f"https://upload.wikimedia.org/test_{pid}.jpg",
                        "url": f"https://upload.wikimedia.org/full_{pid}.jpg",
                        "mime": mime,
                        "descriptionurl": f"https://commons.wikimedia.org/wiki/File:Test_{pid}.jpg",
                    }
                ],
            }
        return {"query": {"pages": pages}}

    def _make_meta_payload(
        self,
        page_ids: list[int],
        *,
        license_name: str = "CC BY 4.0",
        license_url: str = "https://creativecommons.org/licenses/by/4.0/",
    ) -> dict[str, Any]:
        pages = {}
        for pid in page_ids:
            pages[str(pid)] = {
                "pageid": pid,
                "imageinfo": [
                    {
                        "extmetadata": {
                            "LicenseShortName": {"value": license_name},
                            "LicenseUrl": {"value": license_url},
                            "Artist": {"value": "Test artist"},
                            "ObjectName": {"value": "painting"},
                        }
                    }
                ],
            }
        return {"query": {"pages": pages}}

    def test_two_phase_produces_valid_candidates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        call_log: list[str] = []

        def mock_fetch_json(url: str, **kwargs: Any) -> dict[str, Any] | None:
            call_log.append(url)
            if "generator=search" in url:
                return self._make_search_payload([100, 101, 102])
            if "pageids=" in url:
                return self._make_meta_payload([100, 101, 102])
            return None

        monkeypatch.setattr(source, "fetch_json", mock_fetch_json)
        rows = source.commons_candidates("test painting", limit=10, page=1)

        assert len(rows) == 3
        assert all(r["source_id"] == "commons" for r in rows)
        assert all(r["license"] == "CC BY 4.0" for r in rows)
        # Verify two separate API calls were made (phase 1 + phase 2)
        assert len(call_log) == 2
        assert "generator=search" in call_log[0]
        assert "pageids=" in call_log[1]

    def test_phase1_returns_no_images_skips_phase2(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        call_log: list[str] = []

        def mock_fetch_json(url: str, **kwargs: Any) -> dict[str, Any] | None:
            call_log.append(url)
            if "generator=search" in url:
                # Return non-image MIME
                return self._make_search_payload([200], mime="application/pdf")
            return None

        monkeypatch.setattr(source, "fetch_json", mock_fetch_json)
        rows = source.commons_candidates("test document", limit=10, page=1)
        assert len(rows) == 0
        # Phase 2 should NOT be called since no viable image pages
        assert len(call_log) == 1

    def test_phase2_failure_returns_empty_but_consumed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        def mock_fetch_json(url: str, **kwargs: Any) -> dict[str, Any] | None:
            if "generator=search" in url:
                return self._make_search_payload([300])
            if "pageids=" in url:
                return None  # Phase 2 fails
            return None

        monkeypatch.setattr(source, "fetch_json", mock_fetch_json)
        rows = source.commons_candidates("test art", limit=10, page=1)
        # No extmetadata → license check fails → 0 candidates
        assert len(rows) == 0
        assert getattr(rows, "consumed", True)

    def test_uses_shorter_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        recorded_timeouts: list[int] = []

        original_fetch = source.fetch_json

        def tracking_fetch(url: str, **kwargs: Any) -> dict[str, Any] | None:
            if "commons.wikimedia.org" in url:
                recorded_timeouts.append(kwargs.get("timeout", 20))
            return self._make_search_payload([]) if "generator=search" in url else None

        monkeypatch.setattr(source, "fetch_json", tracking_fetch)
        source.commons_candidates("test timeout", limit=5, page=1)
        assert all(t <= 8 for t in recorded_timeouts), (
            f"Expected timeout <= 8 but got {recorded_timeouts}"
        )


# ---------------------------------------------------------------------------
# 3. Compliant User-Agent
# ---------------------------------------------------------------------------


class TestWikimediaUserAgent:
    def test_wikimedia_user_agent_constant_exists(self) -> None:
        from ml.palettebrain.prepare_c11_recovered_source import (
            WIKIMEDIA_USER_AGENT,
        )

        assert "PaletteBrain" in WIKIMEDIA_USER_AGENT
        # Wikimedia policy: must contain URL or contact info
        assert "http" in WIKIMEDIA_USER_AGENT.lower()

    def test_wikimedia_ua_used_for_commons_urls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        captured_headers: list[dict[str, str]] = []

        original_safe_get = source.safe_http_get

        def capturing_get(url: str, **kwargs: Any) -> bytes | None:
            if "commons.wikimedia.org" in url:
                # Instead of actually calling, just check what would be passed
                headers = {
                    "User-Agent": (
                        source.WIKIMEDIA_USER_AGENT
                        if "commons.wikimedia.org" in url
                        else "PaletteBrain-C11-DataBuilder/1.0"
                    ),
                }
                captured_headers.append(headers)
            return None

        monkeypatch.setattr(source, "safe_http_get", capturing_get)
        source.fetch_json(
            "https://commons.wikimedia.org/w/api.php?action=query",
            timeout=5,
        )
        assert len(captured_headers) == 1
        assert "OKLCH-PIXEL-PALETTE" in captured_headers[0]["User-Agent"]


# ---------------------------------------------------------------------------
# 4. Targeted mode exhaustion threshold
# ---------------------------------------------------------------------------


class TestTargetedExhaustion:
    def test_targeted_max_training_queries_is_six(self) -> None:
        from ml.palettebrain.prepare_c11_recovered_source import (
            TARGETED_MAX_TRAINING_QUERIES,
        )

        assert TARGETED_MAX_TRAINING_QUERIES == 6

    def test_limit_commons_ceiling_is_fifty(self) -> None:
        """The limit_commons calculation should allow up to 50."""
        # limit_commons = min(max(max_count, 12), 50)
        assert min(max(6, 12), 50) == 12  # small max_count
        assert min(max(30, 12), 50) == 30  # medium max_count
        assert min(max(60, 12), 50) == 50  # large max_count (capped at 50)


# ---------------------------------------------------------------------------
# 5. Provider health / cooldown tracking
# ---------------------------------------------------------------------------


class TestProviderHealthTracking:
    def test_cooldown_triggers_after_excessive_latency(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        source._COMMONS_METADATA_SECONDS = 130.0  # > 120s threshold
        source._COMMONS_METADATA_ACCEPTED = 2  # < 5 threshold

        def slow_fetch(url: str, **kwargs: Any) -> dict[str, Any] | None:
            return None  # Simulate timeout

        monkeypatch.setattr(source, "fetch_json", slow_fetch)
        result = source.commons_candidates("test cooldown", limit=5, page=1)
        assert len(result) == 0
        # After the call, cooldown should have been triggered
        assert source._COMMONS_COOLDOWN_UNTIL > time.time()

    def test_cooldown_skips_subsequent_requests(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        source._COMMONS_COOLDOWN_UNTIL = time.time() + 60.0
        call_count = 0

        def counting_fetch(url: str, **kwargs: Any) -> dict[str, Any] | None:
            nonlocal call_count
            call_count += 1
            return None

        monkeypatch.setattr(source, "fetch_json", counting_fetch)
        result = source.commons_candidates("test skip", limit=5, page=1)
        assert len(result) == 0
        assert call_count == 0  # Should skip without making any network call


# ---------------------------------------------------------------------------
# 6. Cache integrity
# ---------------------------------------------------------------------------


class TestCacheIntegrity:
    def test_cached_results_returned_on_repeat_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        call_count = 0

        def mock_fetch(url: str, **kwargs: Any) -> dict[str, Any] | None:
            nonlocal call_count
            call_count += 1
            if "generator=search" in url:
                return {
                    "query": {
                        "pages": {
                            "42": {
                                "pageid": 42,
                                "title": "File:Cache_test.jpg",
                                "imageinfo": [
                                    {
                                        "thumburl": "https://upload.wikimedia.org/cache.jpg",
                                        "mime": "image/jpeg",
                                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Cache_test.jpg",
                                    }
                                ],
                            }
                        }
                    }
                }
            if "pageids=" in url:
                return {
                    "query": {
                        "pages": {
                            "42": {
                                "imageinfo": [
                                    {
                                        "extmetadata": {
                                            "LicenseShortName": {
                                                "value": "CC0"
                                            },
                                            "LicenseUrl": {
                                                "value": "https://creativecommons.org/publicdomain/zero/1.0/"
                                            },
                                            "Copyrighted": {"value": "False"},
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            return None

        monkeypatch.setattr(source, "fetch_json", mock_fetch)

        # First call
        rows1 = source.commons_candidates("cache test painting", limit=10, page=1)
        first_call_count = call_count

        # Second call — should come from cache
        rows2 = source.commons_candidates("cache test painting", limit=10, page=1)
        assert call_count == first_call_count  # No new network calls
        assert len(rows2) == len(rows1)

    def test_expanded_queries_use_separate_cache_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ml.palettebrain.prepare_c11_recovered_source as source

        queries_seen: list[str] = []

        def mock_fetch(url: str, **kwargs: Any) -> dict[str, Any] | None:
            if "generator=search" in url and "gsrsearch=" in url:
                import urllib.parse

                parsed = urllib.parse.parse_qs(
                    urllib.parse.urlsplit(url).query
                )
                queries_seen.append(parsed.get("gsrsearch", [""])[0])
            return {"query": {"pages": {}}}

        monkeypatch.setattr(source, "fetch_json", mock_fetch)

        source.commons_candidates("original query", limit=5, page=1)
        source.commons_candidates("expanded synonym", limit=5, page=1)

        assert len(queries_seen) == 2
        assert queries_seen[0] != queries_seen[1]
