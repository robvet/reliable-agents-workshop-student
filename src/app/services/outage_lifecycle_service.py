"""Outage lifecycle service - create outages and transition their status.

Deterministic write path: no agent, no LLM, no MCP. Talks directly to Postgres
via `GeneratorDatabase`, the app's one sanctioned direct-DB connection (same
one used by the `/generator/generate` and `/generator/clear` endpoints).
Every other feature reads through MCP; this is the exception for outage CRUD.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from ..data import Crew, Event, GeneratorDatabase, GridAsset, Outage, OutageStatusLog, WorkOrder

_VALID_STATUSES = ("REPORTED", "CONFIRMED", "CREW_ASSIGNED", "RESTORED", "CLOSED")

# Linear restoration lifecycle. Each status may only advance to the next one;
# CLOSED is terminal. Guards against skipping steps (e.g. REPORTED -> CLOSED).
_ALLOWED_NEXT_STATUS: dict[str, str] = {
    "REPORTED": "CONFIRMED",
    "CONFIRMED": "CREW_ASSIGNED",
    "CREW_ASSIGNED": "RESTORED",
    "RESTORED": "CLOSED",
}


def _asset_status_for(outage_status: str) -> str:
    """Map an outage's own status onto grid_assets.status.

    grid_assets.status only has 4 values in practice (REPORTED/CONFIRMED/
    CREW_ASSIGNED/NORMAL) - RESTORED and CLOSED both mean the asset is back in
    service, so both map to NORMAL. CLOSED still exists as the outage's own
    administrative closing step (required by create_outage()'s one-open-outage-
    per-asset guard), it just no longer changes what the asset itself reports.
    See docs/business-rules/asset-status-business-rules.md.
    """
    return "NORMAL" if outage_status in ("RESTORED", "CLOSED") else outage_status


class OutageLifecycleService:
    """Creates outages and records status transitions, with a paired history log."""

    def __init__(self, generator_database: GeneratorDatabase) -> None:
        self._generator_database = generator_database

    def _current_status(self, session, outage_id: str) -> Optional[str]:
        """Look up an outage's current status from its latest status-log row."""
        log = (
            session.query(OutageStatusLog)
            .filter(OutageStatusLog.outage_id == outage_id)
            .order_by(OutageStatusLog.event_time.desc())
            .first()
        )
        return log.to_status if log else None

    def _latest_work_order(self, session, outage_id: str) -> Optional[WorkOrder]:
        """Look up this outage's most recent work order, if any."""
        return (
            session.query(WorkOrder)
            .filter(WorkOrder.outage_id == outage_id)
            .order_by(WorkOrder.created_date.desc())
            .first()
        )

    def _assigned_crew_name(self, session, outage_id: str) -> Optional[str]:
        """Look up the crew name from this outage's work order, if any."""
        work_order = self._latest_work_order(session, outage_id)
        if work_order is None or work_order.crew_id is None:
            return None
        crew = session.get(Crew, work_order.crew_id)
        return crew.crew_name if crew else None

    def list_crews(self) -> list[dict]:
        """Return all crews for the crew-assignment picker."""
        session = self._generator_database.create_session()
        try:
            crews = session.query(Crew).order_by(Crew.crew_name).all()
            return [
                {
                    "crew_id": crew.crew_id,
                    "crew_name": crew.crew_name,
                    "crew_type": crew.crew_type,
                    "status": crew.status,
                }
                for crew in crews
            ]
        finally:
            session.close()

    def create_outage(
        self,
        asset_id: str,
        event_id: Optional[str] = None,
        impact_count: Optional[int] = None,
        impact_magnitude: Optional[float] = None,
    ) -> Outage:
        """Insert a new outage (status=REPORTED) and its REPORTED history event.

        The outage is thin: status, cause, and timing all live on the event or
        the status log, not on the outage row itself.

        event_id=None means no event was picked in the UI - a standalone,
        default LOW-severity event is created here instead, same pattern as
        spatial_data_generator.py's standalone-outage branch (minus the
        randomness). Outage.event_id is NOT NULL, so an event always has to
        exist before the outage row can be written.
        """
        session = self._generator_database.create_session()
        try:
            asset = session.get(GridAsset, asset_id)
            if asset is None:
                raise ValueError(f"Asset '{asset_id}' not found")

            # One open outage per asset at a time - RESTORED (or CLOSED) frees the
            # asset up for a new outage. RESTORED already means back in service;
            # CLOSED is just the outage's own later administrative close.
            for existing in session.query(Outage).filter(Outage.asset_id == asset_id).all():
                if self._current_status(session, existing.outage_id) not in ("RESTORED", "CLOSED"):
                    raise ValueError(
                        f"Asset '{asset_id}' already has an open outage "
                        f"({existing.outage_id}); restore it before creating a new one"
                    )

            resolved_event_id = event_id
            if resolved_event_id is None:
                default_event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type_code=None,
                    name=None,
                    severity="LOW",
                    region=asset.region,
                    start_time=datetime.utcnow(),
                    end_time=None,
                )
                session.add(default_event)
                session.flush()
                resolved_event_id = default_event.event_id
            else:
                event = session.get(Event, resolved_event_id)
                if event is None:
                    raise ValueError(f"Event '{resolved_event_id}' not found")

            outage = Outage(
                outage_id=str(uuid.uuid4()),
                asset_id=asset_id,
                event_id=resolved_event_id,
                impact_count=impact_count,
                impact_magnitude=impact_magnitude,
            )
            session.add(outage)
            session.flush()

            session.add(
                OutageStatusLog(
                    outage_id=outage.outage_id,
                    event_type="REPORTED",
                    to_status="REPORTED",
                    event_time=datetime.utcnow(),
                )
            )
            asset.status = _asset_status_for("REPORTED")
            session.commit()
            session.refresh(outage)
            logging.info(
                "OutageLifecycleService.create_outage: created outage_id=%s asset_id=%s",
                outage.outage_id,
                asset_id,
            )
            return outage
        except Exception:
            session.rollback()
            logging.exception("OutageLifecycleService.create_outage failed")
            raise
        finally:
            session.close()

    def transition(
        self,
        outage_id: str,
        to_status: str,
        note: Optional[str] = None,
        crew_id: Optional[str] = None,
    ) -> Outage:
        """Move an outage to a new status and record the transition in history.

        Demo mode: any valid status is accepted regardless of current status - the
        strict forward-only whitelist (_ALLOWED_NEXT_STATUS) is intentionally not
        enforced here, so a wrong pick can be corrected without fighting the guard.
        Re-enable the whitelist check before this is anything other than a demo.

        crew_id only matters the first time an outage reaches CREW_ASSIGNED - if a
        work order already exists, the same crew stays assigned regardless of what
        is passed here. Moving away from CREW_ASSIGNED to any other status (RESTORED,
        or even back to CONFIRMED/REPORTED) releases that crew back to AVAILABLE.
        """
        if to_status not in _VALID_STATUSES:
            raise ValueError(f"Invalid status '{to_status}', must be one of {_VALID_STATUSES}")

        session = self._generator_database.create_session()
        try:
            outage = session.get(Outage, outage_id)
            if outage is None:
                raise ValueError(f"Outage '{outage_id}' not found")

            from_status = self._current_status(session, outage_id)

            session.add(
                OutageStatusLog(
                    outage_id=outage_id,
                    event_type=to_status,
                    from_status=from_status,
                    to_status=to_status,
                    note=note,
                    event_time=datetime.utcnow(),
                )
            )
            if outage.asset_id is not None:
                asset = session.get(GridAsset, outage.asset_id)
                if asset is not None:
                    asset.status = _asset_status_for(to_status)

            work_order = self._latest_work_order(session, outage_id)
            if to_status == "CREW_ASSIGNED" and work_order is None:
                if crew_id is None:
                    raise ValueError("crew_id is required to assign a crew")
                crew = session.get(Crew, crew_id)
                if crew is None:
                    raise ValueError(f"Crew '{crew_id}' not found")
                session.add(
                    WorkOrder(
                        work_order_id=str(uuid.uuid4()),
                        outage_id=outage_id,
                        asset_id=outage.asset_id,
                        crew_id=crew_id,
                        wo_type="OUTAGE RESTORATION",
                        status="ASSIGNED",
                        created_date=datetime.utcnow(),
                    )
                )
                crew.status = "DISPATCHED"
            elif to_status != "CREW_ASSIGNED" and work_order is not None and work_order.status != "COMPLETED":
                # Moving away from CREW_ASSIGNED (forward to RESTORED, or backward to
                # CONFIRMED/REPORTED during a demo correction) frees the crew - it's no
                # longer actually working this outage.
                work_order.status = "COMPLETED"
                work_order.completed_date = datetime.utcnow()
                if work_order.crew_id is not None:
                    crew = session.get(Crew, work_order.crew_id)
                    if crew is not None:
                        crew.status = "AVAILABLE"

            session.commit()
            session.refresh(outage)
            logging.info(
                "OutageLifecycleService.transition: outage_id=%s %s -> %s",
                outage_id,
                from_status,
                to_status,
            )
            return outage
        except Exception:
            session.rollback()
            logging.exception("OutageLifecycleService.transition failed")
            raise
        finally:
            session.close()

    def update_event_severity(self, event_id: str, severity: str) -> Event:
        """Write a new severity onto the outage's linked event.

        Deterministic write only - no LLM call lives here. The caller (OutageAgent)
        is responsible for deciding whether a severity change is warranted (via
        LlmOutageNoteClassifier) and for checking the recommendation against the
        outage_note_triage skill's hazard_keywords before calling this method.
        """
        if severity not in ("LOW", "MEDIUM", "HIGH"):
            raise ValueError(f"Invalid severity '{severity}', must be LOW/MEDIUM/HIGH")

        session = self._generator_database.create_session()
        try:
            event = session.get(Event, event_id)
            if event is None:
                raise ValueError(f"Event '{event_id}' not found")
            event.severity = severity
            session.commit()
            session.refresh(event)
            logging.info(
                "OutageLifecycleService.update_event_severity: event_id=%s severity=%s",
                event_id,
                severity,
            )
            return event
        except Exception:
            session.rollback()
            logging.exception("OutageLifecycleService.update_event_severity failed")
            raise
        finally:
            session.close()

    def list_outages(self) -> list[dict]:
        """Return only OPEN outages (status not RESTORED/CLOSED) with their linked
        event's name/severity and current status, most recently started event
        first. Returns plain dicts (not ORM Outage objects) since this is a
        display-shaped read, not a write path.
        """
        session = self._generator_database.create_session()
        try:
            rows = (
                session.query(Outage, Event)
                .join(Event, Outage.event_id == Event.event_id)
                .order_by(Event.start_time.desc())
                .all()
            )
            result = []
            for outage, event in rows:
                status = self._current_status(session, outage.outage_id)
                if status in ("RESTORED", "CLOSED"):
                    continue
                result.append(
                    {
                        "outage_id": outage.outage_id,
                        "asset_id": outage.asset_id,
                        "event_id": outage.event_id,
                        "event_name": event.name,
                        "event_severity": event.severity,
                        "impact_count": outage.impact_count,
                        "impact_magnitude": outage.impact_magnitude,
                        "status": status,
                        "crew_name": self._assigned_crew_name(session, outage.outage_id),
                    }
                )
            return result
        finally:
            session.close()
