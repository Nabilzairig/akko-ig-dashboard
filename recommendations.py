def generate_recommendations(brand_name, metrics_bundle, scores):
    """Evaluate ordered rule set and return all triggered recommendation strings."""
    eq = scores.get("engagement_quality") or 50
    cv = scores.get("content_velocity")   or 50
    gm = scores.get("growth_momentum")

    posting  = metrics_bundle["posting"]
    growth   = metrics_bundle["growth"]

    reel_share   = posting["reel_share"]
    avg_gap_days = posting["avg_gap_days"]
    sufficient   = growth["sufficient_data_for_growth"]

    triggered = []

    if eq < 40 and cv > 60:
        triggered.append(
            "Volume up, quality down. Audit creative direction before publishing more."
        )

    if eq > 60 and cv < 40:
        triggered.append(
            "Underpublished. Strong creative wasted. Increase posting frequency."
        )

    if reel_share < 0.50:
        triggered.append(
            f"Reel ratio at {reel_share * 100:.0f}%. Format underweighted. Shift mix toward reels."
        )

    if avg_gap_days is not None and avg_gap_days > 4:
        triggered.append(
            f"Posting gap averaging {avg_gap_days:.1f} days. Cadence inconsistent. Tighten schedule."
        )

    if gm is not None and gm < 30 and eq > 50 and sufficient:
        triggered.append(
            "Audience saturated. Engagement healthy but follower growth stalled. "
            "Run acquisition push via Meta Ads."
        )

    if not triggered:
        triggered.append("On track. No corrective action required.")

    return triggered
