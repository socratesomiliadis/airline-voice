"""Transactional booking operations shared by REST and ElevenLabs webhook tools."""

import calendar
import hashlib
import json
import secrets
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from airline_api.infrastructure.database.models import (
    Airport,
    ApiOperation,
    Booking,
    BookingEvent,
    BookingExtra,
    BookingPassenger,
    Flight,
    FlightCabin,
    FlightFare,
    PassengerReservation,
)
from airline_api.modules.bookings.errors import BookingError
from airline_api.modules.bookings.policies import PolicyCatalog
from airline_api.modules.bookings.schemas import (
    AddBookingItems,
    BookFlight,
    BookingView,
    CancelBooking,
    EventView,
    ExtraView,
    FlightInformation,
    FlightInformationQuery,
    FlightInformationResult,
    FlightOffer,
    FlightSearch,
    FlightSearchResult,
    Mutation,
    PassengerView,
    RescheduleBooking,
)


class BookingService:
    def __init__(
        self,
        session: AsyncSession,
        policies: PolicyCatalog,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.policies = policies
        self.clock = clock or (lambda: datetime.now(UTC))

    async def search(self, query: FlightSearch) -> FlightSearchResult:
        origin = aliased(Airport)
        destination = aliased(Airport)
        statement = (
            select(Flight, FlightCabin, FlightFare, origin, destination)
            .join(FlightCabin, FlightCabin.flight_id == Flight.id)
            .join(
                FlightFare,
                (FlightFare.flight_id == FlightCabin.flight_id)
                & (FlightFare.seat_class == FlightCabin.seat_class),
            )
            .join(origin, origin.code == Flight.origin_code)
            .join(destination, destination.code == Flight.destination_code)
            .where(
                Flight.status == "scheduled",
                Flight.departure_at > self.clock(),
                FlightCabin.available_seats >= query.passengers,
            )
        )
        for airport, value in [(origin, query.origin), (destination, query.destination)]:
            if value:
                statement = statement.where(
                    or_(
                        func.upper(airport.code) == value.upper(),
                        func.lower(airport.city) == value.casefold(),
                    )
                )
        if query.departure_date is not None:
            statement = statement.where(
                cast(func.timezone(origin.timezone, Flight.departure_at), Date)
                == query.departure_date
            )
        local_date = cast(func.timezone(origin.timezone, Flight.departure_at), Date)
        if query.departure_date_from is not None:
            statement = statement.where(local_date >= query.departure_date_from)
        if query.departure_date_to is not None:
            statement = statement.where(local_date <= query.departure_date_to)
        if query.min_price_cents is not None:
            statement = statement.where(FlightFare.price_cents >= query.min_price_cents)
        if query.max_price_cents is not None:
            statement = statement.where(FlightFare.price_cents <= query.max_price_cents)
        if query.seat_class:
            statement = statement.where(FlightCabin.seat_class == query.seat_class)
        if query.fare_tier:
            statement = statement.where(FlightFare.fare_tier == query.fare_tier)
        order = (
            [FlightFare.price_cents, Flight.departure_at]
            if query.sort_by == "price"
            else [Flight.departure_at, FlightFare.price_cents]
        )
        statement = (
            statement.order_by(*order, Flight.id, FlightCabin.seat_class, FlightFare.fare_tier)
            .offset(query.offset)
            .limit(query.limit + 1)
        )
        rows = (await self.session.execute(statement)).all()
        offers = []
        for flight, cabin, fare, departure_airport, arrival_airport in rows[: query.limit]:
            pieces, weight = self.policies.allowance(fare.fare_tier, flight.route_type)
            offers.append(
                FlightOffer(
                    flight_id=flight.id,
                    flight_number=flight.flight_number,
                    origin=flight.origin_code,
                    destination=flight.destination_code,
                    origin_city=departure_airport.city,
                    destination_city=arrival_airport.city,
                    departure_at=flight.departure_at,
                    arrival_at=flight.arrival_at,
                    departure_local=flight.departure_at.astimezone(
                        ZoneInfo(departure_airport.timezone)
                    ),
                    arrival_local=flight.arrival_at.astimezone(ZoneInfo(arrival_airport.timezone)),
                    route_type=flight.route_type,
                    seat_class=cabin.seat_class,
                    fare_tier=fare.fare_tier,
                    available_seats=cabin.available_seats,
                    unit_price_cents=fare.price_cents,
                    total_price_cents=fare.price_cents * query.passengers,
                    currency=fare.currency,
                    checked_bags_per_passenger=pieces,
                    checked_bag_weight_limit_kg=weight,
                )
            )
        return FlightSearchResult(
            offers=offers, limit=query.limit, offset=query.offset, has_more=len(rows) > query.limit
        )

    async def flight_information(self, query: FlightInformationQuery) -> FlightInformationResult:
        origin, destination = aliased(Airport), aliased(Airport)
        rows = (
            await self.session.execute(
                select(Flight, origin, destination)
                .join(origin, origin.code == Flight.origin_code)
                .join(destination, destination.code == Flight.destination_code)
                .where(
                    func.upper(Flight.flight_number) == query.flight_number.upper(),
                    cast(func.timezone(origin.timezone, Flight.departure_at), Date)
                    == query.departure_date,
                )
                .order_by(Flight.departure_at, Flight.id)
            )
        ).all()
        return FlightInformationResult(
            flights=[
                FlightInformation.model_validate(
                    {
                        "flight_id": flight.id,
                        "flight_number": flight.flight_number,
                        "origin": flight.origin_code,
                        "destination": flight.destination_code,
                        "departure_local": flight.departure_at.astimezone(
                            ZoneInfo(departure.timezone)
                        ),
                        "arrival_local": flight.arrival_at.astimezone(ZoneInfo(arrival.timezone)),
                        "origin_timezone": departure.timezone,
                        "destination_timezone": arrival.timezone,
                        "status": flight.status,
                        "gate": flight.gate,
                    }
                )
                for flight, departure, arrival in rows
            ]
        )

    async def get(self, reference: str) -> BookingView:
        booking = await self._find(reference)
        return await self._view(booking)

    async def list_bookings(
        self, limit: int = 50, offset: int = 0, caller_id: str | None = None
    ) -> list[BookingView]:
        statement = (
            select(Booking)
            .order_by(Booking.created_at.desc(), Booking.id)
            .limit(limit)
            .offset(offset)
        )
        if caller_id:
            statement = statement.where(Booking.caller_id == caller_id)
        bookings = (await self.session.scalars(statement)).all()
        return [await self._view(booking) for booking in bookings]

    async def book(self, request: BookFlight) -> BookingView:
        return await self._mutate("book", request, lambda: self._book(request))

    async def cancel(self, reference: str, request: CancelBooking) -> BookingView:
        return await self._mutate(
            f"cancel:{reference.upper()}", request, lambda: self._cancel(reference, request)
        )

    async def reschedule(self, reference: str, request: RescheduleBooking) -> BookingView:
        return await self._mutate(
            f"reschedule:{reference.upper()}", request, lambda: self._reschedule(reference, request)
        )

    async def add_items(self, reference: str, request: AddBookingItems) -> BookingView:
        return await self._mutate(
            f"items:{reference.upper()}", request, lambda: self._add_items(reference, request)
        )

    async def _mutate(
        self, operation: str, request: Mutation, action: Callable[[], Awaitable[BookingView]]
    ) -> BookingView:
        payloads = [request.model_dump(mode="json")]
        if isinstance(request, BookFlight):
            # Before seat requests existed, serialized passengers had no preference key.
            # Accept those durable receipts without changing retries into new reservations.
            legacy = request.model_dump(mode="json")
            for passenger in legacy["passengers"]:
                if passenger.get("seat_preference") is None:
                    passenger.pop("seat_preference", None)
            payloads.append(legacy)
        fingerprints = [
            hashlib.sha256(
                json.dumps(
                    {"operation": operation, "request": payload},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            for payload in payloads
        ]
        try:
            async with self.session.begin():
                await self.session.execute(
                    insert(ApiOperation)
                    .values(
                        idempotency_key=request.idempotency_key,
                        request_hash=fingerprints[0],
                        operation=operation,
                        response=None,
                        created_at=self.clock(),
                    )
                    .on_conflict_do_nothing()
                )
                receipt = (
                    await self.session.scalars(
                        select(ApiOperation)
                        .where(ApiOperation.idempotency_key == request.idempotency_key)
                        .with_for_update()
                    )
                ).one()
                if receipt.request_hash not in fingerprints:
                    raise BookingError(
                        "idempotency_conflict",
                        "This idempotency key was already used for a different request.",
                    )
                if receipt.response is not None:
                    return BookingView.model_validate(receipt.response)
                result = await action()
                receipt.response = result.model_dump(mode="json")
                await self.session.flush()
            return result
        except IntegrityError as exc:
            code = (
                "passenger_already_booked"
                if "passenger_reservations" in str(exc.orig)
                else "booking_conflict"
            )
            raise BookingError(
                code,
                "A passenger already has this flight booked, or a database conflict occurred. "
                "No changes were committed.",
            ) from exc

    async def _find(self, reference: str, lock: bool = False) -> Booking:
        try:
            predicate = Booking.id == UUID(reference)
        except ValueError:
            predicate = Booking.reference == reference.strip().upper()
        statement = select(Booking).where(predicate)
        if lock:
            statement = statement.with_for_update()
        booking = await self.session.scalar(statement)
        if booking is None:
            raise BookingError("booking_not_found", "No booking matches that reference.", 404)
        return booking

    async def _lock_inventory(
        self, keys: list[tuple[UUID, str]]
    ) -> tuple[dict[UUID, Flight], dict[tuple[UUID, str], FlightCabin]]:
        flights: dict[UUID, Flight] = {}
        cabins: dict[tuple[UUID, str], FlightCabin] = {}
        for flight_id in sorted({key[0] for key in keys}, key=str):
            flight = await self.session.scalar(
                select(Flight).where(Flight.id == flight_id).with_for_update()
            )
            if flight is None:
                raise BookingError("flight_not_found", "The selected flight does not exist.", 404)
            flights[flight_id] = flight
        for flight_id, seat_class in sorted(set(keys), key=lambda key: (str(key[0]), key[1])):
            cabin = await self.session.scalar(
                select(FlightCabin)
                .where(FlightCabin.flight_id == flight_id, FlightCabin.seat_class == seat_class)
                .with_for_update()
            )
            if cabin is None:
                raise BookingError(
                    "cabin_not_found", "That cabin is not offered on the selected flight.", 404
                )
            cabins[(flight_id, seat_class)] = cabin
        return flights, cabins

    async def _fare(self, flight_id: UUID, seat_class: str, tier: str, expected: int) -> FlightFare:
        fare = await self.session.scalar(
            select(FlightFare)
            .where(
                FlightFare.flight_id == flight_id,
                FlightFare.seat_class == seat_class,
                FlightFare.fare_tier == tier,
            )
            .with_for_update()
        )
        if fare is None:
            raise BookingError(
                "fare_not_found", "That fare tier is not offered in the selected cabin.", 404
            )
        if fare.price_cents != expected:
            raise BookingError(
                "fare_price_changed",
                "The quoted fare changed. Search again and confirm the new price.",
                current_unit_price_cents=fare.price_cents,
            )
        return fare

    def _scheduled(self, flight: Flight) -> None:
        if flight.status != "scheduled" or flight.departure_at <= self.clock():
            raise BookingError(
                "flight_unavailable", "The flight is not scheduled for future departure."
            )

    @staticmethod
    def _take(cabin: FlightCabin, count: int) -> None:
        if cabin.available_seats < count:
            raise BookingError(
                "insufficient_seats",
                "Not enough seats remain in this cabin.",
                available_seats=cabin.available_seats,
            )
        cabin.available_seats -= count

    async def _book(self, request: BookFlight) -> BookingView:
        flights, cabins = await self._lock_inventory([(request.flight_id, request.seat_class)])
        flight = flights[request.flight_id]
        self._scheduled(flight)
        fare = await self._fare(
            flight.id, request.seat_class, request.fare_tier, request.expected_unit_price_cents
        )
        self._take(cabins[(flight.id, request.seat_class)], len(request.passengers))
        now = self.clock()
        booking = Booking(
            id=uuid4(),
            reference=secrets.token_hex(5).upper(),
            caller_id=request.caller_id,
            flight_id=flight.id,
            seat_class=request.seat_class,
            fare_tier=request.fare_tier,
            status="confirmed",
            passenger_count=len(request.passengers),
            unit_price_cents=fare.price_cents,
            ticket_total_cents=fare.price_cents * len(request.passengers),
            currency=fare.currency,
            original_departure_at=flight.departure_at,
            booked_departure_at=flight.departure_at,
            booked_arrival_at=flight.arrival_at,
            created_at=now,
            updated_at=now,
            cancelled_at=None,
            policy_version=self.policies.version,
            policy_snapshot=self.policies.snapshot,
        )
        self.session.add(booking)
        await self.session.flush()
        for passenger in request.passengers:
            self.session.add(BookingPassenger(booking_id=booking.id, **passenger.model_dump()))
        await self.session.flush()
        for passenger in request.passengers:
            self.session.add(
                PassengerReservation(
                    booking_id=booking.id, passenger_id=passenger.passenger_id, flight_id=flight.id
                )
            )
        self._event(
            booking,
            "booked",
            request.caller_id,
            charged=booking.ticket_total_cents,
            details={
                "flight_id": str(flight.id),
                "seat_class": booking.seat_class,
                "fare_tier": booking.fare_tier,
            },
        )
        await self.session.flush()
        return await self._view(booking)

    def _disrupted(self, booking: Booking, flight: Flight, policy: PolicyCatalog) -> bool:
        return policy.disruption(
            flight.route_type,
            flight.status,
            flight.departure_at,
            flight.arrival_at,
            booking.booked_departure_at,
            booking.booked_arrival_at,
        )

    async def _cancel(self, reference: str, request: CancelBooking) -> BookingView:
        booking = await self._find(reference, lock=True)
        if booking.status == "cancelled":
            return await self._view(booking)
        flights, cabins = await self._lock_inventory([(booking.flight_id, booking.seat_class)])
        flight = flights[booking.flight_id]
        policy = PolicyCatalog(booking.policy_snapshot)
        disrupted = self._disrupted(booking, flight, policy)
        if flight.status in {"departed", "arrived"} or (
            flight.departure_at <= self.clock() and not disrupted
        ):
            raise BookingError(
                "departure_passed",
                "Post-departure cancellation and no-show settlement require manual review.",
            )
        settlement = policy.cancellation(
            booking.fare_tier,
            flight.route_type,
            booking.ticket_total_cents,
            booking.passenger_count,
            booking.created_at,
            booking.original_departure_at,
            self.clock(),
            disrupted,
        )
        cabin = cabins[(booking.flight_id, booking.seat_class)]
        if cabin.available_seats + booking.passenger_count > cabin.capacity:
            raise BookingError(
                "inventory_conflict", "Seat inventory needs reconciliation before cancellation."
            )
        cabin.available_seats += booking.passenger_count
        await self.session.execute(
            delete(PassengerReservation).where(PassengerReservation.booking_id == booking.id)
        )
        extras = (
            await self.session.scalars(
                select(BookingExtra).where(BookingExtra.booking_id == booking.id)
            )
        ).all()
        ancillary_refund = 0
        for item in extras:
            if item.status == "confirmed":
                ancillary_refund += item.price_cents
            item.status = "cancelled"
        booking.status = "cancelled"
        booking.cancelled_at = self.clock()
        booking.updated_at = self.clock()
        settlement["ancillary_refund_cents"] = ancillary_refund
        self._event(
            booking,
            "cancelled",
            request.caller_id,
            refunded=settlement["ticket_refund_cents"] + ancillary_refund,
            credit=settlement["credit_cents"],
            details=settlement,
        )
        await self.session.flush()
        return await self._view(booking)

    async def _reschedule(self, reference: str, request: RescheduleBooking) -> BookingView:
        booking = await self._find(reference, lock=True)
        if booking.status != "confirmed":
            raise BookingError("booking_not_active", "A cancelled booking cannot be rescheduled.")
        if (booking.flight_id, booking.seat_class, booking.fare_tier) == (
            request.flight_id,
            request.seat_class,
            request.fare_tier,
        ):
            return await self._view(booking)
        old_key = (booking.flight_id, booking.seat_class)
        new_key = (request.flight_id, request.seat_class)
        flights, cabins = await self._lock_inventory([old_key, new_key])
        old_flight, new_flight = flights[booking.flight_id], flights[request.flight_id]
        self._scheduled(new_flight)
        if (old_flight.origin_code, old_flight.destination_code) != (
            new_flight.origin_code,
            new_flight.destination_code,
        ):
            raise BookingError(
                "route_mismatch", "Rescheduling requires the same origin and destination.", 422
            )
        policy = PolicyCatalog(booking.policy_snapshot)
        disrupted = self._disrupted(booking, old_flight, policy)
        if old_flight.status in {"departed", "arrived"} or (
            old_flight.departure_at <= self.clock() and not disrupted
        ):
            raise BookingError("departure_passed", "Post-departure changes require manual review.")
        change_fee = policy.change_fee(
            booking.fare_tier, old_flight.route_type, booking.passenger_count, disrupted
        )
        fare = await self._fare(
            new_flight.id, request.seat_class, request.fare_tier, request.expected_unit_price_cents
        )
        if old_key != new_key:
            self._take(cabins[new_key], booking.passenger_count)
            if cabins[old_key].available_seats + booking.passenger_count > cabins[old_key].capacity:
                raise BookingError(
                    "inventory_conflict", "Original seat inventory needs reconciliation."
                )
            cabins[old_key].available_seats += booking.passenger_count
        if booking.flight_id != new_flight.id:
            await self.session.execute(
                delete(PassengerReservation).where(PassengerReservation.booking_id == booking.id)
            )
            passengers = (
                await self.session.scalars(
                    select(BookingPassenger).where(BookingPassenger.booking_id == booking.id)
                )
            ).all()
            for passenger in passengers:
                self.session.add(
                    PassengerReservation(
                        booking_id=booking.id,
                        passenger_id=passenger.passenger_id,
                        flight_id=new_flight.id,
                    )
                )
        old_total = booking.ticket_total_cents
        old_tier = booking.fare_tier
        new_total = fare.price_cents * booking.passenger_count
        difference = 0 if disrupted else new_total - old_total
        # Disruption rebooking waives fare differences; retain the actual paid value.
        booking.unit_price_cents = booking.unit_price_cents if disrupted else fare.price_cents
        booking.ticket_total_cents = booking.unit_price_cents * booking.passenger_count
        booking.flight_id, booking.seat_class, booking.fare_tier = (
            new_flight.id,
            request.seat_class,
            request.fare_tier,
        )
        booking.booked_departure_at, booking.booked_arrival_at = (
            new_flight.departure_at,
            new_flight.arrival_at,
        )
        booking.updated_at = self.clock()
        extras = (
            await self.session.scalars(
                select(BookingExtra)
                .where(BookingExtra.booking_id == booking.id)
                .order_by(BookingExtra.created_at, BookingExtra.id)
            )
        ).all()
        extra_difference = self._reprice_bags(
            extras, booking.fare_tier, new_flight.route_type, policy
        )
        refund = max(-extra_difference, 0)
        credit = 0
        if difference < 0:
            treatment = policy.rules["changes.voluntary"]["negative_fare_difference"][old_tier]
            if treatment == "travel_credit":
                credit = -difference
            else:
                refund += -difference
        details: dict[str, Any] = {
            "old_flight_id": str(old_key[0]),
            "new_flight_id": str(new_flight.id),
            "old_ticket_total_cents": old_total,
            "ticket_total_cents": booking.ticket_total_cents,
            "fare_difference_cents": difference,
            "change_fee_cents": change_fee,
            "baggage_adjustment_cents": extra_difference,
            "airline_disruption": disrupted,
        }
        if credit:
            months = int(policy.rules["cancellation.travel_credits"]["validity_months_from_issue"])
            now = self.clock()
            year, month_zero = divmod(now.year * 12 + now.month - 1 + months, 12)
            expiry = now.replace(
                year=year,
                month=month_zero + 1,
                day=min(now.day, calendar.monthrange(year, month_zero + 1)[1]),
            )
            details["credit_terms"] = {
                "expires_at": expiry.isoformat(),
                "transferable": False,
                "passenger_ids": [
                    passenger.passenger_id
                    for passenger in (
                        await self.session.scalars(
                            select(BookingPassenger).where(
                                BookingPassenger.booking_id == booking.id
                            )
                        )
                    ).all()
                ],
            }
        self._event(
            booking,
            "rescheduled",
            request.caller_id,
            charged=change_fee + max(difference, 0) + max(extra_difference, 0),
            refunded=refund,
            credit=credit,
            details=details,
        )
        await self.session.flush()
        return await self._view(booking)

    def _reprice_bags(
        self, items: Sequence[BookingExtra], tier: str, route: str, policy: PolicyCatalog
    ) -> int:
        counts: dict[str, int] = {}
        difference = 0
        for item in items:
            if item.item_type != "checked_bag" or item.status != "confirmed":
                continue
            assert item.weight_kg is not None and item.length_cm is not None
            assert item.width_cm is not None and item.height_cm is not None
            counts[item.passenger_id] = counts.get(item.passenger_id, 0) + 1
            size = sum((item.length_cm, item.width_cm, item.height_cm), Decimal(0))
            price = policy.bag_price(tier, route, counts[item.passenger_id], item.weight_kg, size)
            difference += price - item.price_cents
            item.price_cents = price
            item.quoted_price_cents = price
        return difference

    async def _add_items(self, reference: str, request: AddBookingItems) -> BookingView:
        booking = await self._find(reference, lock=True)
        if booking.status != "confirmed":
            raise BookingError(
                "booking_not_active", "Items cannot be added to a cancelled booking."
            )
        flights, _ = await self._lock_inventory([(booking.flight_id, booking.seat_class)])
        flight = flights[booking.flight_id]
        self._scheduled(flight)
        policy = PolicyCatalog(booking.policy_snapshot)
        passengers = set(
            (
                await self.session.scalars(
                    select(BookingPassenger.passenger_id).where(
                        BookingPassenger.booking_id == booking.id
                    )
                )
            ).all()
        )
        previous = (
            await self.session.scalars(
                select(BookingExtra)
                .where(BookingExtra.booking_id == booking.id)
                .order_by(BookingExtra.created_at, BookingExtra.id)
            )
        ).all()
        counts: dict[str, int] = {}
        for existing_item in previous:
            if existing_item.item_type == "checked_bag" and existing_item.status == "confirmed":
                counts[existing_item.passenger_id] = counts.get(existing_item.passenger_id, 0) + 1
        charged = 0
        for item in request.items:
            if item.passenger_id not in passengers:
                raise BookingError(
                    "passenger_not_on_booking",
                    "Every item must belong to a passenger on this booking.",
                    422,
                )
            price = 0
            quote = policy.special_item_quote(item.item_type)
            status = "pending_confirmation"
            if item.item_type == "checked_bag":
                assert (
                    item.weight_kg is not None
                    and item.length_cm is not None
                    and item.width_cm is not None
                    and item.height_cm is not None
                )
                counts[item.passenger_id] = counts.get(item.passenger_id, 0) + 1
                price = policy.bag_price(
                    booking.fare_tier,
                    flight.route_type,
                    counts[item.passenger_id],
                    item.weight_kg,
                    item.length_cm + item.width_cm + item.height_cm,
                )
                quote, status = price, "confirmed"
            charged += price
            self.session.add(
                BookingExtra(
                    id=uuid4(),
                    booking_id=booking.id,
                    passenger_id=item.passenger_id,
                    item_type=item.item_type,
                    status=status,
                    weight_kg=item.weight_kg,
                    length_cm=item.length_cm,
                    width_cm=item.width_cm,
                    height_cm=item.height_cm,
                    price_cents=price,
                    quoted_price_cents=quote,
                    created_at=datetime.now(UTC),
                    details={
                        "description": item.description,
                        "confirmation_required": status == "pending_confirmation",
                    },
                )
            )
        booking.updated_at = self.clock()
        self._event(
            booking,
            "items_added",
            request.caller_id,
            charged=charged,
            details={"item_count": len(request.items), "special_items_require_confirmation": True},
        )
        await self.session.flush()
        return await self._view(booking)

    def _event(
        self,
        booking: Booking,
        action: str,
        caller: str,
        charged: int = 0,
        refunded: int = 0,
        credit: int = 0,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            BookingEvent(
                id=uuid4(),
                booking_id=booking.id,
                action=action,
                caller_id=caller,
                charged_cents=charged,
                refunded_cents=refunded,
                credit_cents=credit,
                details={
                    **(details or {}),
                    "payment_mode": "simulation",
                    "policy_version": booking.policy_version,
                    "effective_at": self.clock().isoformat(),
                },
                created_at=datetime.now(UTC),
            )
        )

    async def _view(self, booking: Booking) -> BookingView:
        flight = await self.session.get(Flight, booking.flight_id)
        assert flight is not None
        departure_airport = await self.session.get(Airport, flight.origin_code)
        arrival_airport = await self.session.get(Airport, flight.destination_code)
        assert departure_airport is not None and arrival_airport is not None
        passengers = (
            await self.session.scalars(
                select(BookingPassenger)
                .where(BookingPassenger.booking_id == booking.id)
                .order_by(BookingPassenger.passenger_id)
            )
        ).all()
        extras = (
            await self.session.scalars(
                select(BookingExtra)
                .where(BookingExtra.booking_id == booking.id)
                .order_by(BookingExtra.created_at, BookingExtra.id)
            )
        ).all()
        events = (
            await self.session.scalars(
                select(BookingEvent)
                .where(BookingEvent.booking_id == booking.id)
                .order_by(BookingEvent.created_at, BookingEvent.id)
            )
        ).all()
        return BookingView(
            id=booking.id,
            reference=booking.reference,
            caller_id=booking.caller_id,
            status=booking.status,
            flight={
                "id": flight.id,
                "flight_number": flight.flight_number,
                "origin": flight.origin_code,
                "destination": flight.destination_code,
                "departure_at": flight.departure_at,
                "arrival_at": flight.arrival_at,
                "departure_local": flight.departure_at.astimezone(
                    ZoneInfo(departure_airport.timezone)
                ),
                "arrival_local": flight.arrival_at.astimezone(ZoneInfo(arrival_airport.timezone)),
                "origin_timezone": departure_airport.timezone,
                "destination_timezone": arrival_airport.timezone,
                "route_type": flight.route_type,
                "status": flight.status,
                "gate": flight.gate,
            },
            seat_class=booking.seat_class,
            fare_tier=booking.fare_tier,
            passengers=[
                PassengerView.model_validate(
                    {
                        "passenger_id": passenger.passenger_id,
                        "full_name": passenger.full_name,
                        "seat_preference": passenger.seat_preference,
                        "seat_preference_status": (
                            "requested" if passenger.seat_preference else "not_requested"
                        ),
                    }
                )
                for passenger in passengers
            ],
            unit_price_cents=booking.unit_price_cents,
            ticket_total_cents=booking.ticket_total_cents,
            currency=booking.currency,
            policy_version=booking.policy_version,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
            cancelled_at=booking.cancelled_at,
            extras=[ExtraView.model_validate(item) for item in extras],
            events=[EventView.model_validate(event) for event in events],
            total_charged_cents=sum(event.charged_cents for event in events),
            total_refunded_cents=sum(event.refunded_cents for event in events),
            total_credit_cents=sum(event.credit_cents for event in events),
        )
