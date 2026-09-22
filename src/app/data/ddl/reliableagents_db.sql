-- ============================================================================
-- Reliable Agents — Database Schema (v2, post-events-refactor)
-- Single PostgreSQL database. 10 tables + 3 views. See
-- specs/09-12-Database-Agent-Refactor.md for the full design rationale.
--
-- customers/outage_reports/meter_readings intentionally removed - this app is
-- an internal operations tool (asset detection, outage management,
-- restoration); customer data structurally belongs in a separate system
-- (CIS), not co-located here.
--
-- Usage:
--   createdb reliableagents_db
--   psql -d reliableagents_db -f reliableagents_db.sql
--
-- Re-runnable: the DROP block below rebuilds a clean schema each run.
-- ============================================================================

-- ------------------------------------------------- clean rebuild (idempotent)
DROP VIEW IF EXISTS asset_meter_map CASCADE;
DROP VIEW IF EXISTS event_current_threats CASCADE;
DROP VIEW IF EXISTS outage_current_status CASCADE;

DROP TABLE IF EXISTS work_orders       CASCADE;
DROP TABLE IF EXISTS event_asset_threat CASCADE;
DROP TABLE IF EXISTS outage_status_log CASCADE;
DROP TABLE IF EXISTS outages           CASCADE;
DROP TABLE IF EXISTS events            CASCADE;
DROP TABLE IF EXISTS event_types       CASCADE;
DROP TABLE IF EXISTS crews             CASCADE;
DROP TABLE IF EXISTS meters            CASCADE;
DROP TABLE IF EXISTS service_locations CASCADE;
DROP TABLE IF EXISTS grid_assets       CASCADE;

-- ------------------------------------------------------------------ topology
CREATE TABLE grid_assets (
    asset_id            varchar(36) PRIMARY KEY,
    asset_type          varchar(50)  CHECK (asset_type IN ('SUBSTATION','FEEDER','TRANSFORMER')),
    asset_name          varchar(120),
    parent_asset        varchar(36) REFERENCES grid_assets(asset_id),
    voltage_kv          double precision,
    rated_capacity_kva  double precision,
    install_date        date,
    -- Asset lifecycle - is this asset commissioned and in service? Unrelated
    -- to whether it currently has an outage. See docs/business-rules/
    -- asset-status-business-rules.md.
    asset_condition     varchar(30)  CHECK (asset_condition IN ('INSTALLED','MAINTENANCE','RETIRED')),
    -- Real-time outage state, kept in sync by OutageLifecycleService on every
    -- outage create/transition. NORMAL = no open outage. See the same doc.
    status              varchar(30)  CHECK (status IN ('REPORTED','CONFIRMED','CREW_ASSIGNED','RESTORED','NORMAL')),
    latitude            double precision,
    longitude           double precision,
    region              varchar(60)
);

CREATE TABLE service_locations (
    location_id     varchar(36) PRIMARY KEY,
    address         varchar(200),
    city            varchar(80),
    state           varchar(2),
    zip             varchar(10),
    location_type   varchar(20) CHECK (location_type IN ('RESIDENTIAL','COMMERCIAL')),
    latitude        double precision,
    longitude       double precision,
    region          varchar(60),
    transformer_id  varchar(36) REFERENCES grid_assets(asset_id)
);

-- -------------------------------------------------------------------- meters
CREATE TABLE meters (
    meter_id            varchar(36) PRIMARY KEY,
    location_id         varchar(36) REFERENCES service_locations(location_id),
    meter_type          varchar(30),
    communication_type  varchar(20),
    install_date        date,
    status              varchar(20) CHECK (status IN ('ACTIVE','INACTIVE','FAULTED'))
);

-- Pre-joins the full substation -> feeder -> transformer -> service_location ->
-- meter chain, so "meters affected by an outage on asset X" is one flat WHERE
-- clause instead of a hierarchy walk (no recursive CTE, no parent_asset
-- traversal needed by whatever queries it). Wired to AssetAgent's deterministic
-- downstream-assets lookup - see docs/business-rules/fixed-graph-traversal-query-for-assets.md.
CREATE VIEW asset_meter_map AS
SELECT
    substation.asset_id AS substation_id,
    feeder.asset_id      AS feeder_id,
    xfmr.asset_id        AS transformer_id,
    sl.location_id,
    m.meter_id
FROM grid_assets xfmr
JOIN grid_assets feeder     ON feeder.asset_id = xfmr.parent_asset
JOIN grid_assets substation ON substation.asset_id = feeder.parent_asset
JOIN service_locations sl   ON sl.transformer_id = xfmr.asset_id
JOIN meters m                ON m.location_id = sl.location_id
WHERE xfmr.asset_type = 'TRANSFORMER';

