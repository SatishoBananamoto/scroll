"""Tests for scroll.query."""

from scroll.store import ScrollEntry
from scroll.query import search, filter_by_type, filter_by_tag


def _entries():
    return [
        ScrollEntry(id="DEC-001", type="decision", date="2026-03-19",
                     title="Switch to gRPC", tags=["architecture", "api"],
                     body="## Context\nPerformance reasons."),
        ScrollEntry(id="LRN-001", type="learning", date="2026-03-19",
                     title="gRPC needs HTTP/2", tags=["grpc", "networking"],
                     body="## Context\nDiscovered during migration."),
        ScrollEntry(id="MST-001", type="mistake", date="2026-03-19",
                     title="Forgot to update API gateway", tags=["api", "gateway"],
                     body="## Context\nGateway still routed to REST."),
    ]


def test_search_matches_title():
    results = search(_entries(), "gRPC")
    assert len(results) == 2  # DEC-001 and LRN-001


def test_search_matches_body():
    results = search(_entries(), "Performance")
    assert len(results) == 1
    assert results[0].id == "DEC-001"


def test_search_matches_tags():
    results = search(_entries(), "gateway")
    assert len(results) == 1
    assert results[0].id == "MST-001"


def test_search_case_insensitive():
    results = search(_entries(), "GRPC")
    assert len(results) == 2


def test_search_no_match():
    results = search(_entries(), "quantum computing")
    assert results == []


def test_filter_by_type():
    results = filter_by_type(_entries(), "mistake")
    assert len(results) == 1
    assert results[0].id == "MST-001"


def test_filter_by_tag():
    results = filter_by_tag(_entries(), "api")
    assert len(results) == 2  # DEC-001 and MST-001


def test_filter_by_tag_case_insensitive():
    results = filter_by_tag(_entries(), "API")
    assert len(results) == 2
