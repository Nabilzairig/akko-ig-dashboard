_SEVERITY_ORDER = {"critical": 0, "warning": 1, "tip": 2, "ok": 3}


def generate_recommendations(brand_name, metrics_bundle, scores):
    """
    Evaluate rule set and return a list of dicts sorted by severity:
        [{"severity": "critical"|"warning"|"tip"|"ok", "message": str}, ...]
    """
    eq = scores.get("engagement_quality") or 50
    cv = scores.get("content_velocity")   or 50
    gm = scores.get("growth_momentum")

    posting    = metrics_bundle["posting"]
    growth     = metrics_bundle["growth"]
    reel_share   = posting["reel_share"]
    avg_gap_days = posting["avg_gap_days"]
    sufficient   = growth["sufficient_data_for_growth"]

    triggered = []

    if eq < 40 and cv > 60:
        triggered.append({
            "severity": "critical",
            "message": (
                f"{brand_name}: posting volume is high (CV {cv}) but engagement is weak "
                f"(EQ {eq}/100). Audit creative direction before publishing more."
            ),
        })

    if eq > 60 and cv < 40:
        triggered.append({
            "severity": "warning",
            "message": (
                f"{brand_name}: content quality is strong (EQ {eq}) but publishing rate is low "
                f"(CV {cv}/100). Increase posting frequency to amplify reach."
            ),
        })

    if reel_share < 0.50:
        triggered.append({
            "severity": "warning",
            "message": (
                f"{brand_name}: only {reel_share * 100:.0f}% of posts are Reels "
                f"(target ≥50%). Shift the content mix — Reels receive 3–5× more reach."
            ),
        })

    if avg_gap_days is not None and avg_gap_days > 4:
        triggered.append({
            "severity": "warning",
            "message": (
                f"{brand_name}: average gap between posts is {avg_gap_days:.1f} days. "
                f"Inconsistent cadence suppresses algorithmic reach. Aim for ≤3 days."
            ),
        })

    if gm is not None and gm < 30 and eq > 50 and sufficient:
        triggered.append({
            "severity": "tip",
            "message": (
                f"{brand_name}: engagement is healthy (EQ {eq}) but follower growth is stalled "
                f"(GM {gm}/100). Consider an acquisition push via Meta Ads or a collab campaign."
            ),
        })

    if not triggered:
        triggered.append({
            "severity": "ok",
            "message": f"{brand_name}: on track. No corrective action required.",
        })

    triggered.sort(key=lambda r: _SEVERITY_ORDER[r["severity"]])
    return triggered
