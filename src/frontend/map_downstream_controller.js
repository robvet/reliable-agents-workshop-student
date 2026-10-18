class MapDownstreamController {
    constructor({ map, assets, markers, iconForAsset, statusLabel, apiBaseUrl, statusElement, setLoading }) {
        this.map = map;
        this.assets = assets;
        this.markers = markers;
        this.iconForAsset = iconForAsset;
        this.statusLabel = statusLabel;
        this.apiBaseUrl = apiBaseUrl;
        this.statusElement = statusElement;
        this.setLoading = setLoading;
        this.overlay = L.layerGroup().addTo(map);
        this.overlayMarkers = [];
        this.root = null;
        this.descendants = [];
        this.outageMode = false;
        this.requestVersion = 0;
        this.pendingRequest = null;
        this.loading = false;
        for (const asset of assets) {
            const marker = markers.get(asset.id);
            if (marker) marker.bindPopup(() => this.createPopup([asset]), { maxHeight: 300 });
        }
    }

    setOutageMode(enabled) {
        this.outageMode = enabled;
        this.refreshStyles();
    }

    assumesOutage() {
        return Boolean(this.outageMode && this.root && this.root.in_outage);
    }

    isDownstream(asset) {
        return this.descendants.some(child => child.id === asset.id && child.asset_type === asset.asset_type);
    }

    createPopup(assets) {
        const content = document.createElement("div");
        const heading = document.createElement("strong");
        heading.textContent = assets.length > 1 ? `${assets.length} meters at this location` : assets[0].name;
        content.appendChild(heading);
        for (const asset of assets) {
            const details = document.createElement("p");
            details.className = "map-asset-details";
            const assumed = this.assumesOutage() && this.isDownstream(asset);
            details.textContent = [
                `ID: ${asset.id}`,
                `Type: ${asset.asset_type}`,
                `Recorded status: ${this.statusLabel(asset.status)}`,
                asset.crew_name ? `Crew: ${asset.crew_name}` : "",
                assumed ? `Assumed affected by upstream outage at ${this.root.name}.` : "",
            ].filter(Boolean).join("\n");
            content.appendChild(details);
        }
        if (assets.length === 1 && assets[0].asset_type !== "METER") {
            const asset = assets[0];
            const toggle = document.createElement("a");
            toggle.href = "#";
            toggle.className = "map-downstream-link";
            toggle.textContent = this.root && this.root.id === asset.id
                ? "Hide Downstream Assets" : "Show Downstream Assets";
            toggle.addEventListener("click", event => {
                event.preventDefault();
                event.stopPropagation();
                this.toggle(asset);
            });
            content.appendChild(toggle);
        }
        return content;
    }

    collapse() {
        this.requestVersion++;
        if (this.pendingRequest) this.pendingRequest.abort();
        this.pendingRequest = null;
        this.root = null;
        this.descendants = [];
        this.loading = false;
        this.overlay.clearLayers();
        this.overlayMarkers = [];
        this.statusElement.textContent = "";
        this.statusElement.classList.remove("is-error");
        this.refreshStyles();
    }

    async toggle(asset) {
        const wasExpanded = this.root && this.root.id === asset.id;
        let version = ++this.requestVersion;
        if (this.pendingRequest) this.pendingRequest.abort();
        let timer;
        this.setLoading(true, `${wasExpanded ? "Hiding" : "Loading"} downstream assets for ${asset.name}...`);
        try {
            // Yield through a paint before synchronous marker removal/restyling.
            await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
            if (version !== this.requestVersion) return;
            this.collapse();
            version = this.requestVersion;
            if (wasExpanded) return;

            this.root = asset;
            this.loading = true;
            const controller = new AbortController();
            this.pendingRequest = controller;
            timer = setTimeout(() => controller.abort(), 15000);
            this.refreshStyles();
            const response = await fetch(
                `${this.apiBaseUrl}/map/assets/${encodeURIComponent(asset.id)}/descendants`,
                { signal: controller.signal, cache: "no-store" }
            );
            if (!response.ok) throw new Error(`Downstream lookup returned HTTP ${response.status}`);
            const result = await response.json();
            if (version !== this.requestVersion) return;
            if (!result.source || result.source.id !== asset.id || !Array.isArray(result.assets)) {
                throw new Error("Downstream lookup returned an invalid response");
            }
            this.root = result.source;
            this.descendants = result.assets;
            const baseById = new Map(this.assets.map(base => [base.id, base]));
            for (const current of [result.source, ...result.assets]) {
                const base = current.asset_type !== "METER" && baseById.get(current.id);
                if (base) {
                    base.status = current.status;
                    base.in_outage = current.in_outage;
                }
            }
            this.loading = false;
            this.addOverlayMarkers();
            this.refreshStyles();
        } catch (error) {
            if (version !== this.requestVersion) return;
            this.collapse();
            const reason = error.name === "AbortError" ? "request timed out" : error.message;
            this.statusElement.textContent = `Could not load downstream assets for ${asset.name}: ${reason}. Try again.`;
            this.statusElement.classList.add("is-error");
            console.error("Map downstream lookup failed", error);
        } finally {
            clearTimeout(timer);
            if (version === this.requestVersion) this.pendingRequest = null;
            this.setLoading(false);
        }
    }

    hasCoordinates(asset) {
        return typeof asset.lat === "number" && Number.isFinite(asset.lat)
            && typeof asset.lng === "number" && Number.isFinite(asset.lng)
            && Math.abs(asset.lat) <= 90 && Math.abs(asset.lng) <= 180;
    }

    addOverlayMarkers() {
        const groups = new Map();
        for (const asset of this.descendants) {
            if (!this.hasCoordinates(asset) || (asset.asset_type !== "METER" && this.markers.has(asset.id))) continue;
            // Co-located meters share one marker, but every meter is listed in its popup.
            const key = asset.asset_type === "METER" ? `meters:${asset.lat},${asset.lng}` : `grid:${asset.id}`;
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(asset);
        }
        for (const assets of groups.values()) {
            const asset = assets[0];
            const marker = L.marker([asset.lat, asset.lng], { icon: this.iconForAsset(asset, false) });
            marker.bindPopup(() => this.createPopup(assets), { maxHeight: 300 });
            const label = assets.length > 1 ? `${assets.length} meters` : asset.name;
            const tooltip = document.createElement("span");
            tooltip.textContent = label;
            marker.bindTooltip(tooltip, { direction: "top", offset: [0, -12], opacity: 0.95 });
            marker.addTo(this.overlay);
            this.overlayMarkers.push({ marker, assets });
        }
    }

    refreshStyles() {
        const ids = new Set(this.descendants.filter(asset => asset.asset_type !== "METER").map(asset => asset.id));
        const assumedOutage = this.assumesOutage();
        for (const asset of this.assets) {
            const marker = this.markers.get(asset.id);
            if (!marker) continue;
            const selected = this.root && this.root.id === asset.id;
            const downstream = ids.has(asset.id);
            const red = this.outageMode && (asset.in_outage || (selected && this.root.in_outage) || (downstream && assumedOutage));
            marker.setIcon(this.iconForAsset(asset, Boolean(red)));
            marker.setOpacity(this.root ? (selected || downstream ? 1 : 0.25) : (this.outageMode && !asset.in_outage ? 0.25 : 1));
            marker.setPopupContent(() => this.createPopup([asset]));
        }
        for (const { marker, assets } of this.overlayMarkers) {
            marker.setIcon(this.iconForAsset(assets[0], Boolean(assumedOutage || (this.outageMode && assets[0].in_outage))));
            marker.setPopupContent(() => this.createPopup(assets));
        }
        if (!this.root) return;
        if (this.loading) {
            this.statusElement.textContent = `Loading downstream assets for ${this.root.name}...`;
            return;
        }
        const count = type => this.descendants.filter(asset => asset.asset_type === type).length;
        const missing = this.descendants.filter(asset => !this.hasCoordinates(asset)).length;
        this.statusElement.textContent = this.descendants.length
            ? `${this.root.name}: ${count("FEEDER")} feeders, ${count("TRANSFORMER")} transformers, ${count("METER")} meters.`
            : `No downstream assets found for ${this.root.name}.`;
        if (missing) this.statusElement.textContent += ` ${missing} assets cannot be plotted because coordinates are missing.`;
        if (assumedOutage && this.descendants.length) {
            this.statusElement.textContent += " Downstream assets are assumed affected; recorded statuses are unchanged.";
        }
    }
}
