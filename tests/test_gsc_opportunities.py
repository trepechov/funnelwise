from __future__ import annotations

from search_console import analyse_opportunities, brand_terms, expected_ctr
from lib.workspace import load_brand


def row(keys, clicks, impressions, position):
    keys = keys if isinstance(keys, list) else [keys]
    return {"keys": keys, "clicks": clicks, "impressions": impressions, "ctr": clicks / impressions if impressions else 0,
            "position": position}


TERMS = ["acme", "acme outdoor"]


def test_striking_distance_ranks_by_potential_and_excludes_brand():
    queries = [
        row("tent review", 40, 4000, 6.9),      # big potential
        row("tent pegs", 2, 300, 15.0),         # small potential
        row("acme tents", 500, 4000, 5.0),      # brand → excluded
        row("hiking boots", 0, 30, 8.0),        # below min impressions
        row("rain jacket", 300, 1000, 2.0),     # top 3 already → not striking
    ]
    qp = [row(["tent review", "https://a.example/tents"], 30, 3000, 6.5),
          row(["tent review", "https://a.example/blog"], 10, 1000, 8.0)]
    out = analyse_opportunities(queries, qp, [], [], TERMS, min_impressions=50)
    sd = out["striking_distance"]
    assert [x["query"] for x in sd] == ["tent review", "tent pegs"]
    assert sd[0]["potential_extra_clicks"] == round(4000 * expected_ctr(3) - 40)
    assert sd[0]["page"] == "https://a.example/tents"  # page with most impressions
    assert out["striking_distance_count"] == 2


def test_ctr_gap_flags_snippets_that_underperform_their_position():
    queries = [row("best tent 2026", 10, 2000, 3.0),   # expected ~10% → 0.5% is a gap
               row("tent sale", 180, 2000, 3.0)]       # 9% ≈ expected → no gap
    out = analyse_opportunities(queries, [], [], [], TERMS, 50)
    gaps = out["ctr_below_expected"]
    assert [g["query"] for g in gaps] == ["best tent 2026"]
    assert gaps[0]["expected_ctr"] == 0.10 and gaps[0]["missed_clicks"] == 190


def test_cannibalisation_needs_two_strong_pages():
    qp = [row(["sleeping bag", "https://a/x"], 5, 500, 9), row(["sleeping bag", "https://a/y"], 4, 400, 11),
          row(["stove", "https://a/s"], 9, 900, 4), row(["stove", "https://a/t"], 0, 20, 30)]
    out = analyse_opportunities([], qp, [], [], TERMS, 50)
    assert [c["query"] for c in out["cannibalisation"]] == ["sleeping bag"]
    assert [p["page"] for p in out["cannibalisation"][0]["pages"]] == ["https://a/x", "https://a/y"]


def test_declining_pages_and_brand_share():
    pages = [row("https://a/1", 30, 1000, 5), row("https://a/2", 95, 1000, 5), row("https://a/3", 1, 10, 5)]
    prev = [row("https://a/1", 100, 1000, 3), row("https://a/2", 100, 1000, 5), row("https://a/3", 5, 10, 5)]
    queries = [row("acme", 60, 100, 1), row("tents", 40, 1000, 5)]
    out = analyse_opportunities(queries, [], pages, prev, TERMS, 50)
    assert [d["page"] for d in out["declining_pages"]] == ["https://a/1"]  # -70%; /2 only -5%; /3 too small
    assert out["declining_pages"][0]["change_pct"] == -70.0
    assert out["non_brand_click_share"] == 0.4


def test_empty_property():
    out = analyse_opportunities([], [], [], [], TERMS, 50)
    assert out["non_brand_click_share"] is None and out["striking_distance"] == []


def test_brand_terms_from_brand_yaml(brand_dir):
    assert brand_terms(load_brand()) == ["acme", "acme outdoor", "acme-outdoor", "acmeoutdoor"]
