class TestMapDownstreamController {
    static fixture(fetchResult) {
        const fs = require("node:fs");
        const path = require("node:path");
        const vm = require("node:vm");
        const element = () => ({
            textContent: "", children: [], listeners: {},
            classList: { add() {}, remove() {} },
            appendChild(child) { this.children.push(child); },
            addEventListener(name, handler) { this.listeners[name] = handler; },
        });
        const marker = () => ({
            bindPopup(content) { this.popup = content; return this; },
            setPopupContent(content) { this.popup = content; return this; },
            bindTooltip(content) { this.tooltip = content; return this; },
            setIcon(icon) { this.icon = icon; return this; },
            setOpacity(opacity) { this.opacity = opacity; return this; },
            addTo(layer) { layer.layers.push(this); return this; },
        });
        const source = { id: "S-1", name: "Substation", asset_type: "SUBSTATION", in_outage: true, status: "REPORTED", lat: 32, lng: -96 };
        const feeder = { id: "F-1", name: "Feeder", asset_type: "FEEDER", in_outage: false, status: "NORMAL", lat: 32.1, lng: -96 };
        const other = { id: "S-2", name: "Other", asset_type: "SUBSTATION", in_outage: false, status: "NORMAL", lat: 33, lng: -96 };
        const meter = { id: "M-1", name: "M-1", asset_type: "METER", status: "ACTIVE", lat: 32.2, lng: -96 };
        const result = { source, assets: [feeder, meter] };
        const requests = [];
        const errors = [];
        const loading = [];
        const Controller = vm.runInNewContext(
            fs.readFileSync(path.join(__dirname, "../src/frontend/map_downstream_controller.js"), "utf8") + "\nMapDownstreamController",
            {
                document: { createElement: element }, AbortController, setTimeout, clearTimeout,
                requestAnimationFrame: callback => callback(),
                console: { error: (...args) => errors.push(args) },
                L: {
                    layerGroup: () => ({ layers: [], addTo() { return this; }, clearLayers() { this.layers = []; } }),
                    marker,
                },
                fetch: async (...args) => {
                    requests.push(args);
                    return fetchResult ? fetchResult(...args) : { ok: true, json: async () => result };
                },
            }
        );
        const assets = [source, feeder, other];
        const markers = new Map(assets.map(asset => [asset.id, marker()]));
        const status = element();
        const controller = new Controller({
            map: {}, assets, markers, statusElement: status, apiBaseUrl: "",
            iconForAsset: (asset, red) => ({ id: asset.id, red }),
            statusLabel: status => status,
            setLoading: (visible, message) => loading.push({ visible, message }),
        });
        return { controller, source, feeder, other, meter, result, markers, status, requests, errors, loading };
    }

    static async waitForPaint() {
        await new Promise(resolve => setTimeout(resolve, 0));
    }

    static async outageToggle() {
        const assert = require("node:assert/strict");
        const f = this.fixture();
        f.controller.setOutageMode(true);
        assert.equal(f.markers.get("S-1").icon.red, true);
        await f.controller.toggle(f.source);
        assert.equal(f.markers.get("F-1").icon.red, true);
        assert.equal(f.controller.overlay.layers[0].icon.red, true);
        assert.equal(f.markers.get("S-2").opacity, 0.25);
        const popup = f.markers.get("F-1").popup();
        assert.match(popup.children[1].textContent, /Assumed affected by upstream outage at Substation/);
        await f.controller.toggle(f.source);
        assert.equal(f.controller.overlay.layers.length, 0);
        assert.equal(f.markers.get("S-1").icon.red, true);
        assert.equal(f.markers.get("F-1").icon.red, false);
        assert.equal(f.markers.get("F-1").opacity, 0.25);
        assert.equal(f.requests.length, 1);
        assert.equal(f.feeder.in_outage, false);
        assert.equal(f.feeder.status, "NORMAL");
    }

    static async filterChanges() {
        const assert = require("node:assert/strict");
        const f = this.fixture();
        await f.controller.toggle(f.source);
        assert.equal(f.controller.overlay.layers[0].icon.red, false);
        f.controller.setOutageMode(true);
        assert.equal(f.controller.overlay.layers[0].icon.red, true);
        f.controller.setOutageMode(false);
        assert.equal(f.controller.overlay.layers[0].icon.red, false);
        assert.doesNotMatch(f.status.textContent, /assumed affected/);
        f.controller.collapse();
        assert.equal(f.markers.get("S-1").opacity, 1);
        assert.equal(f.markers.get("S-1").icon.red, false);
    }

    static async healthyRoot() {
        const assert = require("node:assert/strict");
        const f = this.fixture();
        f.result.source = f.feeder;
        f.result.assets = [f.meter];
        f.controller.setOutageMode(true);
        await f.controller.toggle(f.feeder);
        assert.equal(f.controller.overlay.layers[0].icon.red, false);
        assert.doesNotMatch(f.status.textContent, /assumed affected/);
    }

    static async coordinateAndOverlapHandling() {
        const assert = require("node:assert/strict");
        const f = this.fixture();
        f.result.assets.push(
            { ...f.meter, id: "M-2" },
            { ...f.meter, id: "M-missing", lat: null }
        );
        await f.controller.toggle(f.source);
        assert.equal(f.controller.overlay.layers.length, 1);
        const popup = f.controller.overlay.layers[0].popup();
        assert.equal(popup.children[0].textContent, "2 meters at this location");
        assert.match(popup.children[1].textContent, /M-1/);
        assert.match(popup.children[2].textContent, /M-2/);
        assert.match(f.status.textContent, /3 meters/);
        assert.match(f.status.textContent, /1 assets cannot be plotted/);
        assert.equal(f.markers.size, 3);
    }

