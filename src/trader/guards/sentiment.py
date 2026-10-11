"""Sentiment guard: sentiment score dropping -0.5 within 5 minutes exits 50%."""


def check(sentiment_now: float, sentiment_5m_ago: float) -> tuple[str, float, str]:
    delta = sentiment_now - sentiment_5m_ago
    if delta <= -0.5:
        return ("exit_frac", 0.50, f"sentiment_drop_{delta:.2f}_5m")
    return ("hold", 0.0, "sentiment_ok")
