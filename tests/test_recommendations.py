from recommendations import generate_recommendations


def _bundle(posts_per_week=3.0, reel_share=0.6, avg_gap_days=2.0,
            engagement_rate=0.05, reel_view_rate=0.1,
            sufficient=True, follower_growth_pct_30d=3.0):
    return {
        "posting":    {"posts_per_week": posts_per_week, "reel_share": reel_share,
                       "avg_gap_days": avg_gap_days},
        "engagement": {"engagement_rate": engagement_rate, "reel_view_rate": reel_view_rate},
        "growth":     {"sufficient_data_for_growth": sufficient,
                       "follower_growth_pct_30d": follower_growth_pct_30d},
    }


def _scores(cv=50, eq=50, gm=50):
    return {"content_velocity": cv, "engagement_quality": eq, "growth_momentum": gm}


def _messages(recs):
    return [r["message"] for r in recs]


def _severities(recs):
    return [r["severity"] for r in recs]


def test_rule1_volume_up_quality_down():
    recs = generate_recommendations("Mandi", _bundle(), _scores(cv=70, eq=30))
    assert any("Audit creative direction" in m for m in _messages(recs))
    assert any(r["severity"] == "critical" for r in recs)


def test_rule2_underpublished():
    recs = generate_recommendations("Mandi", _bundle(), _scores(cv=30, eq=70))
    assert any("Increase posting frequency" in m for m in _messages(recs))


def test_rule3_reel_ratio_low():
    recs = generate_recommendations("Mandi", _bundle(reel_share=0.3), _scores())
    assert any("Reels" in m for m in _messages(recs))
    assert any("30%" in m for m in _messages(recs))


def test_rule4_posting_gap():
    recs = generate_recommendations("Mandi", _bundle(avg_gap_days=6.0), _scores())
    assert any("gap between posts" in m for m in _messages(recs))
    assert any("6.0" in m for m in _messages(recs))


def test_rule5_audience_saturated():
    recs = generate_recommendations("Mandi", _bundle(sufficient=True),
                                    _scores(gm=20, eq=60))
    assert any("follower growth is stalled" in m for m in _messages(recs))


def test_rule6_on_track_when_no_rules_fire():
    recs = generate_recommendations("Mandi",
                                    _bundle(reel_share=0.6, avg_gap_days=2.0),
                                    _scores(cv=50, eq=50, gm=50))
    assert len(recs) == 1
    assert recs[0]["severity"] == "ok"
    assert "on track" in recs[0]["message"].lower()


def test_multiple_rules_can_fire():
    recs = generate_recommendations("Mandi",
                                    _bundle(reel_share=0.3, avg_gap_days=6.0),
                                    _scores(cv=70, eq=30))
    assert len(recs) >= 2


def test_brand_name_in_messages():
    recs = generate_recommendations("Elephant", _bundle(reel_share=0.2), _scores())
    assert all("Elephant" in r["message"] for r in recs)


def test_sorted_by_severity():
    recs = generate_recommendations("Mandi",
                                    _bundle(reel_share=0.3, avg_gap_days=6.0),
                                    _scores(cv=70, eq=30))
    from recommendations import _SEVERITY_ORDER
    orders = [_SEVERITY_ORDER[r["severity"]] for r in recs]
    assert orders == sorted(orders)