    static async staleResponses() {
        const assert = require("node:assert/strict");
        const pending = [];
        const f = this.fixture(() => new Promise(resolve => pending.push(resolve)));
        const first = f.controller.toggle(f.source);
        await this.waitForPaint();
        const second = f.controller.toggle(f.other);
        await this.waitForPaint();
        pending[0]({ ok: true, json: async () => f.result });
        await first;
        assert.equal(f.loading.reduce((count, item) => count + (item.visible ? 1 : -1), 0), 1);
        pending[1]({ ok: true, json: async () => ({ source: f.other, assets: [] }) });
        await second;
        assert.equal(f.loading.reduce((count, item) => count + (item.visible ? 1 : -1), 0), 0);
        assert.equal(f.controller.root.id, "S-2");
        assert.equal(f.controller.overlay.layers.length, 0);
        assert.match(f.status.textContent, /No downstream assets found for Other/);
        assert.equal(f.markers.get("S-1").popup().children.at(-1).textContent, "Show Downstream Assets");
    }

    static async cancelLoading() {
        const assert = require("node:assert/strict");
        let finish;
        const f = this.fixture(() => new Promise(resolve => { finish = resolve; }));
        const pending = f.controller.toggle(f.source);
        await this.waitForPaint();
        await f.controller.toggle(f.source);
        finish({ ok: true, json: async () => f.result });
        await pending;
        assert.equal(f.controller.root, null);
        assert.equal(f.controller.overlay.layers.length, 0);
        assert.equal(f.status.textContent, "");
        assert.equal(f.requests[0][1].signal.aborted, true);
        assert.equal(f.loading.reduce((count, item) => count + (item.visible ? 1 : -1), 0), 0);
    }

    static async explicitError() {
        const assert = require("node:assert/strict");
        const f = this.fixture(async () => ({ ok: false, status: 502 }));
        f.controller.setOutageMode(true);
        await f.controller.toggle(f.source);
        assert.match(f.status.textContent, /Could not load downstream assets.*HTTP 502/);
        assert.equal(f.controller.root, null);
        assert.equal(f.controller.overlay.layers.length, 0);
        assert.equal(f.markers.get("S-1").icon.red, true);
        assert.equal(f.errors.length, 1);
        assert.equal(f.loading.at(-1).visible, false);
    }

    static async loadingIndicator() {
        const assert = require("node:assert/strict");
        const f = this.fixture();
        const showing = f.controller.toggle(f.source);
        assert.equal(f.loading.at(-1).visible, true);
        assert.match(f.loading.at(-1).message, /Loading downstream assets/);
        assert.equal(f.requests.length, 0);
        await showing;
        assert.equal(f.loading.at(-1).visible, false);
        const hiding = f.controller.toggle(f.source);
        assert.equal(f.loading.at(-1).visible, true);
        assert.match(f.loading.at(-1).message, /Hiding downstream assets/);
        assert.equal(f.controller.overlay.layers.length, 1);
        await hiding;
        assert.equal(f.controller.overlay.layers.length, 0);
        assert.equal(f.loading.at(-1).visible, false);
    }

    static async supersededBeforePaint() {
        const assert = require("node:assert/strict");
        const f = this.fixture();
        f.result.source = f.other;
        f.result.assets = [];
        await Promise.all([f.controller.toggle(f.source), f.controller.toggle(f.other)]);
        assert.equal(f.requests.length, 1);
        assert.equal(f.controller.root.id, f.other.id);
        assert.equal(f.loading.reduce((count, item) => count + (item.visible ? 1 : -1), 0), 0);
    }

    static async refreshedRecordedOutage() {
        const assert = require("node:assert/strict");
        const f = this.fixture();
        f.source.in_outage = false;
        f.source.status = "NORMAL";
        f.result.source = { ...f.source, in_outage: true, status: "REPORTED" };
        f.controller.setOutageMode(true);
        await f.controller.toggle(f.source);
        f.controller.collapse();
        assert.equal(f.markers.get("S-1").icon.red, true);
        assert.equal(f.source.status, "REPORTED");
        assert.equal(f.feeder.status, "NORMAL");
    }

    static {
        const { test } = require("node:test");
        test("outage expansion is red; collapse preserves the parent's recorded outage", () => this.outageToggle());
        test("changing outage mode restyles the active overlay without refetching", () => this.filterChanges());
        test("a healthy root does not imply a downstream outage", () => this.healthyRoot());
        test("co-located meters are listed together and missing coordinates are reported", () => this.coordinateAndOverlapHandling());
        test("switching roots discards stale responses and keeps one active root", () => this.staleResponses());
        test("collapsing while loading cancels expansion", () => this.cancelLoading());
        test("lookup failure is visible and restores outage styling", () => this.explicitError());
        test("show and hide display loading before work and clear it afterward", () => this.loadingIndicator());
        test("a selection superseded before paint does not fetch or leave loading active", () => this.supersededBeforePaint());
        test("fresh recorded outage data persists after collapse without inferring child statuses", () => this.refreshedRecordedOutage());
    }
}
