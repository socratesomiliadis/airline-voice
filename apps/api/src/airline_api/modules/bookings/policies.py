"""Booking policy calculations sourced from the versioned fictional JSON files."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from airline_api.modules.bookings.errors import BookingError


def cents(amount: Any) -> int:
    value = Decimal(str(amount)) * 100
    if value != value.to_integral_value():
        raise ValueError("Policy fees must resolve to whole USD cents")
    return int(value)


class PolicyCatalog:
    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot
        self.version: str = snapshot["version"]
        self.rules: dict[str, Any] = snapshot["rules"]

    @classmethod
    def from_directory(cls, directory: Path) -> "PolicyCatalog":
        rules: dict[str, Any] = {}
        versions = set()
        scope = None
        for name in [
            "baggage",
            "booking_changes",
            "cancellation_and_refunds",
            "check_in",
            "pet_policy",
            "special_assistance",
        ]:
            document = json.loads((directory / f"{name}.json").read_text())
            versions.add(document["policy_version"])
            if scope is not None and scope != document["scope"]:
                raise ValueError("Policy scopes must agree")
            scope = document["scope"]
            for rule in document["policy"]["rules"]:
                if rule["id"] in rules:
                    raise ValueError("Policy rule IDs must be unique")
                rules[rule["id"]] = rule["details"]
        if len(versions) != 1:
            raise ValueError("Policy versions must agree")
        return cls({"version": versions.pop(), "scope": scope, "rules": rules})

    def allowance(self, tier: str, route: str) -> tuple[int, int]:
        rule = self.rules["baggage.checked_allowance"]
        return int(rule["included_pieces_by_fare"][tier][route]), int(
            rule["standard_weight_limit_kg_by_fare"][tier]
        )

    def bag_price(self, tier: str, route: str, ordinal: int, weight: Decimal, size: Decimal) -> int:
        piece_rule = self.rules["baggage.additional_piece_fees"]
        limits = self.rules["baggage.weight_and_size_fees"]
        if ordinal > piece_rule["maximum_standard_checked_pieces_per_passenger"]:
            raise BookingError(
                "baggage_limit_exceeded",
                f"At most {piece_rule['maximum_standard_checked_pieces_per_passenger']} "
                "standard checked bags are allowed per passenger.",
                422,
            )
        if (
            weight > limits["absolute_maximum_weight_kg"]
            or size > limits["absolute_maximum_dimension_sum_cm"]
        ):
            raise BookingError(
                "baggage_not_accepted",
                "This item exceeds standard checked-baggage limits; request special-item review.",
                422,
            )
        included, weight_limit = self.allowance(tier, route)
        additional = ordinal - included
        amount = 0
        if additional > 0:
            key = (
                "first_additional"
                if additional == 1
                else "second_additional"
                if additional == 2
                else "third_and_each_subsequent"
            )
            amount += cents(piece_rule["additional_piece_fees"][route][key])
        if weight > weight_limit:
            amount += cents(limits["overweight"]["fees"][route])
        if size > self.rules["baggage.checked_allowance"]["standard_maximum_dimension_sum_cm"]:
            amount += cents(limits["oversized"]["fees"][route])
        return amount

    def special_item_quote(self, item_type: str) -> int | None:
        if item_type == "cabin_pet":
            return cents(self.rules["pets.reservations_and_fees"]["fee"]["amount"])
        if item_type == "mobility_aid":
            return cents(self.rules["assistance.mobility"]["transport_fee"]["amount"])
        if item_type in {"stroller", "car_seat"}:
            return 0
        return None

    def disruption(
        self,
        route: str,
        status: str,
        departure: datetime,
        arrival: datetime,
        booked_departure: datetime,
        booked_arrival: datetime,
    ) -> bool:
        if status == "cancelled":
            return True
        events = self.rules["cancellation.airline_disruption"]["qualifying_events_any_one"]
        for event in events:
            if event["event"] == "departure_or_arrival_delayed_from_original_schedule":
                threshold = timedelta(minutes=event["minimum_minutes"][route])
                if (
                    departure - booked_departure >= threshold
                    or arrival - booked_arrival >= threshold
                ):
                    return True
            if event["event"] == "departure_moved_earlier":
                if booked_departure - departure >= timedelta(
                    minutes=event["minimum_minutes"][route]
                ):
                    return True
        return False

    def cancellation(
        self,
        tier: str,
        route: str,
        ticket_total: int,
        passengers: int,
        created: datetime,
        original_departure: datetime,
        now: datetime,
        disrupted: bool,
    ) -> dict[str, Any]:
        conditions = self.rules["cancellation.grace_period"]["all_conditions_required"]
        grace = (
            timedelta(0)
            <= now - created
            <= timedelta(hours=conditions["elapsed_hours_since_purchase_less_than_or_equal_to"])
        )
        grace = grace and original_departure - created >= timedelta(
            hours=conditions[
                "scheduled_hours_from_purchase_to_first_departure_greater_than_or_equal_to"
            ]
        )
        if grace or disrupted:
            return {
                "ticket_refund_cents": ticket_total,
                "credit_cents": 0,
                "cancellation_fee_cents": 0,
                "review_required": False,
                "reason": "airline_disruption" if disrupted else "grace_period",
            }
        rule = self.rules["cancellation.voluntary_by_fare"]["fare_rules"][tier]
        if rule["refund_type"] == "original_payment_method":
            return {
                "ticket_refund_cents": ticket_total,
                "credit_cents": 0,
                "cancellation_fee_cents": 0,
                "review_required": False,
                "reason": "refundable_fare",
            }
        fee = cents(rule.get("cancellation_fee_usd", {}).get(route, 0)) * passengers
        return {
            "ticket_refund_cents": 0,
            "credit_cents": 0,
            "cancellation_fee_cents": min(fee, ticket_total),
            "review_required": True,
            "reason": "travel_credit_pending_tax_breakdown"
            if rule["refund_type"] == "travel_credit"
            else "unused_tax_review",
            "review_note": (
                "The paid ticket value is recorded, but refundable taxes are not itemized. "
                "No tax refund or travel credit amount has been fabricated."
            ),
        }

    def change_fee(self, tier: str, route: str, passengers: int, disrupted: bool) -> int:
        if disrupted:
            return 0
        rule = self.rules["changes.voluntary"]["fare_rules"][tier]
        if not rule["changes_allowed"]:
            raise BookingError(
                "fare_change_not_allowed",
                "The basic fare does not allow voluntary rescheduling; "
                "cancellation and a new booking are separate options.",
            )
        return cents(rule["change_fee_usd"][route]) * passengers