-- --------------------------------------------------------------------- crews
CREATE TABLE crews (
    crew_id        varchar(36) PRIMARY KEY,
    crew_name      varchar(100),
    crew_type      varchar(40) CHECK (crew_type IN ('DISTRIBUTION','EMERGENCY_RESPONSE','METERING','TRANSMISSION')),
    region         varchar(60),
    base_location  varchar(120),
    crew_size      integer,
    supervisor     varchar(100),
    status         varchar(20) CHECK (status IN ('AVAILABLE','DISPATCHED','OFF_DUTY'))
);

-- ---------------------------------------------------------------------------
-- EVENTS — the primitive. Any occurrence, tiny or huge, is one row here.
-- Replaces major_events + major_event_types. Does not know about outages.
-- "Major" is an instance fact (severity), never derived from event_type_code.
-- ---------------------------------------------------------------------------

-- Lookup: extensible business vocabulary (users add types over time).
-- Superset of the old major_event_types (STORM/VEHICLE/FIRE/EXPLOSION/...)
-- and the old outages.cause (WEATHER/EQUIPMENT_FAILURE/VEGETATION/...) -
-- type and cause were the same idea at two granularities; now one vocabulary.
CREATE TABLE event_types (
    event_type_code  varchar(30) PRIMARY KEY,
    description      varchar(120)
);

CREATE TABLE events (
    event_id         varchar(36) PRIMARY KEY,
    event_type_code  varchar(30) REFERENCES event_types(event_type_code),
    name             varchar(120),
    severity         varchar(20) CHECK (severity IN ('LOW','MEDIUM','HIGH')),
    region           varchar(60),
    start_time       timestamp without time zone NOT NULL,
    end_time         timestamp without time zone
);

-- ------------------------------------------------------------------- outages
-- Thin: references events.event_id. cause/region/start_time are inherited
-- from the event; a one-off "tennis shoe" outage still gets its own one-row
-- event. No status column - see outage_status_log / outage_current_status.
CREATE TABLE outages (
    outage_id          varchar(36) PRIMARY KEY,
    event_id           varchar(36) NOT NULL REFERENCES events(event_id),
    asset_id           varchar(36) REFERENCES grid_assets(asset_id),
    impact_count       integer,
    impact_magnitude   double precision
);

-- Status ledger for one outage. Renamed from outage_events - it always
-- tracked outage restoration status, never event status, so its FK stays
-- on outages, not events.
CREATE TABLE outage_status_log (
    log_id       bigserial PRIMARY KEY,
    outage_id    varchar(36) NOT NULL REFERENCES outages(outage_id) ON DELETE CASCADE,
    event_type   varchar(30) NOT NULL
                 CHECK (event_type IN ('REPORTED','CONFIRMED','CREW_ASSIGNED','ETR_UPDATED','RESTORED','CLOSED')),
    from_status  varchar(20),
    to_status    varchar(20),
    etr          timestamp without time zone,
    note         text,
    event_time   timestamp without time zone NOT NULL DEFAULT now()
);

-- Current status is derived, not stored twice - the latest ledger row per outage.
CREATE VIEW outage_current_status AS
SELECT DISTINCT ON (outage_id) outage_id, to_status AS status, event_time AS status_since
FROM outage_status_log
ORDER BY outage_id, event_time DESC;

-- ---------------------------------------------------------------------------
-- STORM THREAT TRACKING — which assets a given event (e.g. a simulated storm)
-- currently threatens. Many-to-many, time-varying: the legitimate case for a
-- link table, unlike outages<->events (plain one-to-many via outages.event_id).
--
-- DORMANT: nothing writes to this table today (no ORM model, no service, no
-- agent) - the write path (StormThreatService) was never built. Kept
-- intentionally, not dead weight; see
-- docs/enhancements-future/storm-threat-tracking.md.
-- ---------------------------------------------------------------------------
CREATE TABLE event_asset_threat (
    threat_id    bigserial PRIMARY KEY,
    event_id     varchar(36) NOT NULL REFERENCES events(event_id),
    asset_id     varchar(36) NOT NULL REFERENCES grid_assets(asset_id),
    detected_at  timestamp without time zone NOT NULL DEFAULT now(),
    cleared_at   timestamp without time zone
);

-- Current threat set is derived, not a flag - NULL cleared_at = still threatened.
CREATE VIEW event_current_threats AS
SELECT event_id, asset_id, detected_at
FROM event_asset_threat
WHERE cleared_at IS NULL;

