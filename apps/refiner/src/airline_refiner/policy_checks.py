"""Narrow factual guards; free-form policy reasoning still needs calibrated judging."""

import re
from datetime import datetime, timedelta

from airline_refiner.models import OutcomeCheck, Simulation

# Match an affirmative elapsed-window explanation, not an explanation of advance
# purchase eligibility or a negated statement such as 'has not passed'.
EXPIRED_WINDOW = re.compile(
    r"\bwindow\s+"
    r"(?:(?:has|is|had)\s+)?(?:(?:likely|probably|already)\s+)*"
    r"(?:passed|expired|closed|over)\b",
    re.IGNORECASE,
)


def check_policy_facts(simulation: Simulation) -> list[OutcomeCheck]:
    checks = []
    for index, turn in enumerate(simulation.transcript):
        if turn.get("role") != "agent":
            continue
        message = turn.get("message") or ""
        if (
            not re.search(r"\b24[- ]hours?\b", message, re.IGNORECASE)
            or "cancel" not in message.casefold()
            or not EXPIRED_WINDOW.search(message)
        ):
            continue
        booking = simulation.fixture.get("booking") or {}
        now = simulation.fixture.get("business_time")
        created = booking.get("created_at")
        elapsed = None
        try:
            current, purchased = (
                datetime.fromisoformat(str(now)),
                datetime.fromisoformat(str(created)),
            )
            if current.tzinfo is not None and purchased.tzinfo is not None:
                elapsed = current - purchased
        except (ValueError, TypeError):
            pass
        checks.append(
            OutcomeCheck(
                name=f"policy:elapsed_cancellation_window:{index}",
                passed=elapsed is not None and elapsed > timedelta(hours=24),
                criteria=["understanding"],
                explanation=(
                    "Claiming that the 24-hour window elapsed requires purchase and business "
                    "timestamps more than 24 hours apart. "
                    "Advance-purchase eligibility is separate. "
                    f"business_time={now!r}, created_at={created!r}, elapsed={elapsed}."
                ),
                evidence=message,
            )
        )
    return checks
