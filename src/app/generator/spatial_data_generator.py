"""Deterministic synthetic data generator for the utility grid schema."""

from __future__ import annotations

import logging
import random
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from faker import Faker
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..data import (
    Crew,
    Event,
    EventType,
    GridAsset,
    Meter,
    Outage,
    OutageStatusLog,
    ServiceLocation,
    WorkOrder,
)


class SpatialDataGenerator:
    """Populates the grid-topology and outage tables with synthetic data.

    All coordinate generation is confined to the configured bounding box.
    """

    # Dallas / Fort Worth metro bounding box
    LAT_MIN: float = 32.0
    LAT_MAX: float = 33.0
    LON_MIN: float = -97.0
    LON_MAX: float = -96.0
    SUBSTATION_SPREAD: float = 0.12
    FEEDER_SPREAD: float = 0.20
    TRANSFORMER_SPREAD: float = 0.08
    SERVICE_LOCATION_SPREAD: float = 0.005

    REGIONS: list[str] = ["North", "South"]

    GENERATED_TABLES: list[str] = [
        "work_orders",
        "outage_status_log",
        "outages",
        "meters",
        "service_locations",
        "crews",
        "events",
        "event_types",
        "grid_assets",
    ]

    def __init__(self, seed: int = 42) -> None:
        self._fake = Faker()
        Faker.seed(seed)
        random.seed(seed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _uid(self) -> str:
        return str(uuid.uuid4())

    def _nearby_coordinates(
        self,
        parent_latitude: float,
        parent_longitude: float,
        spread: float,
    ) -> tuple[float, float]:
        latitude = parent_latitude + random.uniform(-spread, spread)
        longitude = parent_longitude + random.uniform(-spread, spread)
        return (
            min(self.LAT_MAX, max(self.LAT_MIN, latitude)),
            min(self.LON_MAX, max(self.LON_MIN, longitude)),
        )

    def _region(self) -> str:
        return random.choice(self.REGIONS)

    def _past_date(self, years: int = 10) -> date:
        return self._fake.date_between(start_date=f"-{years}y", end_date="today")

    def _now(self) -> datetime:
        return datetime.utcnow()

    def clear_generated_data(self, session: Session) -> None:
        """Truncate every table this generator writes to, in FK-safe order."""
        table_list = ", ".join(self.GENERATED_TABLES)
        session.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def execute_spatial_generation(
        self,
        session: Session,
        num_locations: int,
        crew_count: int,
        dry_run: bool = False,
    ) -> None:
        """Populate all tables in strict foreign-key-safe order.

        Parameters
        ----------
        session            : active SQLAlchemy Session
        num_locations      : number of ServiceLocations (and Meters) to create
        crew_count         : number of Crew records

        Outages are fixed, not parameterized: one storm outage (North region,
        CONFIRMED) plus three baseline outages (LOW/REPORTED, MEDIUM/CONFIRMED,
        HIGH/CREW_ASSIGNED). See STEP 6 below.
        """

        if not dry_run:
            self.clear_generated_data(session)

        logging.info("SpatialDataGenerator: starting generation")

        # ------------------------------------------------------------------
        # STEP 1 - Grid topology: substation -> feeder -> transformer
        # ------------------------------------------------------------------
        logging.info("SpatialDataGenerator: step 1/6 - grid topology")
        service_area_latitude = random.uniform(
            self.LAT_MIN + self.FEEDER_SPREAD,
            self.LAT_MAX - self.FEEDER_SPREAD,
        )
        service_area_longitude = random.uniform(
            self.LON_MIN + self.FEEDER_SPREAD,
            self.LON_MAX - self.FEEDER_SPREAD,
        )

        # Mirror one random offset so the two substations sit on opposite
        # sides of the shared center, instead of landing at random distances
        # (which could put them nearly on top of each other).
        substation_offset_latitude = random.uniform(-self.SUBSTATION_SPREAD, self.SUBSTATION_SPREAD)
        substation_offset_longitude = random.uniform(-self.SUBSTATION_SPREAD, self.SUBSTATION_SPREAD)

        substations: list[GridAsset] = []
        for i in range(2):
            sign = 1 if i == 0 else -1
            latitude = min(
                self.LAT_MAX,
                max(self.LAT_MIN, service_area_latitude + sign * substation_offset_latitude),
            )
            longitude = min(
                self.LON_MAX,
                max(self.LON_MIN, service_area_longitude + sign * substation_offset_longitude),
            )
            asset = GridAsset(
                asset_id=self._uid(),
                asset_type="SUBSTATION",
                asset_name=f"Substation {self._fake.city_suffix()} {i + 1}",
                parent_asset=None,
                voltage_kv=random.choice([69.0, 115.0, 138.0]),
                rated_capacity_kva=random.choice([15000.0, 30000.0]),
                install_date=self._past_date(20),
                asset_condition="INSTALLED",
                status="NORMAL",
                latitude=latitude,
                longitude=longitude,
                region=self._region(),
            )
            session.add(asset)
            substations.append(asset)

        feeders: list[GridAsset] = []
        for i in range(4):
            substation = random.choice(substations)
            latitude, longitude = self._nearby_coordinates(
                substation.latitude,
                substation.longitude,
                self.FEEDER_SPREAD,
            )
            asset = GridAsset(
                asset_id=self._uid(),
                asset_type="FEEDER",
                asset_name=f"Feeder-{100 + i}",
                parent_asset=substation.asset_id,
                voltage_kv=random.choice([12.47, 13.2, 25.0]),
                rated_capacity_kva=random.choice([5000.0, 8000.0]),
                install_date=self._past_date(15),
                asset_condition="INSTALLED",
                status="NORMAL",
                latitude=latitude,
                longitude=longitude,
                region=substation.region,
            )
            session.add(asset)
            feeders.append(asset)

        # Fixed at 20 - independent of num_locations (service locations/meters volume).
        transformer_count = 20
        transformers: list[GridAsset] = []
        for i in range(transformer_count):
            feeder = random.choice(feeders)
            latitude, longitude = self._nearby_coordinates(
                feeder.latitude,
                feeder.longitude,
                self.TRANSFORMER_SPREAD,
            )
            asset = GridAsset(
                asset_id=self._uid(),
                asset_type="TRANSFORMER",
                asset_name=f"XFMR-{1000 + i}",
                parent_asset=feeder.asset_id,
                voltage_kv=random.choice([0.12, 0.24, 4.16]),
                rated_capacity_kva=random.choice([500.0, 1000.0]),
                install_date=self._past_date(10),
                asset_condition="INSTALLED",
                status="NORMAL",
                latitude=latitude,
                longitude=longitude,
                region=feeder.region,
            )
            session.add(asset)
            transformers.append(asset)

        session.flush()

        # ------------------------------------------------------------------
        # STEP 2 - Event lookup and events
        # ------------------------------------------------------------------
        logging.info("SpatialDataGenerator: step 2/6 - events")
        event_types = [
            ("STORM", "Severe weather event"),
            ("VEHICLE", "Vehicle impact"),
            ("FIRE", "Fire-related incident"),
            ("EXPLOSION", "Explosion-related incident"),
        ]
        for code, description in event_types:
            session.add(EventType(event_type_code=code, description=description))
        session.flush()

        events: list[Event] = []

        # Guarantee a STORM event in the North region so the storm demo is stable
        # and the "major storm in the north" query has a concrete event to join to.
        storm_event = Event(
            event_id=self._uid(),
            event_type_code="STORM",
            name="North Region Storm",
            severity="HIGH",
            start_time=self._now() - timedelta(hours=random.randint(2, 72)),
            end_time=None,
            region="North",
        )
        session.add(storm_event)
        events.append(storm_event)

        # A small, deterministic variety of additional events - one LOW (North)
        # and one MEDIUM (South), so the outage-create UI's event picker has
        # options besides the storm, and each event's region matches the region
        # its own baseline outage's asset will be pinned to below. HIGH severity
        # is covered by the storm event itself - no separate HIGH event, so the
        # system has exactly three events total.
        for i, (severity, event_region) in enumerate([("LOW", "North"), ("MEDIUM", "South")]):
            event = Event(
                event_id=self._uid(),
                event_type_code=random.choice([code for code, _ in event_types]),
                name=f"Event {i + 2}",
                severity=severity,
                start_time=self._now() - timedelta(hours=random.randint(2, 72)),
                end_time=None,
                region=event_region,
            )
            session.add(event)
            events.append(event)
        session.flush()

        # ------------------------------------------------------------------
        # STEP 3 - Crews
        # ------------------------------------------------------------------
        logging.info("SpatialDataGenerator: step 3/6 - crews")
        crew_types = ["DISTRIBUTION", "TRANSMISSION", "EMERGENCY_RESPONSE", "METERING"]
        crew_statuses = ["AVAILABLE", "DISPATCHED", "OFF_DUTY"]
        crews: list[Crew] = []
        response_crews: list[Crew] = []

        for i in range(crew_count):
            ctype = random.choice(crew_types)
            crew = Crew(
                crew_id=self._uid(),
                crew_name=f"Crew {self._fake.last_name()}",
                crew_type=ctype,
                region=self.REGIONS[i % len(self.REGIONS)],
                base_location=self._fake.city(),
                crew_size=random.randint(2, 8),
                supervisor=self._fake.name(),
                status=random.choice(crew_statuses),
            )
            session.add(crew)
            crews.append(crew)
            if ctype in ("EMERGENCY_RESPONSE", "DISTRIBUTION"):
                response_crews.append(crew)

        session.flush()

        if not response_crews:
            response_crews = crews[:]

        # ------------------------------------------------------------------
        # STEP 4 - Service locations
        # ------------------------------------------------------------------
        logging.info("SpatialDataGenerator: step 4/6 - service locations")
        locations: list[ServiceLocation] = []
        location_types = ["RESIDENTIAL", "COMMERCIAL"]
        for _ in range(num_locations):
            transformer = random.choice(transformers)
            latitude, longitude = self._nearby_coordinates(
                transformer.latitude,
                transformer.longitude,
                self.SERVICE_LOCATION_SPREAD,
            )
            loc = ServiceLocation(
                location_id=self._uid(),
                address=self._fake.street_address(),
                city=self._fake.city(),
                state="TX",
                zip=self._fake.postcode(),
                location_type=random.choice(location_types),
                latitude=latitude,
                longitude=longitude,
                region=transformer.region,
                transformer_id=transformer.asset_id,
            )
            session.add(loc)
            locations.append(loc)

        session.flush()

        # ------------------------------------------------------------------
        # STEP 5 - Meters
        # ------------------------------------------------------------------
        logging.info("SpatialDataGenerator: step 5/6 - meters")
        meters: list[Meter] = []
        meter_types = ["SMART METER", "LEGACY AMR"]
        comm_types = ["RF MESH", "PLC", "CELLULAR"]
        for loc in locations:
            meter = Meter(
                meter_id=self._uid(),
                location_id=loc.location_id,
                meter_type=random.choice(meter_types),
                install_date=self._past_date(5),
                communication_type=random.choice(comm_types),
                status="ACTIVE",
            )
            session.add(meter)
            meters.append(meter)

        session.flush()

        # ------------------------------------------------------------------
        # STEP 6 - Outages and supporting status log/work orders
        #
        # Outage volume is DECOUPLED from transformer count: a transformer can
        # back many historical outages (chosen with replacement). Every outage
        # belongs to exactly one event (schema requires event_id NOT NULL) - a
        # standalone incident not tied to the storm or the extra seeded events
        # gets its own fresh one-row event, same as a real "tennis shoe on a
        # line" outage would. A dedicated cluster is pinned to NORTH-region
        # transformers and the STORM event, so "assets impacted by the storm
        # in the north" is both coherent and internally consistent.
        # ------------------------------------------------------------------
        logging.info("SpatialDataGenerator: step 6/6 - outages")
        priorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        def _make_outage(
            event_id: Optional[str],
            status: str,
            asset_pool: Optional[list[GridAsset]] = None,
        ) -> None:
            """Create one outage plus its detection log entry and restoration work order.

            event_id=None means a standalone incident - a fresh one-row event is
            created for it here, since every outage needs exactly one event.
            """
            xfmr = random.choice(asset_pool if asset_pool else transformers)  # with replacement
            start_dt = self._now() - timedelta(hours=random.randint(1, 48))

            resolved_event_id = event_id
            if resolved_event_id is None:
                standalone_event = Event(
                    event_id=self._uid(),
                    event_type_code=random.choice([code for code, _ in event_types]),
                    name=f"Standalone incident ({xfmr.region})",
                    severity="LOW",
                    start_time=start_dt,
                    end_time=None,
                    region=xfmr.region,
                )
                session.add(standalone_event)
                session.flush()
                resolved_event_id = standalone_event.event_id

            outage = Outage(
                outage_id=self._uid(),
                event_id=resolved_event_id,
                asset_id=xfmr.asset_id,
                impact_count=random.randint(5, 500),
                impact_magnitude=round(random.uniform(1.0, 40.0), 2),
            )
            session.add(outage)
            session.flush()

            session.add(
                OutageStatusLog(
                    outage_id=outage.outage_id,
                    event_type=status,
                    from_status=None,
                    to_status=status,
                    note="Synthetic outage creation",
                    event_time=start_dt,
                )
            )

            # grid_assets.status mirrors the outage's own lifecycle, except RESTORED
            # and CLOSED both mean the asset is back in service, so both map to
            # NORMAL. See docs/business-rules/asset-status-business-rules.md.
            xfmr.status = "NORMAL" if status in ("RESTORED", "CLOSED") else status

            # Same invariant the live transition() enforces: a crew/work order
            # only exists once the outage reaches CREW_ASSIGNED - a REPORTED or
            # CONFIRMED outage has no crew yet.
            if status in ("CREW_ASSIGNED", "RESTORED", "CLOSED"):
                available_crews = [c for c in response_crews if c.status == "AVAILABLE"]
                assigned_crew = random.choice(available_crews) if available_crews else random.choice(response_crews)
                assigned_crew.status = "DISPATCHED"
                session.add(
                    WorkOrder(
                        work_order_id=self._uid(),
                        outage_id=outage.outage_id,
                        asset_id=xfmr.asset_id,
                        crew_id=assigned_crew.crew_id,
                        wo_type="OUTAGE RESTORATION",
                        priority=random.choice(priorities),
                        status=random.choice(["OPEN", "ASSIGNED", "IN_PROGRESS", "COMPLETED"]),
                        created_date=start_dt,
                        scheduled_date=start_dt + timedelta(minutes=30),
                        completed_date=None,
                        estimated_hours=random.uniform(1.0, 8.0),
                        actual_hours=None,
                    )
                )
                # Outage already resolved (RESTORED/CLOSED) - release the crew right
                # back to AVAILABLE so it's free for a later outage in this same run.
                if status in ("RESTORED", "CLOSED"):
                    assigned_crew.status = "AVAILABLE"

        # Three outages total, one per severity/status pair - LOW/REPORTED,
        # MEDIUM/CONFIRMED, HIGH/CREW_ASSIGNED. Each outage's asset is pinned to
        # its event's own region (North for LOW/storm, South for MEDIUM), so an
        # outage's asset region and its event's region always agree.
        north_transformers = [t for t in transformers if t.region == "North"] or transformers
        south_transformers = [t for t in transformers if t.region == "South"] or transformers
        other_events = [e for e in events if e is not storm_event]
        baseline_severity_by_event = {e.event_id: e.severity for e in other_events}
        baseline_plan = [
            ("LOW", "REPORTED", north_transformers),
            ("MEDIUM", "CONFIRMED", south_transformers),
            ("HIGH", "CREW_ASSIGNED", north_transformers),
        ]
        for severity, status, asset_pool in baseline_plan:
            if severity == "HIGH":
                _make_outage(event_id=storm_event.event_id, status=status, asset_pool=asset_pool)
                continue
            matching_events = [
                event_id for event_id, sev in baseline_severity_by_event.items() if sev == severity
            ]
            event_id = random.choice(matching_events) if matching_events else None
            _make_outage(event_id=event_id, status=status, asset_pool=asset_pool)

        session.flush()

        logging.info("SpatialDataGenerator: generation complete")

        if dry_run:
            session.rollback()
        else:
            session.commit()