-- --------------------------------------------------------------- work_orders
CREATE TABLE work_orders (
    work_order_id    varchar(36) PRIMARY KEY,
    outage_id        varchar(36) REFERENCES outages(outage_id),
    asset_id         varchar(36) REFERENCES grid_assets(asset_id),
    crew_id          varchar(36) REFERENCES crews(crew_id),
    wo_type          varchar(30),
    priority         varchar(10) CHECK (priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    status           varchar(20) CHECK (status IN ('OPEN','ASSIGNED','IN_PROGRESS','COMPLETED','CANCELLED')),
    created_date     timestamp without time zone,
    scheduled_date   timestamp without time zone,
    completed_date   timestamp without time zone,
    estimated_hours  double precision,
    actual_hours     double precision
);

-- ===========================================================================
-- CUSTOMER DOMAIN removed - see docs/business-rules and the DDL header
-- comment above. customers/outage_reports intentionally do not exist here.
-- ===========================================================================

-- ------------------------------------------------------------------- indexes
CREATE INDEX ix_outages_asset                ON outages (asset_id);
CREATE INDEX ix_outages_event                ON outages (event_id);
CREATE INDEX ix_outage_status_log_outage     ON outage_status_log (outage_id, event_time);
CREATE INDEX ix_event_asset_threat_event     ON event_asset_threat (event_id);
CREATE INDEX ix_event_asset_threat_current   ON event_asset_threat (event_id, asset_id) WHERE cleared_at IS NULL;
CREATE INDEX ix_work_orders_crew             ON work_orders (crew_id);
CREATE INDEX ix_work_orders_status           ON work_orders (status);
CREATE INDEX ix_service_locations_xfmr       ON service_locations (transformer_id);
CREATE INDEX ix_meters_location              ON meters (location_id);

-- ============================================================================
-- SCHEMA DESCRIPTIONS — read by the NL2SQL tool (get_schema_info reads
-- pg_description directly), so these are not just for humans; they shape
-- what the SQL-writing model sees. Prioritized on tables/columns that have
-- caused real confusion, not exhaustive on every column.
-- ============================================================================

COMMENT ON TABLE grid_assets IS 'Physical grid equipment: substations, feeders, transformers. Has two separate status-like fields - see column comments.';
COMMENT ON COLUMN grid_assets.asset_condition IS 'Lifecycle state - is the asset commissioned and in service? INSTALLED/MAINTENANCE/RETIRED. Unrelated to whether it currently has an outage.';
COMMENT ON COLUMN grid_assets.status IS 'Real-time outage state, kept in sync automatically on every outage create/transition. REPORTED/CONFIRMED/CREW_ASSIGNED/RESTORED/NORMAL - NORMAL means no open outage.';

COMMENT ON TABLE service_locations IS 'A customer premise (residential or commercial), served by one transformer.';

COMMENT ON TABLE meters IS 'A physical meter installed at a service location.';
COMMENT ON COLUMN meters.status IS 'Meter device status: ACTIVE/INACTIVE/FAULTED. Not related to grid_assets.status.';

COMMENT ON TABLE crews IS 'Field crews available for outage response and work orders.';
COMMENT ON COLUMN crews.status IS 'Crew availability: AVAILABLE/DISPATCHED/OFF_DUTY. Not related to grid_assets.status or outage status.';

COMMENT ON TABLE event_types IS 'Lookup of event categories (storm, vehicle, fire, equipment failure, etc.). Extensible vocabulary, not an enum.';

COMMENT ON TABLE events IS 'The primitive: any occurrence, tiny or huge, is one row here. Does not know about outages. Has no status column - only severity.';
COMMENT ON COLUMN events.severity IS 'LOW/MEDIUM/HIGH - an instance fact judged per event, never derived from event_type_code (a STORM can be LOW, a VEHICLE incident can be HIGH).';

COMMENT ON TABLE outages IS 'Links one event to one impacted asset. Thin: no status column here - status is derived from outage_status_log, never duplicated. asset_id nullable if the asset is later removed.';
COMMENT ON COLUMN outages.impact_count IS 'How many customers/points affected.';
COMMENT ON COLUMN outages.impact_magnitude IS 'Volume/load impact (e.g. MW). Not a dollar or customer-count figure.';

COMMENT ON TABLE outage_status_log IS 'Append-only history: one row per status transition for one outage. This is the source of truth for outage status - never a column on outages.';
COMMENT ON COLUMN outage_status_log.to_status IS 'REPORTED/CONFIRMED/CREW_ASSIGNED/RESTORED/CLOSED. The latest row per outage_id is the outage''s current status (see outage_current_status view).';

COMMENT ON TABLE event_asset_threat IS 'Which assets a storm/event currently threatens (proximity warning). Separate concept from outages - an asset can be threatened with no outage yet, or have an outage with no active threat.';

COMMENT ON TABLE work_orders IS 'Crew dispatch record tied to an outage and asset.';
COMMENT ON COLUMN work_orders.status IS 'Work order progress: OPEN/ASSIGNED/IN_PROGRESS/COMPLETED/CANCELLED. Unrelated to grid_assets.status or outage status.';
-- ============================================================================
