/**
 * Engage 360 — Frontend Application
 *
 * Wires up the HTML controls to the FastAPI backend endpoints:
 *   GET  /prompt-library  — fetch available analysis types
 *   POST /analyze         — run analysis with model + prompt + optional file
 */

document.addEventListener("DOMContentLoaded", () => {

    // One conversation id per page load (per tab); resets on refresh. Sent with each
    // chat request so the backend can group turns. See docs/Intent-Classification-Routing.
    const CONVERSATION_ID = crypto.randomUUID();

    // ===================================================================
    // DOM References
    // ===================================================================
    const btnAddFile       = document.getElementById("btn-add-file");
    const fileDropZone     = document.getElementById("file-drop-zone");
    const fileInput        = document.getElementById("file-input");
    const fileChips        = document.getElementById("file-chips");
    const fileLimitNote    = document.getElementById("file-limit-note");
    const promptTextarea   = document.getElementById("prompt-textarea");
    const btnAnalyze       = document.getElementById("btn-analyze");
    const analyzeConfirm   = document.getElementById("analyze-confirm");
    const analyzeConfirmDialog = document.getElementById("analyze-confirm-dialog");
    const analyzeConfirmTitle = document.getElementById("analyze-confirm-title");
    const analyzeConfirmMessage = document.getElementById("analyze-confirm-message");
    const btnAnalyzeConfirm = document.getElementById("btn-analyze-confirm");
    const btnAnalyzeCancel = document.getElementById("btn-analyze-cancel");
    const btnClear         = document.getElementById("btn-clear");
    const exportMenu       = document.getElementById("export-menu");
    const btnExportClipboard = document.getElementById("btn-export-clipboard");
    const btnExportFile    = document.getElementById("btn-export-file");
    const btnExportPrint   = document.getElementById("btn-export-print");
    const navAgenticLink   = document.getElementById("nav-agentic-link");
    const navArchitectureLink = document.getElementById("nav-architecture-link");
    const navDataModelLink = document.getElementById("nav-datamodel-link");
    const navBusinessCaseLink = document.getElementById("nav-businesscase-link");
    const navMapLink       = document.getElementById("nav-map-link");
    const navReasoningLink = document.getElementById("nav-reasoning-link");
    const navGeneratorLink = document.getElementById("nav-generator-link");
    const navOutagesLink   = document.getElementById("nav-outages-link");
    const navHomeLink      = document.getElementById("nav-home-link");
    const homePanel        = document.getElementById("home-panel");
    const agenticPanel     = document.getElementById("agentic-panel");
    const mapPanel         = document.getElementById("map-panel");
    const generatorPanel   = document.getElementById("generator-panel");
    const outagesPanel     = document.getElementById("outages-panel");
    const mapContainer     = document.getElementById("asset-map");
    const mapWeatherChip   = document.getElementById("map-weather-chip");
    const mapOutageToggle  = document.getElementById("map-outage-toggle");
    const genNumLocations  = document.getElementById("gen-num-locations");
    const genCrewCount     = document.getElementById("gen-crew-count");
    const generatorForecast = document.getElementById("generator-forecast");
    const generatorStatus  = document.getElementById("generator-status");
    const btnGeneratorGenerate = document.getElementById("btn-generator-generate");
    const btnGeneratorClear = document.getElementById("btn-generator-clear");
    const outageAssetSelect = document.getElementById("outage-asset");
    const outageAssetAskLink = document.getElementById("outage-asset-ask-link");
    const outageEventSelect = document.getElementById("outage-event");
    const outageCrewField  = document.getElementById("outage-crew-field");
    const outageCrewSelect = document.getElementById("outage-crew");
    const outageNoteTextarea = document.getElementById("outage-note");
    const btnOutageCreate  = document.getElementById("btn-outage-create");
    const btnOutageRefresh = document.getElementById("btn-outage-refresh");
    const outageStatus     = document.getElementById("outage-status");
    const outageList       = document.getElementById("outage-list");
    const pageLoadingOverlay = document.getElementById("page-loading-overlay");
    const pageLoadingMessage = document.getElementById("page-loading-message");
    const suggestionsList  = document.getElementById("suggestions-list");
    const resultsArea      = document.getElementById("results-area");
    const resultsPlaceholder = document.getElementById("results-placeholder");
    const outputArtifacts  = document.getElementById("output-artifacts");
    const resultsContent   = document.getElementById("results-content");
    const assetResults     = document.getElementById("asset-results");
    const resultsMeta      = document.getElementById("results-meta");
    const instrumentation      = document.getElementById("instrumentation");
    const instrumentationSteps = document.getElementById("instrumentation-steps");
    let executionTraceUserHidden = false;
    const loading          = document.getElementById("loading");
    const loadingLabel     = document.getElementById("loading-label");
    const elapsedTimer     = document.getElementById("elapsed-timer");
    let   timerInterval    = null;
    let   timerSeconds     = 0;
    let   lastRawMarkdown  = "";
    let   conversationId   = CONVERSATION_ID;
    // Same-origin: nginx serves this static site AND reverse-proxies the API paths
    // (/health, /chat/stream, /map/assets, /prompt-library, /generator/*) to the
    // backend Container App. Empty base => relative URLs => no CORS.
    //
    // Local-vs-server is decided by the BROWSER'S address bar host, not the port and
    // not where the server runs. `location.hostname` is whatever the user typed to
    // reach this page: on a real deployment (Container App, AKS ingress, App Service)
    // that's the public domain, never "localhost" — the container's internal
    // networking is invisible to the browser. Only a browser actually pointed at
    // localhost/127.0.0.1 (local dev, or a port-forward tunnel) reads as local, so we
    // point at the local backend on :8010 there and use same-origin everywhere else.
    const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
    const API_BASE_URL = isLocalHost ? "http://localhost:8010" : "";
    // Backend startup is dependency-heavy (MCP server on :8000, Azure Entra auth) and
    // `uvicorn --reload` cycles it on every code change, so readiness can take a while.
    // Retry the ramp below, then keep retrying on a steady interval so the prompts always
    // self-heal once the backend is up — never permanently give up.
    const PROMPT_RETRY_DELAYS_SECONDS = [2, 4, 8, 12, 16, 20, 25];
    const PROMPT_RETRY_STEADY_SECONDS = 15;
    // Declared up here because ensureAssetMap() runs before the bottom of this file is
    // reached. `const` is not hoisted, so leaving these next to loadMapAssets() threw
    // "Cannot access 'MAP_ASSET_TIMEOUT_MS' before initialization" and killed the map.
    const MAP_ASSET_TIMEOUT_MS = 6000;
    const MAP_ASSET_RETRY_MS = 2000;
    // Cap the /map/assets retries. Each attempt opens a fresh cold DB connection (no
    // pool), so an unbounded loop against a failing endpoint pins the server's
    // connection count. ~60s of retries covers backend/MCP cold start, then we stop.
    const MAX_MAP_ASSET_RETRIES = 30;
    // Built on demand, NEVER resolved once at parse time. Leaflet comes from a CDN, so
    // `L` can still be undefined while this file is being parsed. The old code captured
    // that moment in a const: if Leaflet was even slightly late, this was null for the
    // life of the page and the map silently refused to do anything until a reload.
    // That is the intermittent "it never even called the backend" bug.
    function getTexasBounds() {
        return (typeof L !== "undefined")
            ? L.latLngBounds([25.8, -106.8], [36.7, -93.5])
            : null;
    }
    let assetMap = null;
    let weatherLayer = null;
    let mapRadarLayer = null;
    // Draggable simulated-storm handle (only present while simulatedStormActive).
    // stormBaseRing/stormBaseAlert are the untranslated polygon + alert data from the
    // last fetch; drag deltas are applied on top of them so repeated drags don't drift.
    let stormPolygonLayer = null;
    let stormDragMarker = null;
    let stormBaseRing = null;
    let stormBaseAlert = null;
    let stormDragOrigin = null;
    // Assets are tracked separately from the map itself. The map can exist (tiles,
    // weather) while the asset load has failed, and we want the next view switch to
    // retry JUST the assets instead of concluding "map already built, nothing to do".
    let mapAssetsLoaded = false;
    // Same idea as mapAssetsLoaded: loaded once on first nav to Outages, then left
    // alone. "Refresh List" and any write action (create/transition) still reload
    // explicitly, this flag only stops the *view switch itself* from re-fetching.
    let outagesLoaded = false;
    // Last successful fetch, kept so a render retry does not re-hit the backend.
    let mapAssets = [];
    // Markers are added to the map without being retained anywhere, so the outage
    // filter needs its own lookup to restyle a marker after the fact without
    // rebuilding the whole map.
    let markersByAssetId = new Map();
    let showOutagesOnly = false;
    // Frontend-only: no backend state is changed. Toggling just adds/removes
    // ?demo=true on the /map/weather fetch. Resets to false on page reload.
    let simulatedStormActive = false;

    if (mapOutageToggle) {
        mapOutageToggle.addEventListener("click", () => {
            showOutagesOnly = !showOutagesOnly;
            mapOutageToggle.textContent = showOutagesOnly ? "Show All" : "Show Outages";
            mapOutageToggle.classList.toggle("is-active", showOutagesOnly);
            applyOutageDimming();
        });
    }

    const mapSimulateStormToggle = document.getElementById("map-simulate-storm-toggle");
    if (mapSimulateStormToggle) {
        mapSimulateStormToggle.addEventListener("click", () => {
            simulatedStormActive = !simulatedStormActive;
            mapSimulateStormToggle.textContent = simulatedStormActive ? "Stop Simulated Storm" : "Simulate Storm";
            mapSimulateStormToggle.classList.toggle("is-active", simulatedStormActive);
            addMapWeatherOverlay().catch((err) =>
                logMapDiag("fail", "Weather: overlay refresh failed", String(err && err.message ? err.message : err))
            );
        });
    }

    // Purely client-side: mapAssets and markersByAssetId are already populated from
    // the last load, so toggling never re-fetches.
    //
    // ON:  outage assets -> red icon, full opacity. Healthy assets -> normal icon, dimmed.
    // OFF: every asset -> normal icon, full opacity (original render state).
    function applyOutageDimming() {
        for (const asset of mapAssets) {
            const marker = markersByAssetId.get(asset.id);
            if (!marker) continue;
            const isOutage = showOutagesOnly && asset.in_outage;
            marker.setIcon(iconForMapAsset(asset, isOutage));
            marker.setOpacity(showOutagesOnly && !asset.in_outage ? 0.25 : 1);
        }
    }

    if (navAgenticLink) {
        navAgenticLink.addEventListener("click", (event) => {
            event.preventDefault();
            showAgenticView();
        });
    }
    if (navHomeLink) {
        navHomeLink.addEventListener("click", (event) => {
            event.preventDefault();
            showHomeView();
        });
    }
    if (navArchitectureLink) {
        navArchitectureLink.addEventListener("click", (event) => {
            event.preventDefault();
            openDocumentPopup(
                navArchitectureLink.href,
                "reliable-agents-architecture"
            );
        });
    }
    if (navDataModelLink) {
        navDataModelLink.addEventListener("click", (event) => {
            event.preventDefault();
            openDocumentPopup(
                navDataModelLink.href,
                "reliable-agents-datamodel"
            );
        });
    }
    if (navBusinessCaseLink) {
        navBusinessCaseLink.addEventListener("click", (event) => {
            event.preventDefault();
            openDocumentPopup(
                navBusinessCaseLink.href,
                "reliable-agents-businesscase"
            );
        });
    }
    // Last line of defence. Anything that rejects without a handler lands here and
    // gets a row in the Execution Trace, so a failure can never again be invisible
    // just because someone forgot a try/catch or wrote `void somethingAsync()`.
    window.addEventListener("unhandledrejection", (event) => {
        const reason = event && event.reason;
        logMapDiag("error", "Unhandled error", String((reason && reason.message) || reason));
    });

    if (navMapLink) {
        navMapLink.addEventListener("click", async (event) => {
            event.preventDefault();
            await showMapView();
        });
    }
    if (navGeneratorLink) {
        navGeneratorLink.addEventListener("click", (event) => {
            event.preventDefault();
            showGeneratorView();
        });
    }
    if (navOutagesLink) {
        navOutagesLink.addEventListener("click", (event) => {
            event.preventDefault();
            showOutagesView();
        });
    }
    // Manual toggle of the Execution Trace. Once hidden here, streamed rows must not
    // force it back open until the user shows it again.
    if (navReasoningLink) {
        navReasoningLink.addEventListener("click", (event) => {
            event.preventDefault();
            const willHide = !instrumentation.classList.contains("hidden");
            executionTraceUserHidden = willHide;
            instrumentation.classList.toggle("hidden", willHide);
            navReasoningLink.classList.toggle("active", !willHide);
        });
    }
    showHomeView();


    function confirmDialog({ title, message = "", confirmLabel = "Confirm", cancelLabel = "Cancel", variant = "default" } = {}) {
        return new Promise((resolve) => {
            analyzeConfirmTitle.textContent = title;
            btnAnalyzeConfirm.textContent = confirmLabel;
            btnAnalyzeCancel.textContent = cancelLabel;
            if (message) {
                analyzeConfirmMessage.textContent = message;
                analyzeConfirmMessage.classList.remove("hidden");
            } else {
                analyzeConfirmMessage.textContent = "";
                analyzeConfirmMessage.classList.add("hidden");
            }
            analyzeConfirmDialog.classList.toggle("confirm-dialog-caution", variant === "caution");

            const close = (confirmed) => {
                analyzeConfirm.classList.add("hidden");
                btnAnalyzeConfirm.removeEventListener("click", onConfirm);
                btnAnalyzeCancel.removeEventListener("click", onCancel);
                analyzeConfirm.removeEventListener("click", onOverlayClick);
                document.removeEventListener("keydown", onKeyDown);
                resolve(confirmed);
            };

            const onConfirm = () => close(true);
            const onCancel = () => close(false);
            const onOverlayClick = (event) => {
                if (event.target === analyzeConfirm) {
                    close(false);
                }
            };
            const onKeyDown = (event) => {
                if (event.key === "Escape") {
                    close(false);
                }
            };

            btnAnalyzeConfirm.addEventListener("click", onConfirm);
            btnAnalyzeCancel.addEventListener("click", onCancel);
            analyzeConfirm.addEventListener("click", onOverlayClick);
            document.addEventListener("keydown", onKeyDown);
            analyzeConfirm.classList.remove("hidden");
            btnAnalyzeConfirm.focus();
        });
    }


    // ===================================================================
    // 1. Load Prompt Library — populate suggestion chips
    // ===================================================================
    let promptPollCount = 0;
    loadPromptLibrary();

    async function loadPromptLibrary() {
        promptPollCount++;
        console.warn(`[POLL #${promptPollCount} @ ${new Date().toLocaleTimeString()}] fetching /prompt-library ...`);

        // The backend accepts connections before it can answer, so a bare fetch can
        // hang indefinitely during startup - never resolving, never rejecting, and
        // never arming the retry. Bound each attempt so a stalled request fails fast
        // and the poll loop keeps running.
        const controller = new AbortController();
        const timeoutId  = setTimeout(() => controller.abort(), 3000);

        try {
            const res = await fetch(`${API_BASE_URL}/prompt-library`, { signal: controller.signal });
            clearTimeout(timeoutId);
            if (!res.ok) throw new Error(`Failed to load prompt library: ${res.status}`);

            const prompts = await res.json();
            suggestionsList.innerHTML = "";

            const outagePrompts = prompts?.entities?.outages;
            if (!outagePrompts || typeof outagePrompts !== "object") {
                throw new Error("Prompt library missing entities.outages");
            }
            const entities = prompts?.entities || {};
            // Suggestion card data lives entirely in suggestive-prompts.yaml now.
            // fallbackEntries stays empty per card - just a safe no-op if the
            // backend ever omits an entity key, not a second source of content.
            const cardSpecs = [
                { key: "outages", title: "Outages", icon: "\uD83D\uDCA1", className: "suggestion-card--outages", entityKeys: ["outages"] },
                { key: "events", title: "Events", icon: "\u26A1", className: "suggestion-card--events", entityKeys: ["events"] },
                { key: "assets", title: "Assets", icon: "\uD83D\uDD0C", className: "suggestion-card--assets", entityKeys: ["assets"] },
                { key: "crew", title: "Crews", icon: "\uD83D\uDC77", className: "suggestion-card--crew", entityKeys: ["crew"] },
            ];

            // Combines prompts from one or more suggestive-prompts.yaml entity keys
            // into a single flat entry list (label + prompt), in yaml key order.
            function collectEntries(entityKeys) {
                const entries = [];
                for (const key of entityKeys) {
                    const entityPrompts = entities?.[key];
                    if (!entityPrompts || typeof entityPrompts !== "object") continue;
                    for (const entry of Object.values(entityPrompts)) {
                        if (!entry || typeof entry !== "object") continue;
                        if (!entry.label) continue;
                        entries.push({ label: entry.label, prompt: entry.prompt || "" });
                    }
                }
                return entries;
            }

            function buildPromptList(entries) {
                const promptList = document.createElement("div");
                promptList.className = "suggestion-card-list";
                for (const entry of entries) {
                    const link = document.createElement("a");
                    link.className = "suggestion-link";
                    link.href = "#";
                    link.textContent = entry.label;
                    // Every entry's prompt now comes from suggestive-prompts.yaml -
                    // no client-side text generation.
                    const effectivePrompt = entry.prompt;

                    link.setAttribute("data-tooltip", effectivePrompt);
                    link.setAttribute("aria-label", `${entry.label}: ${effectivePrompt}`);
                    link.draggable = true;
                    link.addEventListener("click", (event) => {
                        event.preventDefault();
                        selectSuggestion(link, effectivePrompt);
                    });
                    link.addEventListener("dragstart", (event) => {
                        event.dataTransfer.setData("text/plain", effectivePrompt);
                        event.dataTransfer.effectAllowed = "copy";
                    });
                    promptList.appendChild(link);
                }
                return promptList;
            }

            const board = document.createElement("div");
            board.className = "suggestion-board";

            for (const spec of cardSpecs) {
                const card = document.createElement("section");
                card.className = `suggestion-card ${spec.className}`;

                const title = document.createElement("h4");
                title.className = "suggestion-card-title";
                const icon = document.createElement("span");
                icon.className = `suggestion-card-icon suggestion-card-icon--${spec.key}`;
                icon.textContent = spec.icon;
                icon.setAttribute("aria-hidden", "true");
                title.appendChild(icon);
                title.appendChild(document.createTextNode(spec.title));
                card.appendChild(title);

                card.appendChild(buildPromptList(collectEntries(spec.entityKeys)));
                board.appendChild(card);
            }

            suggestionsList.appendChild(board);
        } catch (err) {
            clearTimeout(timeoutId);
            // Backend not ready yet (startup is dependency-heavy). Show a waiting state
            // and keep polling on a short, steady interval so the panel populates on its
            // own the moment the backend answers — no manual reload needed.
            suggestionsList.innerHTML = "";
            const waiting = document.createElement("span");
            waiting.className = "suggestions-wait";
            waiting.textContent = "Connecting to backend\u2026";
            suggestionsList.appendChild(waiting);

            console.warn("Prompt library not ready; retrying in 2s.", err);
            setTimeout(loadPromptLibrary, 2000);
        }
    }


    // ===================================================================
    // 2. File Upload — "+ Add File" opens the hidden file input
    // ===================================================================
    const selectedFiles = [];

    btnAddFile.addEventListener("click", (event) => {
        event.stopPropagation();
        fileInput.click();
    });

    fileDropZone.addEventListener("click", () => fileInput.click());

    fileDropZone.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            fileInput.click();
        }
    });

    for (const eventName of ["dragenter", "dragover"]) {
        fileDropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            fileDropZone.classList.add("drag-over");
        });
    }

    for (const eventName of ["dragleave", "drop"]) {
        fileDropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            fileDropZone.classList.remove("drag-over");
        });
    }

    fileDropZone.addEventListener("drop", (event) => {
        addSelectedFiles(event.dataTransfer.files);
    });

    fileInput.addEventListener("change", () => {
        addSelectedFiles(fileInput.files);
        fileInput.value = ""; // reset so same file can be re-added
    });

    function addSelectedFiles(files) {
        for (const file of files) {
            selectedFiles.push(file);
        }
        renderFileChips();
    }

    function renderFileChips() {
        fileChips.innerHTML = "";

        for (let i = 0; i < selectedFiles.length; i++) {
            const chip = document.createElement("span");
            chip.className = "file-chip";
            chip.textContent = selectedFiles[i].name;

            const removeBtn = document.createElement("button");
            removeBtn.className = "file-chip-remove";
            removeBtn.textContent = "×";
            const idx = i;
            removeBtn.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                selectedFiles.splice(idx, 1);
                renderFileChips();
            });
            chip.appendChild(removeBtn);
            fileChips.appendChild(chip);
        }

        if (selectedFiles.length === 0) {
            fileLimitNote.classList.add("hidden");
        } else if (selectedFiles.length === 1) {
            fileLimitNote.textContent = "1 file will be analyzed";
            fileLimitNote.classList.remove("hidden");
        } else {
            fileLimitNote.textContent = `${selectedFiles.length} files will be combined and analyzed as one transcript`;
            fileLimitNote.classList.remove("hidden");
        }
    }


    // ===================================================================
    // 3. Suggestion Chip Selection
    // ===================================================================
    function selectSuggestion(chipElement, displayName) {
        // Deselect any previously selected chip
        const prev = suggestionsList.querySelector(".suggestion-link.selected");
        if (prev) prev.classList.remove("selected");

        // Mark this chip as selected
        chipElement.classList.add("selected");

        // Populate textarea with the selected prompt text
        promptTextarea.value = displayName;
    }


    promptTextarea.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            btnAnalyze.click();
        }
    });

    // Accept a suggestion chip dragged onto the prompt box.
    promptTextarea.addEventListener("dragover", (event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
    });
    promptTextarea.addEventListener("drop", (event) => {
        const assetName = event.dataTransfer.getData("application/x-reliable-agents-asset");
        const text = event.dataTransfer.getData("text/plain");
        if (assetName) {
            event.preventDefault();
            promptTextarea.value = `${promptTextarea.value.trimEnd()} ${assetName}`.trimStart();
        } else if (text) {
            event.preventDefault();
            promptTextarea.value = text;
        }
    });


    // ===================================================================
    // 5. Analyze — Run Analysis
    // ===================================================================
    btnAnalyze.addEventListener("click", async () => {
        // Collect inputs
        const modelRadio = document.querySelector('input[name="model"]:checked');
        const modelName  = modelRadio ? modelRadio.value : "";
        const userPrompt = promptTextarea.value.trim();

        // Validate inputs
        if (!modelName) {
            showError("Please select a model.");
            return;
        }
        if (!userPrompt) {
            showError("Please enter text to analyze.");
            return;
        }

        const confirmed = await confirmDialog({
            title: "Analyze Conversation?",
            confirmLabel: "Analyze",
        });
        if (!confirmed) {
            return;
        }

        // Show loading, reset previous results + instrumentation
        showLoading(true);
        hideResults();
        // Collapse the results area entirely while the run is in flight - the
        // answer gets injected here, between the prompt and the live pipeline.
        resultsPlaceholder.classList.add("hidden");
        clearInstrumentation();

        try {
            // Reliable Agents backend: POST /chat/stream — NDJSON stream of pipeline events
            // (intent -> step per agent -> final). Steps render live in the
            // instrumentation panel; the final answer renders in the results panel.
            await streamChat(userPrompt);
        } catch (err) {
            // Name the failure instead of swallowing it - the instrumentation panel
            // is the diagnostic surface, so the real exception belongs there too.
            addInstrumentationRow("error", "Request failed", String(err && err.message ? err.message : err));
            showError(err.message);
        } finally {
            showLoading(false);
        }
    });


    // ===================================================================
    // 6. Display Results
    // ===================================================================
    function displayResults(data) {
        lastRawMarkdown = data.content || "";

        // Content — the model's answer
        resultsContent.innerHTML = "";
        if (data.errorDetail) {
            const apology = document.createElement("div");
            apology.className = "result-error";
            apology.textContent = data.content || "Please accept our apologies as our system is currently encountering a technical issue.";
            resultsContent.appendChild(apology);

            const technicalError = document.createElement("div");
            technicalError.className = "result-error-technical";
            technicalError.textContent = `Technical Details: ${data.errorDetail}`;
            resultsContent.appendChild(technicalError);
        } else if (data.content) {
            const contentBlock = document.createElement("div");
            contentBlock.className = "result-block final-response-block";

            const contentBody = document.createElement("div");
            contentBody.className = "result-text final-response-text";
            contentBody.innerHTML = renderMarkdown(data.content);
            const detailBlocks = wrapDetailSections(contentBody);

            // Show a single "Expand all / Collapse all" toggle when the report
            // contains one or more collapsible Detail blocks.
            if (detailBlocks.length > 0) {
                const toggle = document.createElement("button");
                toggle.type = "button";
                toggle.className = "detail-toggle-all";
                toggle.textContent = "Expand all details";

                toggle.addEventListener("click", () => {
                    const shouldOpen = detailBlocks.some((d) => !d.open);
                    detailBlocks.forEach((d) => { d.open = shouldOpen; });
                    toggle.textContent = shouldOpen ? "Collapse all details" : "Expand all details";
                });

                contentBlock.appendChild(toggle);
            }

            contentBlock.appendChild(contentBody);
            renderAssetResults(data.assets, data.content, contentBlock, contentBody);

            resultsContent.appendChild(contentBlock);
        }

        // Token Usage — show as a compact metadata line
        resultsMeta.innerHTML = "";
        if (data.token_usage) {
            const usage = data.token_usage;
            const metaLine = document.createElement("div");
            metaLine.className = "meta-line";
            metaLine.textContent = `Tokens — input: ${usage.input_tokens ?? "?"}, output: ${usage.output_tokens ?? "?"}, total: ${usage.total_tokens ?? "?"}`;
            resultsMeta.appendChild(metaLine);
        }

        // Model info from response_meta
        if (data.response_meta) {
            const modelId = data.response_meta.model_name || data.response_meta.model || "";
            if (modelId) {
                const modelLine = document.createElement("div");
                modelLine.className = "meta-line";
                modelLine.textContent = `Model: ${modelId}`;
                resultsMeta.appendChild(modelLine);
            }
        }

        // Show results, hide placeholder
        resultsPlaceholder.classList.add("hidden");
        resultsContent.classList.remove("hidden");
        if (resultsMeta.children.length > 0) {
            resultsMeta.classList.remove("hidden");
        }
    }

    function renderAssetResults(assets, content, contentBlock, contentBody) {
        assetResults.innerHTML = "";
        assetResults.classList.add("hidden");
        if (!Array.isArray(assets) || assets.length < 2) {
            return;
        }

        // This card view only makes sense for typed grid-asset rows (substations,
        // feeders, transformers), which carry `asset_name`/`region`. Other queries
        // (e.g. meter/reading lookups) return rows from a completely different,
        // dynamically-generated SQL shape - rendering those here would print
        // "undefined" for the missing fields and clobber the narrator's full
        // answer with just its first line. Bail out and let the narrator's
        // markdown stand untouched.
        if (typeof assets[0]?.asset_name !== "string") {
            return;
        }

        const summary = content.split("\n").find((line) => line.trim());
        contentBody.innerHTML = renderMarkdown(summary || "");

        assets.forEach((asset, index) => {
            const row = document.createElement("div");
            row.className = "asset-result-row";

            const number = document.createElement("span");
            number.className = "asset-result-number";
            number.textContent = `${index + 1}.`;

            const fields = Object.entries(asset);

            // A row with only one field has nothing to expand into - there's no
            // headline/detail split to justify a "+" disclosure. Render it as a
            // flat "key: value" line instead of guessing at asset_name/region,
            // which don't exist on non-asset rows (e.g. a schema/status lookup).
            if (fields.length <= 1) {
                const [key, value] = fields[0] || ["", ""];
                const flat = document.createElement("span");
                flat.className = "asset-result-flat";
                flat.textContent = key ? `${key}: ${value}` : "";
                row.append(number, flat);
                assetResults.appendChild(row);
                return;
            }

            const details = document.createElement("details");
            details.className = "asset-result-details";

            const label = document.createElement("summary");
            const assetLink = document.createElement("a");
            assetLink.className = "asset-result-link";
            assetLink.href = "#prompt-textarea";
            assetLink.textContent = asset.asset_name;
            assetLink.draggable = true;
            assetLink.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                promptTextarea.value = asset.asset_name;
                promptTextarea.focus();
            });
            assetLink.addEventListener("dragstart", (event) => {
                event.dataTransfer.setData("application/x-reliable-agents-asset", asset.asset_name);
                event.dataTransfer.setData("text/plain", asset.asset_name);
                event.dataTransfer.effectAllowed = "copy";
            });
            label.append(assetLink, ` - ${asset.region}`);

            const body = document.createElement("pre");
            body.className = "asset-result-body";
            body.textContent = fields
                .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`)
                .join("\n");

            details.append(label, body);

            row.append(number, details);
            assetResults.appendChild(row);
        });

        contentBlock.appendChild(assetResults);
        assetResults.classList.remove("hidden");
    }


    // ===================================================================
    // 7. Clear — reset everything
    // ===================================================================
    btnClear.addEventListener("click", async () => {
        const confirmed = await confirmDialog({
            title: "Clear Conversation?",
            confirmLabel: "Clear",
        });
        if (!confirmed) {
            return;
        }
        resetConversationContext();
    });

    function resetConversationContext() {
        conversationId = window.crypto?.randomUUID ? window.crypto.randomUUID() : String(Date.now());
        promptTextarea.value = "";
        clearFiles();
        hideResults();
        clearInstrumentation();

        // Deselect suggestion chips
        const selected = suggestionsList.querySelector(".suggestion-link.selected");
        if (selected) selected.classList.remove("selected");
    }

    function clearFiles() {
        fileInput.value = "";
        selectedFiles.length = 0;
        fileChips.innerHTML = "";
        fileLimitNote.classList.add("hidden");
    }

    function showHomeView() {
        if (homePanel) homePanel.classList.remove("hidden");
        if (agenticPanel) agenticPanel.classList.add("hidden");
        if (mapPanel) mapPanel.classList.add("hidden");
        if (generatorPanel) generatorPanel.classList.add("hidden");
        if (outagesPanel) outagesPanel.classList.add("hidden");
        if (navHomeLink) navHomeLink.classList.add("active");
        if (navAgenticLink) navAgenticLink.classList.remove("active");
        if (navMapLink) navMapLink.classList.remove("active");
        if (navGeneratorLink) navGeneratorLink.classList.remove("active");
        if (navOutagesLink) navOutagesLink.classList.remove("active");
    }

    function showAgenticView() {
        if (homePanel) homePanel.classList.add("hidden");
        if (agenticPanel) agenticPanel.classList.remove("hidden");
        if (mapPanel) mapPanel.classList.add("hidden");
        if (generatorPanel) generatorPanel.classList.add("hidden");
        if (outagesPanel) outagesPanel.classList.add("hidden");
        if (navHomeLink) navHomeLink.classList.remove("active");
        if (navAgenticLink) navAgenticLink.classList.add("active");
        if (navMapLink) navMapLink.classList.remove("active");
        if (navGeneratorLink) navGeneratorLink.classList.remove("active");
        if (navOutagesLink) navOutagesLink.classList.remove("active");
    }

    async function showMapView() {
        if (homePanel) homePanel.classList.add("hidden");
        if (agenticPanel) agenticPanel.classList.add("hidden");
        if (mapPanel) mapPanel.classList.remove("hidden");
        if (generatorPanel) generatorPanel.classList.add("hidden");
        if (outagesPanel) outagesPanel.classList.add("hidden");
        if (navHomeLink) navHomeLink.classList.remove("active");
        if (navMapLink) navMapLink.classList.add("active");
        if (navAgenticLink) navAgenticLink.classList.remove("active");
        if (navGeneratorLink) navGeneratorLink.classList.remove("active");
        if (navOutagesLink) navOutagesLink.classList.remove("active");
        // Caught here because both callers discard the promise - the click handler is
        // an async listener and startup uses `void showMapView()`. Without this, a
        // throw would vanish and the only symptom would be an empty map.
        try {
            await ensureAssetMap();
        } catch (err) {
            logMapDiag("error", "Map: view failed to initialise", String(err && err.message ? err.message : err));
        }
    }

    function showGeneratorView() {
        if (homePanel) homePanel.classList.add("hidden");
        if (agenticPanel) agenticPanel.classList.add("hidden");
        if (mapPanel) mapPanel.classList.add("hidden");
        if (generatorPanel) generatorPanel.classList.remove("hidden");
        if (outagesPanel) outagesPanel.classList.add("hidden");
        if (navHomeLink) navHomeLink.classList.remove("active");
        if (navMapLink) navMapLink.classList.remove("active");
        if (navAgenticLink) navAgenticLink.classList.remove("active");
        if (navGeneratorLink) navGeneratorLink.classList.add("active");
        if (navOutagesLink) navOutagesLink.classList.remove("active");
        refreshGeneratorForecast();
    }

    function showOutagesView() {
        if (homePanel) homePanel.classList.add("hidden");
        if (agenticPanel) agenticPanel.classList.add("hidden");
        if (mapPanel) mapPanel.classList.add("hidden");
        if (generatorPanel) generatorPanel.classList.add("hidden");
        if (outagesPanel) outagesPanel.classList.remove("hidden");
        if (navHomeLink) navHomeLink.classList.remove("active");
        if (navMapLink) navMapLink.classList.remove("active");
        if (navAgenticLink) navAgenticLink.classList.remove("active");
        if (navGeneratorLink) navGeneratorLink.classList.remove("active");
        if (navOutagesLink) navOutagesLink.classList.add("active");
        if (outagesLoaded) return;
        setPageLoading(true, "Loading outages...");
        Promise.all([loadOutageAssets().then(() => loadOutages()), loadOutageEvents(), loadCrews()]).finally(() => {
            setPageLoading(false);
            outagesLoaded = true;
        });
    }

    function setPageLoading(visible, message = "Loading...") {
        if (!pageLoadingOverlay) return;
        if (visible) {
            if (pageLoadingMessage) pageLoadingMessage.textContent = message;
            pageLoadingOverlay.classList.remove("hidden");
        } else {
            pageLoadingOverlay.classList.add("hidden");
        }
    }

    function generatorParams() {
        return {
            num_locations: Number(genNumLocations.value),
            crew_count: Number(genCrewCount.value),
        };
    }

    async function refreshGeneratorForecast() {
        if (!generatorForecast) return;
        const params = generatorParams();
        const query = new URLSearchParams(
            Object.fromEntries(Object.entries(params).map(([key, value]) => [key, String(value)]))
        );
        try {
            const res = await fetch(`${API_BASE_URL}/generator/forecast?${query.toString()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const forecast = await res.json();
            generatorForecast.innerHTML = Object.entries(forecast)
                .map(([key, value]) => `<span>${key.replace(/_/g, " ")}: ${value.toLocaleString()}</span>`)
                .join("");
        } catch (err) {
            generatorForecast.innerHTML = `<span>Forecast unavailable</span>`;
            logMapDiag("error", "Generator: forecast fetch failed", String(err && err.message ? err.message : err));
        }
    }

    function setGeneratorStatus(kind, message) {
        if (!generatorStatus) return;
        generatorStatus.textContent = message;
        generatorStatus.classList.remove("hidden", "success", "error", "pending");
        generatorStatus.classList.add(kind);
    }

    let generatorTimerInterval = null;
    let generatorTimerSeconds = 0;

    function startGeneratorTimer(labelText) {
        generatorTimerSeconds = 0;
        setGeneratorStatus("pending", `${labelText} (0s)`);
        generatorTimerInterval = setInterval(() => {
            generatorTimerSeconds++;
            setGeneratorStatus("pending", `${labelText} (${generatorTimerSeconds}s)`);
        }, 1000);
    }

    function stopGeneratorTimer() {
        clearInterval(generatorTimerInterval);
        generatorTimerInterval = null;
        return generatorTimerSeconds;
    }

    [genNumLocations, genCrewCount].forEach((input) => {
        if (input) input.addEventListener("change", refreshGeneratorForecast);
    });

    if (btnGeneratorGenerate) {
        btnGeneratorGenerate.addEventListener("click", async () => {
            const confirmed = await confirmDialog({
                title: "Regenerate Synthetic Data",
                message: "Caution: Deletes your current data",
                confirmLabel: "Regenerate",
                variant: "caution",
            });
            if (!confirmed) return;
            const originalLabel = btnGeneratorGenerate.textContent;
            btnGeneratorGenerate.disabled = true;
            btnGeneratorGenerate.textContent = "Generating...";
            startGeneratorTimer("Generating data, please wait...");
            try {
                const res = await fetch(`${API_BASE_URL}/generator/generate`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ ...generatorParams(), confirm: true }),
                });
                if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
                const elapsed = stopGeneratorTimer();
                setGeneratorStatus("success", `Data generated successfully. (${elapsed}s)`);
            } catch (err) {
                const elapsed = stopGeneratorTimer();
                setGeneratorStatus("error", `Generation failed: ${err && err.message ? err.message : err} (${elapsed}s)`);
            } finally {
                btnGeneratorGenerate.disabled = false;
                btnGeneratorGenerate.textContent = originalLabel;
            }
        });
    }

    if (btnGeneratorClear) {
        btnGeneratorClear.addEventListener("click", async () => {
            const confirmed = await confirmDialog({
                title: "Clear Data",
                message: "Caution: Deletes your current data",
                confirmLabel: "Clear Data",
                variant: "caution",
            });
            if (!confirmed) return;
            const originalLabel = btnGeneratorClear.textContent;
            btnGeneratorClear.disabled = true;
            btnGeneratorClear.textContent = "Clearing...";
            setGeneratorStatus("pending", "Clearing data, please wait...");
            try {
                const res = await fetch(`${API_BASE_URL}/generator/clear?confirm=true`, { method: "POST" });
                if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
                setGeneratorStatus("success", "Generated data cleared.");
            } catch (err) {
                setGeneratorStatus("error", `Clear failed: ${err && err.message ? err.message : err}`);
            } finally {
                btnGeneratorClear.disabled = false;
                btnGeneratorClear.textContent = originalLabel;
            }
        });
    }

    // ===================================================================
    // Outage Management — deterministic REST calls, no orchestrator/agent involved.
    // ===================================================================
    // CLOSED intentionally excluded - RESTORED is the terminal state an operator
    // ever needs to pick; CLOSED still exists in the backend/schema but is no
    // longer something this screen asks anyone to click.
    const OUTAGE_STATUSES = ["REPORTED", "CONFIRMED", "CREW_ASSIGNED", "RESTORED"];
    const outageAssetNames = new Map();
    const outageAssetTypes = new Map();
    const outageAssetRegions = new Map();
    const outageEventNames = new Map();
    let crewList = [];

    function setOutageStatus(kind, message) {
        if (!outageStatus) return;
        outageStatus.textContent = message;
        outageStatus.classList.remove("hidden", "success", "error", "pending");
        outageStatus.classList.add(kind);
    }

    if (outageAssetAskLink && outageAssetSelect) {
        outageAssetAskLink.addEventListener("click", (event) => {
            event.preventDefault();
            const option = outageAssetSelect.selectedOptions[0];
            if (!option || !option.value) return;
            const assetName = outageAssetNames.get(option.value) || option.textContent;
            showAgenticView();
            promptTextarea.value = `What is the status of ${assetName}?`;
            promptTextarea.focus();
        });
    }

    async function loadOutageAssets() {
        if (!outageAssetSelect) return;
        try {
            const res = await fetch(`${API_BASE_URL}/map/assets`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const assets = data.assets || [];
            outageAssetNames.clear();
            outageAssetTypes.clear();
            outageAssetRegions.clear();
            assets.forEach((asset) => {
                outageAssetNames.set(asset.id, asset.name);
                outageAssetTypes.set(asset.id, asset.asset_type);
                outageAssetRegions.set(asset.id, asset.region);
            });
            if (assets.length === 0) {
                outageAssetSelect.innerHTML = `<option value="">No assets - generate synthetic data first</option>`;
                outageAssetSelect.disabled = true;
                if (btnOutageCreate) btnOutageCreate.disabled = true;
                return;
            }
            outageAssetSelect.disabled = false;
            if (btnOutageCreate) btnOutageCreate.disabled = false;
            outageAssetSelect.innerHTML = assets
                .map((asset) => `<option value="${asset.id}">${asset.name} (${asset.asset_type})</option>`)
                .join("");
        } catch (err) {
            outageAssetSelect.innerHTML = "";
            logMapDiag("error", "Outages: asset list fetch failed", String(err && err.message ? err.message : err));
        }
    }

    async function loadOutageEvents() {
        if (!outageEventSelect) return;
        const defaultOption = `<option value="">Create new default event (LOW severity)</option>`;
        try {
            const res = await fetch(`${API_BASE_URL}/events`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const events = await res.json();
            outageEventNames.clear();
            events.forEach((event) => outageEventNames.set(event.event_id, event.name || event.event_id));
            const options = events
                .map((event) => `<option value="${event.event_id}">${event.name || event.event_id} (${event.severity || "?"}, ${event.region || "?"})</option>`)
                .join("");
            outageEventSelect.innerHTML = defaultOption + options;
        } catch (err) {
            outageEventSelect.innerHTML = defaultOption;
            logMapDiag("error", "Outages: event list fetch failed", String(err && err.message ? err.message : err));
        }
    }

    async function loadOutages() {
        if (!outageList) return;
        try {
            const res = await fetch(`${API_BASE_URL}/outages`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const outages = await res.json();
            renderOutageList(outages);
        } catch (err) {
            outageList.innerHTML = `<p class="outage-empty">Outage list unavailable.</p>`;
            logMapDiag("error", "Outages: list fetch failed", String(err && err.message ? err.message : err));
        }
    }

    async function loadCrews() {
        try {
            const res = await fetch(`${API_BASE_URL}/crews`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            crewList = await res.json();
            populateOutageCrewSelect(currentOutageCrewRegion);
        } catch (err) {
            crewList = [];
            populateOutageCrewSelect(currentOutageCrewRegion);
            logMapDiag("error", "Outages: crew list fetch failed", String(err && err.message ? err.message : err));
        }
    }

    // Prefer a crew in the same region as the outage's asset - falls back to any
    // AVAILABLE crew if none match, so a small demo pool never blocks dispatch.
    let currentOutageCrewRegion = null;
    function populateOutageCrewSelect(assetRegion) {
        if (!outageCrewSelect) return;
        const available = crewList.filter((crew) => crew.status === "AVAILABLE");
        const sameRegion = assetRegion ? available.filter((crew) => crew.region === assetRegion) : [];
        const options = sameRegion.length ? sameRegion : available;
        outageCrewSelect.innerHTML = options
            .map((crew) => `<option value="${crew.crew_id}">${crew.crew_name} (${crew.crew_type || "?"}, ${crew.region || "?"})</option>`)
            .join("");
    }

    // Shared field, same pattern as Field Notes: applies to whichever row's Update
    // button is clicked next. Only relevant when that row's status is being set to
    // CREW_ASSIGNED, so it stays hidden otherwise. Re-fetches crews on every show -
    // availability changes as other rows get updated during the same session, so a
    // stale AVAILABLE list here could offer a crew someone just dispatched elsewhere.
    async function updateOutageCrewFieldVisibility(statusSelect, assetRegion) {
        if (!outageCrewField) return;
        const shouldShow = statusSelect.value === "CREW_ASSIGNED";
        outageCrewField.classList.toggle("hidden", !shouldShow);
        if (shouldShow) {
            currentOutageCrewRegion = assetRegion || null;
            await loadCrews();
        }
    }

    const STATUS_SELECT_COLOR_CLASSES = ["status-reported", "status-confirmed", "status-crew_assigned", "status-restored"];
    const STATUS_SELECT_COLOR_MAP = {
        REPORTED: "status-reported",
        CONFIRMED: "status-confirmed",
        CREW_ASSIGNED: "status-crew_assigned",
        RESTORED: "status-restored",
    };

    function applyStatusSelectColor(select) {
        select.classList.remove(...STATUS_SELECT_COLOR_CLASSES);
        const cls = STATUS_SELECT_COLOR_MAP[select.value];
        if (cls) select.classList.add(cls);
    }

    function renderOutageList(outages) {
        if (!outageList) return;
        if (!outages.length) {
            outageList.innerHTML = `<tr><td colspan="8" class="outage-empty">No outages yet.</td></tr>`;
            return;
        }
        outageList.innerHTML = "";
        outages.forEach((outage) => {
            const row = document.createElement("tr");

            const assetName = outageAssetNames.get(outage.asset_id) || outage.asset_id || "Unknown asset";
            const assetType = (outageAssetTypes.get(outage.asset_id) || "").toLowerCase();
            const eventName = outage.event_name || outageEventNames.get(outage.event_id) || outage.event_id || "Unknown event";
            const severity = (outage.event_severity || "unknown").toLowerCase();

            const assetCell = document.createElement("td");
            if (assetType) {
                const typeBadge = document.createElement("span");
                typeBadge.className = `asset-type-badge asset-type-${assetType}`;
                typeBadge.textContent = assetType.charAt(0).toUpperCase();
                assetCell.appendChild(typeBadge);
            }
            const assetLink = document.createElement("a");
            assetLink.className = "asset-result-link";
            assetLink.href = "#prompt-textarea";
            assetLink.textContent = assetName;
            assetLink.addEventListener("click", (event) => {
                event.preventDefault();
                showAgenticView();
                promptTextarea.value = `What is the status of ${assetName}?`;
                promptTextarea.focus();
            });
            assetCell.appendChild(assetLink);

            const idCell = document.createElement("td");
            idCell.textContent = outage.outage_id.slice(0, 8);

            const eventCell = document.createElement("td");
            eventCell.textContent = eventName;

            const severityCell = document.createElement("td");
            const severityBadge = document.createElement("span");
            severityBadge.className = `severity-badge severity-${severity}`;
            severityBadge.textContent = outage.event_severity || "?";
            severityCell.appendChild(severityBadge);

            const statusCell = document.createElement("td");
            const select = document.createElement("select");
            select.className = "outage-row-status";
            OUTAGE_STATUSES.forEach((status) => {
                const option = document.createElement("option");
                option.value = status;
                option.textContent = status;
                if (status === outage.status) option.selected = true;
                select.append(option);
            });
            select.addEventListener("change", () => {
                updateOutageCrewFieldVisibility(select, outageAssetRegions.get(outage.asset_id));
                applyStatusSelectColor(select);
            });
            applyStatusSelectColor(select);
            statusCell.appendChild(select);

            const crewCell = document.createElement("td");
            crewCell.textContent = outage.crew_name || "-";

            const impactCell = document.createElement("td");
            const impactValue = outage.impact_count;
            if (impactValue === null || impactValue === undefined) {
                impactCell.textContent = "?";
            } else {
                const impactBadge = document.createElement("span");
                const impactLevel = impactValue <= 150 ? "low" : impactValue <= 300 ? "medium" : "high";
                impactBadge.className = `impact-badge impact-${impactLevel}`;
                impactBadge.textContent = impactValue;
                impactCell.appendChild(impactBadge);
            }

            const actionCell = document.createElement("td");
            const button = document.createElement("button");
            button.className = "action-btn btn-analyze outage-row-btn";
            button.type = "button";
            button.textContent = "Update";
            button.addEventListener("click", async () => {
                button.disabled = true;
                try {
                    const res = await fetch(`${API_BASE_URL}/outages/${outage.outage_id}/transition`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            to_status: select.value,
                            note: outageNoteTextarea && outageNoteTextarea.value ? outageNoteTextarea.value : null,
                            crew_id: select.value === "CREW_ASSIGNED" && outageCrewSelect ? outageCrewSelect.value : null,
                        }),
                    });
                    if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
                    setOutageStatus("success", `Outage ${outage.outage_id.slice(0, 8)} moved to ${select.value}.`);
                    if (outageNoteTextarea) outageNoteTextarea.value = "";
                    if (outageCrewField) outageCrewField.classList.add("hidden");
                    await loadOutages();
                    await loadOutageEvents();
                    await loadCrews();
                } catch (err) {
                    setOutageStatus("error", `Update failed: ${err && err.message ? err.message : err}`);
                } finally {
                    button.disabled = false;
                }
            });
            actionCell.appendChild(button);

            row.append(assetCell, idCell, eventCell, severityCell, statusCell, crewCell, impactCell, actionCell);
            outageList.appendChild(row);
        });
    }

    if (btnOutageCreate) {
        btnOutageCreate.addEventListener("click", async () => {
            if (!outageAssetSelect || !outageAssetSelect.value) {
                setOutageStatus("error", "Select an asset first.");
                return;
            }
            const originalLabel = btnOutageCreate.textContent;
            btnOutageCreate.disabled = true;
            btnOutageCreate.textContent = "Creating...";
            setOutageStatus("pending", "Creating outage...");
            try {
                const res = await fetch(`${API_BASE_URL}/outages`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        asset_id: outageAssetSelect.value,
                        event_id: outageEventSelect && outageEventSelect.value ? outageEventSelect.value : null,
                    }),
                });
                if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
                setOutageStatus("success", "Outage created.");
                await loadOutages();
                await loadOutageEvents();
            } catch (err) {
                setOutageStatus("error", `Create failed: ${err && err.message ? err.message : err}`);
            } finally {
                btnOutageCreate.disabled = false;
                btnOutageCreate.textContent = originalLabel;
            }
        });
    }

    if (btnOutageRefresh) {
        btnOutageRefresh.addEventListener("click", async () => {
            btnOutageRefresh.disabled = true;
            try {
                await Promise.all([loadOutageAssets().then(() => loadOutages()), loadOutageEvents(), loadCrews()]);
                setOutageStatus("success", "List refreshed.");
            } catch (err) {
                setOutageStatus("error", `Refresh failed: ${err && err.message ? err.message : err}`);
            } finally {
                btnOutageRefresh.disabled = false;
            }
        });
    }

    function setMapWeatherStatus(text) {
        if (mapWeatherChip) mapWeatherChip.textContent = text;
    }

    // Every map-loading decision goes through here, so a blank map is never a mystery.
    // Writes to the browser console (durable) AND the Execution Trace panel (convenient,
    // but cleared on each chat submit and hidden while the map view is showing).
    function logMapDiag(kind, title, detail) {
        const line = detail ? `${title} - ${detail}` : title;
        if (kind === "error" || kind === "fail") {
            console.warn("[map]", line);
        } else {
            console.info("[map]", line);
        }
        try {
            addInstrumentationRow(kind, title, detail);
        } catch (_) {
            // Trace panel not mounted yet (page still booting) - console already has it.
        }
    }

    // fetch() has no built-in timeout: a server that accepts the connection but never
    // answers leaves the promise pending forever. AbortController is the only way to
    // put a ceiling on it.
    async function fetchWithTimeout(url, options, timeoutMs) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        try {
            return await fetch(url, { ...options, signal: controller.signal });
        } finally {
            clearTimeout(timer);
        }
    }

    // The map popup is a separate window with a SEPARATE console. Anything it logs is
    // invisible unless you knew to open devtools on that window specifically - which is
    // exactly how the weather-first bug hid for so long. The popup calls this on the
    // opener for every error and console line, so its output lands in THIS tab's
    // console and the Execution Trace alongside everything else.
    //
    // Safe to expose on window: the popup is same-origin (we document.write it), and
    // this only formats text into a log. It takes no action.
    window.reportMapPopupLog = function (kind, message) {
        logMapDiag(
            kind === "error" || kind === "fail" ? "error" : "step",
            "Map popup",
            String(message)
        );
    };

    // Iowa State Mesonet serves real NEXRAD tiles at every zoom level we use.
    // RainViewer's free tilecache was removed: it caps at zoom 7 and returns a
    // "Zoom Level Not Supported" placeholder PNG (HTTP 200) for zoom >= 8.
    function addRadarLayer(targetMap) {
        try {
            const radarLayer = L.tileLayer(
                "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png",
                {
                    opacity: 0.45,
                    maxZoom: 18,
                    attribution: "&copy; Iowa State Mesonet",
                }
            );
            radarLayer.addTo(targetMap);
            return radarLayer;
        } catch (error) {
            console.warn("Mesonet radar load failed:", error);
            return null;
        }
    }

    // Ray casting: ring is a closed [lng, lat] array (GeoJSON order). Only needs to
    // handle the simple (non-self-intersecting) polygons our demo preset uses.
    function pointInPolygonRing(lng, lat, ring) {
        let inside = false;
        for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            const xi = ring[i][0], yi = ring[i][1];
            const xj = ring[j][0], yj = ring[j][1];
            const intersect = ((yi > lat) !== (yj > lat)) &&
                (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    }

    function ringCentroid(ring) {
        const pts = ring.slice(0, -1); // drop the closing duplicate vertex
        const sum = pts.reduce((acc, [lng, lat]) => [acc[0] + lng, acc[1] + lat], [0, 0]);
        return L.latLng(sum[1] / pts.length, sum[0] / pts.length);
    }

    async function addMapWeatherOverlay() {
        if (!assetMap) return;
        setMapWeatherStatus("Weather: loading...");
        let alertsCount = 0;
        let radarProvider = "";
        if (mapRadarLayer && assetMap.hasLayer(mapRadarLayer)) {
            assetMap.removeLayer(mapRadarLayer);
        }
        if (weatherLayer && assetMap.hasLayer(weatherLayer)) {
            assetMap.removeLayer(weatherLayer);
            weatherLayer = null;
        }
        if (stormDragMarker && assetMap.hasLayer(stormDragMarker)) {
            assetMap.removeLayer(stormDragMarker);
        }
        stormDragMarker = null;
        stormPolygonLayer = null;
        stormBaseRing = null;
        stormBaseAlert = null;
        stormDragOrigin = null;
        mapRadarLayer = addRadarLayer(assetMap);
        if (mapRadarLayer) {
            radarProvider = "Mesonet";
        }

        // Two attempts at 3s each. The backend already owns the NWS call (and demo
        // mode); a single stall on our own /map/weather endpoint should not cost us
        // the alerts overlay, but looping past two tries just means it is down.
        // simulatedStormActive appends ?demo=true - a live, no-restart way to force
        // the hardcoded demo alert for this fetch only (see Simulate Storm toggle).
        const weatherUrl = `${API_BASE_URL}/map/weather` + (simulatedStormActive ? "?demo=true" : "");
        let alertsData = null;
        for (let attempt = 1; attempt <= 2 && !alertsData; attempt += 1) {
            try {
                const res = await fetchWithTimeout(
                    weatherUrl,
                    { cache: "no-store" },
                    3000
                );
                if (res.ok) {
                    alertsData = await res.json();
                    logMapDiag("step", "Weather: TX alerts loaded", `attempt ${attempt}`);
                } else {
                    logMapDiag("fail", "Weather: alerts request rejected", `HTTP ${res.status} on attempt ${attempt}`);
                }
            } catch (error) {
                const timedOut = error && error.name === "AbortError";
                logMapDiag(
                    "fail",
                    timedOut ? "Weather: timed out after 3s" : "Weather: alerts fetch failed",
                    attempt === 1 ? "retrying once" : String(error && error.message ? error.message : error)
                );
            }
        }

        try {
            if (alertsData) {
                // Backend returns a flat {alerts: [{event, severity, headline, geometry,
                // matching_asset_ids}]} list, not a GeoJSON FeatureCollection - adapt it
                // into the {properties, geometry} shape L.geoJSON expects, unchanged below.
                const alerts = Array.isArray(alertsData.alerts) ? alertsData.alerts : [];
                const features = alerts.map((alert) => ({
                    type: "Feature",
                    properties: {
                        event: alert.event,
                        severity: alert.severity,
                        headline: alert.headline,
                    },
                    geometry: alert.geometry,
                }));
                alertsCount = features.length;
                renderOperatorAlertPanel(alerts);
                weatherLayer = L.geoJSON(features, {
                    style: (feature) => {
                        const headline = String(feature?.properties?.headline || "");
                        // Simulated storm (Gate 10) gets its own scary-purple look so it
                        // is visually obvious it is a demo, not a real NWS alert.
                        if (headline.includes("(demo alert)")) {
                            return { color: "#4c1d95", weight: 3, fillColor: "#7e22ce", fillOpacity: 0.35 };
                        }
                        const severity = String(feature?.properties?.severity || "").toLowerCase();
                        if (severity === "extreme") return { color: "#dc2626", weight: 2, fillColor: "#ef4444", fillOpacity: 0.18 };
                        if (severity === "severe") return { color: "#f97316", weight: 2, fillColor: "#fb923c", fillOpacity: 0.16 };
                        if (severity === "moderate") return { color: "#eab308", weight: 2, fillColor: "#fde047", fillOpacity: 0.14 };
                        return { color: "#0284c7", weight: 2, fillColor: "#38bdf8", fillOpacity: 0.12 };
                    },
                    onEachFeature: (feature, layer) => {
                        const p = feature?.properties || {};
                        const event = p.event || "Weather Alert";
                        const severity = p.severity || "Unknown";
                        const headline = p.headline || "";
                        layer.bindTooltip(event, { direction: "top", opacity: 0.95 });
                        layer.bindPopup(
                            "<strong>" + escapeHtml(String(event)) + "</strong><br>" +
                            "Severity: " + escapeHtml(String(severity)) + "<br>" +
                            escapeHtml(String(headline))
                        );
                        // Stash the one demo-storm layer + its untranslated ring so the
                        // drag handle below can move it without refetching.
                        if (String(headline).includes("(demo alert)") && feature.geometry?.coordinates?.[0]) {
                            stormPolygonLayer = layer;
                            stormBaseRing = feature.geometry.coordinates[0].map(([lng, lat]) => [lng, lat]);
                            stormBaseAlert = alerts.find((a) => a.headline === headline) || null;
                        }
                    },
                }).addTo(assetMap);

                // Live-drag handle: only when the simulated storm is on and we found its
                // polygon above. Dragging translates the polygon + recomputes matching
                // assets client-side (ray casting against the already-loaded asset list),
                // no backend call, so the operator panel updates instantly while dragging.
                if (simulatedStormActive && stormPolygonLayer && stormBaseRing) {
                    stormDragOrigin = ringCentroid(stormBaseRing);
                    stormDragMarker = L.marker(stormDragOrigin, {
                        draggable: true,
                        icon: L.divIcon({ className: "storm-drag-handle", html: "\u2725", iconSize: [34, 34] }),
                        title: "Drag to move the simulated storm",
                        zIndexOffset: 5000,
                    }).addTo(assetMap);
                    stormDragMarker.on("drag", () => {
                        const cur = stormDragMarker.getLatLng();
                        const dLat = cur.lat - stormDragOrigin.lat;
                        const dLng = cur.lng - stormDragOrigin.lng;
                        const movedRing = stormBaseRing.map(([lng, lat]) => [lng + dLng, lat + dLat]);
                        stormPolygonLayer.setLatLngs([movedRing.map(([lng, lat]) => [lat, lng])]);
                        const movedAssetIds = mapAssets
                            .filter((asset) => pointInPolygonRing(Number(asset.lng), Number(asset.lat), movedRing))
                            .map((asset) => asset.id);
                        renderOperatorAlertPanel([{ ...(stormBaseAlert || {}), matching_asset_ids: movedAssetIds }]);
                    });
                }
            }
        } catch (error) {
            logMapDiag("fail", "Weather: alert rendering failed", String(error && error.message ? error.message : error));
        }

        if (radarProvider) {
            setMapWeatherStatus("Weather: " + radarProvider + " radar • TX alerts " + alertsCount);
        } else if (alertsCount > 0) {
            setMapWeatherStatus("Weather: TX alerts " + alertsCount);
        } else {
            setMapWeatherStatus("Weather: unavailable");
        }
    }

    // Separate from #map-weather-chip and from chat: a persistent banner that only
    // shows up when an active alert actually overlaps a monitored asset (backend
    // already did the point-in-polygon match and sent matching_asset_ids per alert).
    function renderOperatorAlertPanel(alerts) {
        const panel = document.getElementById("map-alert-panel");
        if (!panel) return;

        const assetNameById = new Map(mapAssets.map((asset) => [asset.id, asset.name]));
        const rows = [];
        for (const alert of alerts || []) {
            const ids = Array.isArray(alert.matching_asset_ids) ? alert.matching_asset_ids : [];
            if (!ids.length) continue;
            const names = ids.map((id) => assetNameById.get(id) || id).join(", ");
            rows.push(
                "⚠ Active " + escapeHtml(String(alert.event || "Weather Alert")) +
                " — " + ids.length + " asset" + (ids.length === 1 ? "" : "s") +
                " affected: " + escapeHtml(names)
            );
        }

        if (!rows.length) {
            panel.classList.add("hidden");
            panel.innerHTML = "";
            return;
        }

        panel.innerHTML = rows.map((row) => '<div class="map-alert-row">' + row + "</div>").join("");
        panel.classList.remove("hidden");
    }

    function symbolForMapAssetType(assetType) {
        const t = String(assetType || "").toLowerCase();
        if (t.includes("substation")) return { symbol: "S", className: "sym-substation" };
        if (t.includes("feeder")) return { symbol: "F", className: "sym-feeder" };
        if (t.includes("transformer")) return { symbol: "T", className: "sym-transformer" };
        return { symbol: "•", className: "sym-default" };
    }

    // outageStyled=true overrides the normal type color with the red outage color;
    // the symbol (S/F/T/•) is unchanged either way.
    function iconForMapAsset(asset, outageStyled) {
        const typeSymbol = symbolForMapAssetType(asset.asset_type);
        const className = outageStyled ? "sym-outage" : typeSymbol.className;
        return L.divIcon({
            className: "asset-icon-wrap",
            html: '<div class="asset-icon ' + className + '">' + typeSymbol.symbol + '</div>',
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -14],
        });
    }

    function markerForMapAsset(asset) {
        return L.marker([asset.lat, asset.lng], { icon: iconForMapAsset(asset, false) });
    }

    const MAP_ASSET_STATUS_LABELS = {
        NORMAL: "Normal (no open outage)",
        REPORTED: "Reported outage",
        CONFIRMED: "Confirmed outage",
        CREW_ASSIGNED: "Crew assigned",
    };
    function mapAssetStatusLabel(status) {
        return MAP_ASSET_STATUS_LABELS[status] || status || "unknown";
    }

    // Leaflet is a third-party CDN script. "Not there yet" and "never coming" look
    // identical at any single instant, so look repeatedly for a few seconds before
    // declaring it dead. Checking once was why a slow CDN killed the map permanently.
    async function waitForLeaflet(timeoutMs) {
        const deadline = Date.now() + timeoutMs;
        while (typeof L === "undefined" && Date.now() < deadline) {
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return typeof L !== "undefined";
    }

    // A dead map must SAY it is dead, in the panel the user is staring at. The console
    // and the trace panel are both easy to miss.
    function showMapMessage(message) {
        if (!mapContainer) return;
        mapContainer.innerHTML =
            '<p style="padding:1rem;color:#fca5a5;font-weight:600;">' + escapeHtml(message) + "</p>";
    }

    // Asset load failed and there is no local fallback data. Show it in the map panel
    // with a Retry button that re-runs the (bounded) load.
    function showMapError() {
        if (!mapContainer) return;
        if (assetMap) { assetMap.remove(); assetMap = null; }
        mapContainer.innerHTML =
            '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;' +
            'height:100%;gap:0.75rem;padding:1.5rem;text-align:center;">' +
            '<p style="color:#fca5a5;font-weight:600;margin:0;">Couldn\'t load map assets from the database.</p>' +
            '<p style="color:#94a3b8;margin:0;font-size:0.9rem;">Tried ' + MAX_MAP_ASSET_RETRIES +
            ' times with no usable response.</p>' +
            '<p style="color:#94a3b8;margin:0;font-size:0.9rem;">If this is a fresh database, generate synthetic data first.</p>' +
            '<button id="map-retry-btn" type="button" style="padding:0.5rem 1.25rem;border:0;border-radius:6px;' +
            'background:#2563eb;color:#fff;font-weight:600;cursor:pointer;">Retry</button>' +
            '</div>';
        const btn = document.getElementById("map-retry-btn");
        if (btn) {
            btn.addEventListener("click", () => {
                mapAssetsLoaded = false;
                mapAssets = [];
                showMapMessage("Retrying...");
                ensureAssetMap();
            });
        }
    }

    async function ensureAssetMap() {
        logMapDiag("intent", "Map: view opened", "loading assets, then drawing");

        // The backend call goes FIRST and depends on nothing above it.
        //
        // Drawing needs Leaflet. ASKING THE BACKEND DOES NOT. The old order checked
        // Leaflet first and returned silently if anything was missing, so a CDN hiccup
        // meant GET /map/assets was never sent and the console stayed completely empty.
        // In this order that failure mode cannot exist: the request always happens, and
        // whatever goes wrong afterwards is a rendering problem with a visible message.
        if (!mapAssetsLoaded) {
            mapAssets = await loadMapAssets();
        }

        if (!mapContainer) {
            logMapDiag("error", "Map: container missing", "#asset-map is not in the DOM - nothing to draw into");
            return;
        }

        if (!mapAssets.length) {
            logMapDiag("error", "Map: no assets to plot", "showing in-map error with Retry");
            // Mark as loaded so revisiting this panel doesn't silently redo the whole
            // fetch/retry cycle every time - only the Retry button (which resets this
            // flag itself) should trigger another attempt.
            mapAssetsLoaded = true;
            showMapError();
            return;
        }

        if (!(await waitForLeaflet(5000))) {
            logMapDiag(
                "error",
                "Map: Leaflet never loaded",
                `assets fetched (${mapAssets.length}) but the leaflet.js CDN did not load - cannot draw`
            );
            showMapMessage("Map library failed to load (leaflet.js). Assets were fetched. Reload the page to retry.");
            return;
        }

        const texasBounds = getTexasBounds();
        if (!assetMap) {
            assetMap = L.map(mapContainer, {
                zoomControl: true,
                maxBounds: texasBounds,
                minZoom: 5,
            }).setView([32.4, -96.5], 8);

            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 18,
                attribution: "&copy; OpenStreetMap contributors",
            }).addTo(assetMap);

            // Weather is decorative. It used to run FIRST and be awaited, so a stalled
            // weather.gov call meant /map/assets was never even requested and the map
            // sat empty forever. It now runs last and un-awaited - it can fail all it
            // likes without costing us the assets.
            addMapWeatherOverlay().catch((err) =>
                logMapDiag("error", "Weather: overlay failed", String(err && err.message ? err.message : err))
            );
        }

        // Retried on every entry until it actually succeeds, so one bad startup does
        // not leave a permanently empty map for the life of the page.
        if (!mapAssetsLoaded) {
            const bounds = L.latLngBounds();
            markersByAssetId = new Map();
            for (const asset of mapAssets) {
                const marker = markerForMapAsset(asset).addTo(assetMap);
                markersByAssetId.set(asset.id, marker);
                marker.bindPopup(
                    "<strong>" + escapeHtml(asset.name || asset.id || "Asset") + "</strong><br>" +
                    "ID: " + escapeHtml(asset.id || "-") + "<br>" +
                    "Type: " + escapeHtml(asset.asset_type || "-") + "<br>" +
                    "Status: " + escapeHtml(mapAssetStatusLabel(asset.status)) +
                    (asset.crew_name ? "<br>Crew: " + escapeHtml(asset.crew_name) : "")
                );
                marker.bindTooltip(escapeHtml(asset.name || asset.id || "Asset"), {
                    direction: "top",
                    offset: [0, -12],
                    opacity: 0.95,
                });
                bounds.extend([asset.lat, asset.lng]);
            }

            if (bounds.isValid()) {
                setTimeout(() => {
                    assetMap.invalidateSize();
                    assetMap.fitBounds(bounds, { padding: [30, 30] });
                }, 0);
                mapAssetsLoaded = true;
                applyOutageDimming();
            } else {
                assetMap.fitBounds(texasBounds, { padding: [20, 20] });
                logMapDiag("error", "Map: no assets plotted", "map is empty - will retry on next view switch");
            }
        }

        setTimeout(() => assetMap.invalidateSize(), 0);
    }

    async function openAssetMapPopup() {
        const popup = window.open(
            "",
            "reliable-agents-asset-map",
            "popup=yes,width=1280,height=820,left=120,top=90,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes"
        );
        if (!popup) {
            showError("Popup blocked. Please allow popups for this site.");
            return;
        }

        // window.open() hands back a blank white document. The asset load below is
        // awaited, so without something painted here the user stares at white and
        // cannot tell "still working" from "broken".
        popup.document.open();
        popup.document.write(
            '<!DOCTYPE html><html><head><title>Reliable Agents Asset Map</title></head>' +
            '<body style="margin:0;background:#0f172a;color:#e2e8f0;' +
            'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">' +
            '<p style="padding:1rem;">Loading assets...</p></body></html>'
        );
        popup.document.close();

        // Assets are loaded HERE, in the opener, by the same loadMapAssets() the
        // inline map uses - so the popup inherits its timeout, retries, local-file
        // fallback and Execution Trace diagnostics for free.
        //
        // The popup used to run its own private copy of this fetch. When the inline
        // map was fixed, that copy was missed and kept the original bug: it awaited
        // the weather overlay first, so a slow api.weather.gov call meant /map/assets
        // was never requested, and it reported the failure with console.error into
        // the popup's own console where nobody looks. The popup now receives finished
        // data and does no fetching at all, so there is only one loader left to break.
        let assets = [];
        try {
            assets = await loadMapAssets();
        } catch (err) {
            logMapDiag("error", "Map popup: asset load threw", String(err && err.message ? err.message : err));
        }

        if (popup.closed) {
            return;
        }

        // Baked into the document below as data, so escape anything that could end
        // the script tag early or break the parse.
        const assetsJson = JSON.stringify(assets)
            .replace(/</g, "\\u003c")
            .replace(/\u2028/g, "\\u2028")
            .replace(/\u2029/g, "\\u2029");

        const popupHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Reliable Agents Asset Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
  <style>
    html, body { margin: 0; height: 100%; background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    .wrap { display: flex; flex-direction: column; height: 100%; }
    .toolbar { display: flex; flex-wrap: wrap; gap: .5rem; padding: .75rem .9rem; border-bottom: 1px solid #334155; background: #111827; }
    .chip { padding: .32rem .66rem; border-radius: 999px; font-size: .78rem; font-weight: 600; border: 1px solid transparent; }
    .chip-substation { color: #7f1d1d; background: #fee2e2; border-color: #fecaca; }
    .chip-feeder { color: #1e3a8a; background: #dbeafe; border-color: #bfdbfe; }
    .chip-transformer { color: #78350f; background: #fef3c7; border-color: #fde68a; }
    .chip-default { color: #14532d; background: #dcfce7; border-color: #bbf7d0; }
    .chip-weather { color: #075985; background: #e0f2fe; border-color: #bae6fd; }
    #fatal { display: none; padding: .6rem .9rem; background: #7f1d1d; color: #fee2e2; font-size: .84rem; font-weight: 600; border-bottom: 1px solid #dc2626; white-space: pre-wrap; }
    #fatal.show { display: block; }
    #map { flex: 1 1 auto; min-height: 0; }
    .asset-icon-wrap { background: transparent; border: 0; }
    .asset-icon {
            width: 30px;
            height: 30px;
      border-radius: 999px;
      display: flex;
      align-items: center;
      justify-content: center;
    font-size: 14px;
      font-weight: 800;
    border: 3px solid #166534;
      color: #14532d;
      background: #dcfce7;
    box-shadow: 0 2px 7px rgba(0,0,0,.5);
    }
    .asset-icon.sym-substation { background: #fee2e2; color: #991b1b; border-color: #dc2626; }
    .asset-icon.sym-feeder { background: #dbeafe; color: #1e3a8a; border-color: #2563eb; }
    .asset-icon.sym-transformer { background: #fef3c7; color: #78350f; border-color: #d97706; }
    .asset-icon.sym-default { background: #dcfce7; color: #14532d; border-color: #166534; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="toolbar">
      <span class="chip chip-substation">S = Substation</span>
      <span class="chip chip-feeder">F = Feeder</span>
      <span class="chip chip-transformer">T = Transformer</span>
      <span class="chip chip-default">• = Other/Unknown</span>
      <span id="weather-chip" class="chip chip-weather">Weather: loading...</span>
    </div>
    <div id="fatal"></div>
    <div id="map"></div>
  </div>

  <script>
    // Registered BEFORE Leaflet loads, so even "the CDN is blocked and L is
    // undefined" shows up on screen instead of dying silently in a popup console
    // that nobody has open. Nothing in this window is allowed to fail invisibly.

    // This window has its own console. Everything logged here is echoed to the
    // opener so it lands in the main tab's console and Execution Trace, where you
    // are already looking. Wrapped in try/catch because the opener can be closed,
    // navigated away, or reloaded out from under us - losing a log line must never
    // be what breaks the map.
    function toOpener(kind, message) {
      try {
        if (window.opener && !window.opener.closed && window.opener.reportMapPopupLog) {
          window.opener.reportMapPopupLog(kind, message);
        }
      } catch (_) {}
    }

    // Keep the popup's own console working, then tee each line to the opener. Errors
    // and warnings only - info/debug noise is not worth pushing into the trace panel.
    ["error", "warn"].forEach(function (level) {
      var original = console[level] ? console[level].bind(console) : function () {};
      console[level] = function () {
        original.apply(null, arguments);
        toOpener(level === "error" ? "error" : "fail",
          Array.prototype.map.call(arguments, function (a) {
            if (a instanceof Error) return a.message;
            if (typeof a === "object") { try { return JSON.stringify(a); } catch (_) { return String(a); } }
            return String(a);
          }).join(" ")
        );
      };
    });

    window.showMapError = function (message) {
      var el = document.getElementById("fatal");
      if (el) {
        el.textContent = String(message);
        el.className = "show";
      }
      // Goes through the wrapped console above, so it reaches the opener too.
      console.error("[map popup]", message);
    };
    window.addEventListener("error", function (e) {
      window.showMapError("Map error: " + ((e && e.message) || "script failed to load"));
    }, true);
    window.addEventListener("unhandledrejection", function (e) {
      var reason = e && e.reason;
      window.showMapError("Map error: " + ((reason && reason.message) || String(reason)));
    });
  <\/script>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""><\/script>
  <script>
    const ASSETS = ${assetsJson};
    const texasBounds = L.latLngBounds(
      [25.8, -106.8],  // SW
      [36.7, -93.5]    // NE
    );
    const map = L.map("map", { zoomControl: true, maxBounds: texasBounds, minZoom: 5 }).setView([32.4, -96.5], 8);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    const weatherChip = document.getElementById("weather-chip");

    function setWeatherStatus(text) {
      if (weatherChip) weatherChip.textContent = text;
    }

    async function addWeatherOverlay() {
      let alertsCount = 0;
      let radarAdded = false;

      try {
        L.tileLayer("https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png", {
          opacity: 0.45,
          maxZoom: 18,
          attribution: "&copy; Iowa State Mesonet"
        }).addTo(map);
        radarAdded = true;
      } catch (_) {}

      try {
        const controller = new AbortController();
        const timer = setTimeout(function () { controller.abort(); }, 5000);
        let res;
        try {
          res = await fetch("https://api.weather.gov/alerts/active?area=TX", {
            cache: "no-store",
            signal: controller.signal,
            headers: { "Accept": "application/geo+json" }
          });
        } finally {
          clearTimeout(timer);
        }
        if (res.ok) {
          const data = await res.json();
          const features = Array.isArray(data.features) ? data.features : [];
          alertsCount = features.length;
          L.geoJSON(features, {
            style: (feature) => {
              const severity = String(feature?.properties?.severity || "").toLowerCase();
              if (severity === "extreme") return { color: "#dc2626", weight: 2, fillColor: "#ef4444", fillOpacity: 0.18 };
              if (severity === "severe") return { color: "#f97316", weight: 2, fillColor: "#fb923c", fillOpacity: 0.16 };
              if (severity === "moderate") return { color: "#eab308", weight: 2, fillColor: "#fde047", fillOpacity: 0.14 };
              return { color: "#0284c7", weight: 2, fillColor: "#38bdf8", fillOpacity: 0.12 };
            },
            onEachFeature: (feature, layer) => {
              const p = feature?.properties || {};
              const event = p.event || "Weather Alert";
              const severity = p.severity || "Unknown";
              const headline = p.headline || "";
              layer.bindTooltip(event, { direction: "top", opacity: 0.95 });
              layer.bindPopup(
                "<strong>" + esc(String(event)) + "</strong><br>" +
                "Severity: " + esc(String(severity)) + "<br>" +
                esc(String(headline))
              );
            }
          }).addTo(map);
        }
      } catch (_) {}

      if (radarAdded) {
        setWeatherStatus("Weather: radar on • TX alerts " + alertsCount);
      } else if (alertsCount > 0) {
        setWeatherStatus("Weather: TX alerts " + alertsCount);
      } else {
        setWeatherStatus("Weather: unavailable");
      }
    }

    function markerStyleForStatus(status) {
      const s = String(status || "").toLowerCase();
      if (s === "outage" || s === "critical" || s === "error") {
        return { radius: 10, color: "#e53935", weight: 2, fillColor: "#ef5350", fillOpacity: 0.45 };
      }
      if (s === "warning" || s === "degraded" || s === "alert") {
        return { radius: 10, color: "#f59e0b", weight: 2, fillColor: "#fbbf24", fillOpacity: 0.45 };
      }
      return { radius: 9, color: "#22c55e", weight: 2, fillColor: "#4ade80", fillOpacity: 0.4 };
    }

    function symbolForAssetType(assetType) {
      const t = String(assetType || "").toLowerCase();
      if (t.includes("substation")) return { symbol: "S", className: "sym-substation" };
      if (t.includes("feeder")) return { symbol: "F", className: "sym-feeder" };
      if (t.includes("transformer")) return { symbol: "T", className: "sym-transformer" };
      return { symbol: "•", className: "sym-default" };
    }

    function markerForAsset(asset) {
      const typeSymbol = symbolForAssetType(asset.asset_type);
      const icon = L.divIcon({
        className: "asset-icon-wrap",
        html: '<div class="asset-icon ' + typeSymbol.className + '">' + typeSymbol.symbol + '</div>',
        iconSize: [30, 30],
        iconAnchor: [15, 15],
        popupAnchor: [0, -14],
      });
      return L.marker([asset.lat, asset.lng], { icon });
    }

    function esc(value) {
      return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    }

    function normalizeAsset(row) {
      const lat = Number(row.lat ?? row.latitude ?? row.laitude);
      const lng = Number(row.lng ?? row.longitude ?? row.longitiude ?? row.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
      return {
        id: String(row.id ?? row.asset_id ?? ""),
        name: String(row.name ?? row.asset_name ?? row.id ?? "Asset"),
        asset_type: String(row.asset_type ?? ""),
        status: String(row.status ?? "NORMAL"),
        crew_name: row.crew_name || null,
        lat,
        lng
      };
    }

    const MAP_ASSET_STATUS_LABELS = {
      NORMAL: "Normal (no open outage)",
      REPORTED: "Reported outage",
      CONFIRMED: "Confirmed outage",
      CREW_ASSIGNED: "Crew assigned",
    };
    function mapAssetStatusLabel(status) {
      return MAP_ASSET_STATUS_LABELS[status] || status || "unknown";
    }

    // No fetching here, on purpose. ASSETS was loaded by the opener and injected as
    // data. Rendering is synchronous, so nothing external can stop the map drawing.
    function renderAssets() {
      const bounds = L.latLngBounds();
      let plotted = 0;
      for (const row of ASSETS) {
        const asset = normalizeAsset(row);
        if (!asset) continue;
        const marker = markerForAsset(asset).addTo(map);
        marker.bindPopup(
          "<strong>" + esc(asset.name || asset.id || "Asset") + "</strong><br>" +
          "ID: " + esc(asset.id || "-") + "<br>" +
          "Type: " + esc(asset.asset_type || "-") + "<br>" +
          "Status: " + esc(mapAssetStatusLabel(asset.status)) +
          (asset.crew_name ? "<br>Crew: " + esc(asset.crew_name) : "")
        );
        marker.bindTooltip(esc(asset.name || asset.id || "Asset"), { direction: "top", offset: [0, -12], opacity: 0.95 });
        bounds.extend([asset.lat, asset.lng]);
        plotted++;
      }
   if (plotted && bounds.isValid()) {
    setTimeout(function () {
     map.invalidateSize();
     map.fitBounds(bounds, { padding: [30, 30] });
    }, 0);
   } else {
        map.fitBounds(texasBounds, { padding: [20, 20] });
        window.showMapError("No assets to plot. The map is empty - open the main window's Execution Trace or console for the reason.");
      }
    }

    try {
      renderAssets();
    } catch (err) {
      window.showMapError("Asset rendering failed: " + ((err && err.message) || err));
    }

    // Weather is decorative, so it runs LAST and un-awaited. It used to run FIRST and
    // be awaited, which meant a slow api.weather.gov call stopped the assets from
    // ever being drawn. Never put it in front of the assets again.
    addWeatherOverlay().catch(function (err) {
      setWeatherStatus("Weather: unavailable");
      console.warn("Weather overlay failed:", err);
    });

    if (map) {
      setTimeout(() => map.invalidateSize(), 0);
    }
  <\/script>
</body>
</html>`;
        popup.document.open();
        popup.document.write(popupHtml);
        popup.document.close();
        popup.focus();
    }

    function openImagePopup(imageUrl, windowName, title) {
        const popup = window.open(
            "",
            windowName,
            "popup=yes,width=1280,height=820,left=120,top=90,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes"
        );
        if (!popup) {
            showError("Popup blocked. Please allow popups for this site.");
            return;
        }

        const safeTitle = escapeHtml(title || "Image");
        const safeImageUrl = escapeHtml(imageUrl);
        popup.document.open();
        popup.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${safeTitle}</title>
  <style>
    html, body { margin: 0; height: 100%; background: #0b1220; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    .wrap { display: flex; align-items: center; justify-content: center; height: 100%; padding: 1rem; box-sizing: border-box; }
    img { max-width: 100%; max-height: 100%; border-radius: 8px; box-shadow: 0 8px 30px rgba(0,0,0,0.45); background: #111827; }
  </style>
</head>
<body>
  <div class="wrap">
    <img src="${safeImageUrl}" alt="${safeTitle}" />
  </div>
</body>
</html>`);
        popup.document.close();
        popup.focus();
    }

    function openDocumentPopup(url, windowName) {
        const popup = window.open(
            url,
            windowName,
            "popup=yes,width=1280,height=820,left=120,top=90,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes"
        );
        if (!popup) {
            showError("Popup blocked. Please allow popups for this site.");
            return;
        }
        popup.focus();
    }


    // One mapper for both sources. This was copy-pasted twice; two copies of a
    // coordinate parser is how one of them quietly stops matching the other.
    function normalizeMapAssetRows(rows) {
        return rows
            .map((row) => ({
                id: String(row.id ?? row.asset_id ?? ""),
                name: String(row.name ?? row.asset_name ?? row.id ?? "Asset"),
                asset_type: String(row.asset_type ?? ""),
                lat: Number(row.lat ?? row.latitude ?? row.laitude),
                lng: Number(row.lng ?? row.longitude ?? row.longitiude ?? row.lon),
                status: String(row.status ?? "NORMAL"),
                in_outage: Boolean(row.in_outage),
                crew_name: row.crew_name || null,
            }))
            .filter((row) => Number.isFinite(row.lat) && Number.isFinite(row.lng));
    }

    // The ONLY place asset data is loaded. Both the inline map and the popup map go
    // through here, so there is exactly one thing to fix when it misbehaves.
    //
    // Every request uses fetchWithTimeout, never a bare fetch(). A bare fetch has no
    // timeout at all: the backend accepts the TCP connection before it is ready to
    // answer, so the promise can stay pending forever and the map waits forever with
    // it. That is the failure that keeps coming back. Do not put a bare fetch here.
    async function loadMapAssets() {
        // Retry the MCP-backed /map/assets endpoint through backend/MCP cold start, but
        // BOUNDED: an unbounded loop against a failing endpoint opens a fresh cold DB
        // connection every retry and can pin the server's connection count. After the
        // cap we fall through to the local file instead of hammering the DB forever.
        let attempt = 0;
        while (attempt < MAX_MAP_ASSET_RETRIES) {
            attempt++;
            logMapDiag("intent", "Map: requesting assets", `GET ${API_BASE_URL}/map/assets (attempt ${attempt}/${MAX_MAP_ASSET_RETRIES})`);
            try {
                const res = await fetchWithTimeout(
                    `${API_BASE_URL}/map/assets`,
                    { cache: "no-store" },
                    MAP_ASSET_TIMEOUT_MS
                );
                if (res.ok) {
                    const payload = await res.json();
                    const rows = Array.isArray(payload.assets) ? payload.assets : [];
                    if (rows.length) {
                        const mapped = normalizeMapAssetRows(rows);
                        logMapDiag(
                            "step",
                            `Map: ${mapped.length} assets loaded from database`,
                            mapped.length === rows.length
                                ? `${rows.length} rows returned`
                                : `${rows.length} rows returned, ${rows.length - mapped.length} dropped for bad coordinates`
                        );
                        return mapped;
                    }
                    // Empty 200 means the DB has no rows for the map query. There is
                    // no local fallback data, so return empty and let the caller show
                    // the in-map error + Retry.
                    logMapDiag("fail", "Map: backend returned zero assets", "no assets to plot");
                    return [];
                }
                logMapDiag("fail", "Map: backend rejected the request", `HTTP ${res.status}`);
            } catch (err) {
                const reason =
                    err && err.name === "AbortError"
                        ? `no response within ${MAP_ASSET_TIMEOUT_MS} ms`
                        : String(err && err.message ? err.message : err);
                logMapDiag("fail", "Map: backend unreachable", reason);
            }
            // Backend/MCP still warming up - wait and retry, up to the bounded cap.
            await new Promise((resolve) => setTimeout(resolve, MAP_ASSET_RETRY_MS));
        }
        logMapDiag("error", "Map: giving up after retries", `${MAX_MAP_ASSET_RETRIES} attempts failed; no assets loaded`);
        return [];
    }

    function markerStyleForStatus(status) {
        const s = String(status || "").toLowerCase();
        if (s === "outage" || s === "critical" || s === "error") {
            return { radius: 10, color: "#e53935", weight: 2, fillColor: "#ef5350", fillOpacity: 0.45 };
        }
        if (s === "warning" || s === "degraded" || s === "alert") {
            return { radius: 10, color: "#f59e0b", weight: 2, fillColor: "#fbbf24", fillOpacity: 0.45 };
        }
        return { radius: 9, color: "#22c55e", weight: 2, fillColor: "#4ade80", fillOpacity: 0.4 };
    }

    // ===================================================================
    // 8. Export — clipboard, file, or print
    // ===================================================================
    btnExportClipboard.addEventListener("click", async () => {
        const text = getExportText();
        if (!text) return;

        try {
            await navigator.clipboard.writeText(text);
            showExportStatus("✅ Copied!");
        } catch (err) {
            showError("Failed to copy to clipboard.");
        } finally {
            exportMenu.removeAttribute("open");
        }
    });

    btnExportFile.addEventListener("click", () => {
        const text = getExportText();
        if (!text) return;

        const fileName = createExportFileName();
        const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);

        const downloadLink = document.createElement("a");
        downloadLink.href = url;
        downloadLink.download = fileName;
        downloadLink.click();

        showOutputArtifact(fileName, url);
        showExportStatus("💾 Exported!");
        exportMenu.removeAttribute("open");
    });

    btnExportPrint.addEventListener("click", () => {
        const text = getExportText();
        if (!text) return;

        // Render markdown -> sanitized HTML using the same libs the main UI uses.
        const rawHtml = (typeof marked !== "undefined") ? marked.parse(text) : escapeHtml(text);
        const safeHtml = (typeof DOMPurify !== "undefined") ? DOMPurify.sanitize(rawHtml) : rawHtml;

        const printCss = `
            body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.55;padding:2rem;color:#111827;max-width:48rem;margin:0 auto;}
            h1,h2,h3,h4{margin:1.2em 0 .4em;line-height:1.25;}
            h1{font-size:1.8rem;} h2{font-size:1.4rem;} h3{font-size:1.15rem;}
            p{margin:.5em 0;}
            ul,ol{margin:.4em 0 .8em 1.4em; padding:0;}
            li{margin:.2em 0;}
            li > ul, li > ol{margin:.2em 0 .2em 1.2em;}
            strong{font-weight:600;}
            code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.9em;background:#f3f4f6;padding:.1em .3em;border-radius:3px;}
            pre{background:#f3f4f6;padding:.75rem;border-radius:4px;overflow:auto;}
            pre code{background:transparent;padding:0;}
            blockquote{border-left:3px solid #d1d5db;margin:.6em 0;padding:.2em .8em;color:#374151;}
            table{border-collapse:collapse;margin:.6em 0;} th,td{border:1px solid #d1d5db;padding:.3em .6em;}
            @media print { body { padding: 0.5in; } }
        `;
        const printHtml = `<!doctype html><html><head><meta charset="utf-8"><title>Engage 360 Export</title><style>${printCss}</style></head><body>${safeHtml}<script>window.addEventListener("load", () => { setTimeout(() => window.print(), 150); });<\/script></body></html>`;

        const printBlob = new Blob([printHtml], { type: "text/html;charset=utf-8" });
        const printUrl = URL.createObjectURL(printBlob);
        const printWindow = window.open(printUrl, "_blank");

        if (!printWindow) {
            URL.revokeObjectURL(printUrl);
            showError("Failed to open print window.");
            return;
        }

        setTimeout(() => URL.revokeObjectURL(printUrl), 60000);
        showExportStatus("🖨️ Printed!");
        exportMenu.removeAttribute("open");
    });

    function getExportText() {
        const text = lastRawMarkdown.trim();
        if (!text) {
            showError("No results to export.");
            exportMenu.removeAttribute("open");
            return "";
        }
        return text;
    }

    function createExportFileName() {
        const now = new Date();
        const mm = String(now.getMonth() + 1).padStart(2, "0");
        const dd = String(now.getDate()).padStart(2, "0");
        const customer = extractCustomerName(lastRawMarkdown) || "customer";
        return `${mm}-${dd} ActionPlan ${customer}.md`;
    }

    // Pull the customer name out of the report's title heading. The title is built
    // as "[date] - Customer Plan - [name]" (date and name optional), so the customer
    // name is whatever follows "Customer Plan". Returns "" when no name is present.
    function extractCustomerName(markdown) {
        if (!markdown) return "";

        // First markdown heading line is the report title.
        const headingMatch = markdown.match(/^#{1,6}\s+(.+)$/m);
        if (!headingMatch) return "";

        // Strip emphasis markers (** _ `) and surrounding whitespace.
        const title = headingMatch[1].replace(/[*_`]/g, "").trim();

        const idx = title.search(/customer plan/i);
        if (idx === -1) return "";

        let name = title
            .slice(idx)
            .replace(/customer plan/i, "")
            .replace(/^[\s\-–—]+/, "")
            .trim();

        // Guard against leftover placeholder text.
        if (!name || name.startsWith("[") || /not\s+(provided|stated|specified)/i.test(name)) {
            return "";
        }

        // Remove characters that are invalid in filenames.
        return name.replace(/[\\/:*?"<>|]+/g, "").trim();
    }

    function showOutputArtifact(fileName, url) {
        outputArtifacts.innerHTML = "";

        const artifact = document.createElement("span");
        artifact.className = "output-artifact";

        const label = document.createElement("span");
        label.textContent = "Output file:";

        const link = document.createElement("a");
        link.href = url;
        link.download = fileName;
        link.textContent = fileName;

        artifact.appendChild(label);
        artifact.appendChild(link);
        outputArtifacts.appendChild(artifact);
        outputArtifacts.classList.remove("hidden");
    }

    function showExportStatus(message) {
        const summary = exportMenu.querySelector("summary");
        const original = summary.textContent;
        summary.textContent = message;
        setTimeout(() => { summary.textContent = original; }, 1500);
    }

    function escapeHtml(value) {
        return value
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }


    // ===================================================================
    // Helpers
    // ===================================================================
    function showLoading(visible, labelText = "Analyzing...") {
        if (visible) {
            timerSeconds = 0;
            if (loadingLabel) loadingLabel.textContent = labelText;
            elapsedTimer.textContent = "0s";
            loading.classList.remove("hidden");
            timerInterval = setInterval(() => {
                timerSeconds++;
                elapsedTimer.textContent = timerSeconds + "s";
            }, 1000);
        } else {
            clearInterval(timerInterval);
            timerInterval = null;
            loading.classList.add("hidden");
        }
    }

    function renderMarkdown(markdown) {
        if (!window.marked || !window.DOMPurify) {
            return markdown
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replace(/\n/g, "<br>");
        }

        return window.DOMPurify.sanitize(window.marked.parse(markdown));
    }

    // Wrap each "#### Detail" heading (rendered as <h4>Detail</h4>) plus everything
    // beneath it — up to the next section heading (h1–h4) — inside a native
    // <details>/<summary> so it becomes a collapsible block on screen.
    // Returns the list of created <details> elements.
    function wrapDetailSections(container) {
        const headings = Array.from(container.querySelectorAll("h4"));
        const created = [];

        for (const heading of headings) {
            if (heading.textContent.trim().toLowerCase() !== "detail") continue;

            const details = document.createElement("details");
            details.className = "detail-collapsible";

            const summary = document.createElement("summary");
            summary.textContent = "Detail";
            details.appendChild(summary);

            // Gather the nodes that follow this heading until the next section
            // boundary (any h1–h4). h5/h6 subsections stay inside the block.
            const collected = [];
            let node = heading.nextSibling;
            while (node) {
                if (node.nodeType === Node.ELEMENT_NODE &&
                    ["H1", "H2", "H3", "H4"].includes(node.tagName)) {
                    break;
                }
                collected.push(node);
                node = node.nextSibling;
            }

            // Swap the heading for the <details> block, then move the collected
            // nodes inside it (appendChild moves existing nodes).
            heading.replaceWith(details);
            for (const n of collected) details.appendChild(n);
            created.push(details);
        }

        return created;
    }

    function hideResults() {
        resultsPlaceholder.classList.remove("hidden");
        outputArtifacts.classList.add("hidden");
        outputArtifacts.innerHTML = "";
        resultsContent.classList.add("hidden");
        resultsContent.innerHTML = "";
        assetResults.classList.add("hidden");
        assetResults.innerHTML = "";
        resultsMeta.classList.add("hidden");
        resultsMeta.innerHTML = "";
    }

    function showError(message) {
        resultsPlaceholder.classList.add("hidden");
        resultsContent.innerHTML = "";
        resultsContent.classList.remove("hidden");

        const errorDiv = document.createElement("div");
        errorDiv.className = "result-error";
        errorDiv.textContent = message;
        resultsContent.appendChild(errorDiv);
    }


    // ===================================================================
    // Streaming — POST /chat/stream, render events live
    // ===================================================================
    async function streamChat(userPrompt) {
        addInstrumentationRow("intent", "User prompt", userPrompt);

        const res = await fetch(`${API_BASE_URL}/chat/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: userPrompt,
                conversation_id: conversationId,
            }),
        });

        if (!res.ok) {
            const errBody = await res.text().catch(() => "");
            throw new Error(`Request failed (${res.status}): ${errBody}`);
        }

        // Not every browser exposes an incrementally readable body on a fetch
        // response. When it is missing, read the whole payload and replay the
        // events at once so the answer still lands.
        if (!res.body || typeof res.body.getReader !== "function") {
            addInstrumentationRow("intent", "Streaming unavailable", "This browser cannot read the response incrementally; showing the completed run.");
            const whole = await res.text();
            for (const line of whole.split("\n")) {
                const trimmed = line.trim();
                if (trimmed) dispatchStreamLine(trimmed);
            }
            return;
        }

        // Read the NDJSON body incrementally: one JSON event per line.
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            let newlineIdx;
            while ((newlineIdx = buffer.indexOf("\n")) >= 0) {
                const line = buffer.slice(0, newlineIdx).trim();
                buffer = buffer.slice(newlineIdx + 1);
                if (line) dispatchStreamLine(line);
            }
        }
        // Flush any trailing partial line.
        const tail = buffer.trim();
        if (tail) dispatchStreamLine(tail);
    }

    function dispatchStreamLine(line) {
        let event;
        try {
            event = JSON.parse(line);
        } catch {
            return; // ignore malformed / keep-alive lines
        }
        handleStreamEvent(event);
    }

    function handleStreamEvent(event) {
        const p = event.payload || {};
        if (event.type === "intent") {
            const pct = Math.round((p.confidence || 0) * 100);
            const kind = p.intent === "ERROR" ? "error" : "intent";
            addInstrumentationRow(
                kind,
                `Intent: ${p.intent} (${pct}%)`,
                formatIntentDetail(p),
            );
        } else if (event.type === "plan") {
            const steps = Array.isArray(p.steps) ? p.steps : [];
            addInstrumentationRow(
                "plan",
                `Plan: ${steps.length} agent${steps.length === 1 ? "" : "s"}`,
                steps.map((s, i) => {
                    const deps = Array.isArray(s.depends_on) ? s.depends_on : [];
                    const after = deps.length ? ` \u2190 after ${deps.join(", ")}` : "";
                    return `${i + 1}. ${s.agent} (${s.id})${after}`;
                }),
            );
        } else if (event.type === "step") {
            const kind = p.success === false ? "fail" : "step";
            const agent = String(p.agent || "");
            const agentLabel = agent ? agent.charAt(0).toUpperCase() + agent.slice(1) : "Unknown";
            let title;
            if (p.action === "decide") {
                title = "Planned Next Step";
            } else if (p.action === "dispatch") {
                title = `Now Calling ${agentLabel} Agent (please wait...)`;
            } else {
                title = `Agent: ${agentLabel} — ${p.action}`;
            }
            addInstrumentationRow(
                kind,
                title,
                formatStepDetail(p),
            );
        } else if (event.type === "final") {
            const errorDetail = p.artifacts && typeof p.artifacts === "object" ? p.artifacts.error : "";
            const assets = p.artifacts && typeof p.artifacts === "object" ? p.artifacts.assets : null;
            displayResults({ content: p.answer, reasoning: p.reasoning, errorDetail, assets });

            // Final row is a compact summary; detailed per-agent data already arrived as step rows.
            const confidencePct = Math.round((Number(p.confidence) || 0) * 100);
            const agents = Array.isArray(p.agents) && p.agents.length
                ? p.agents.join(", ")
                : "none";
            const stepCount = Array.isArray(p.steps) ? p.steps.length : 0;
            const finalDetail = [
                `Intent: ${p.intent || "UNKNOWN"}`,
                `Confidence: ${confidencePct}%`,
                `Agents: ${agents}`,
                `Steps: ${stepCount}`,
                `Answer: ${p.answer || ""}`,
            ];
            addInstrumentationRow("final", "Final Summary", finalDetail);
        } else if (event.type === "error") {
            addInstrumentationRow("error", "Error", p.message || "Processing failed.");
            showError(p.message || "Processing failed.");
        }
    }

    function clearInstrumentation() {
        instrumentationSteps.innerHTML = "";
        instrumentation.classList.add("hidden");
    }

    function addInstrumentationRow(kind, title, detail) {
        if (!executionTraceUserHidden) instrumentation.classList.remove("hidden");

        const row = document.createElement("div");
        row.className = `instrumentation-step step-${kind}`;

        const titleEl = document.createElement("div");
        titleEl.className = "instrumentation-step-title";
        titleEl.textContent = title;
        row.appendChild(titleEl);

        if (detail) {
            const detailEl = document.createElement("div");
            detailEl.className = "instrumentation-step-detail";
            if (Array.isArray(detail)) {
                for (const line of detail) {
                    if (line.startsWith("SQL: ")) {
                        const details = document.createElement("details");
                        details.className = "trace-line trace-sql";
                        const summary = document.createElement("summary");
                        summary.textContent = "SQL";
                        const body = document.createElement("pre");
                        body.className = "trace-sql-body";
                        body.textContent = line.slice(5); // drop "SQL: "
                        details.appendChild(summary);
                        details.appendChild(body);
                        detailEl.appendChild(details);
                    } else {
                        const lineEl = document.createElement("div");
                        lineEl.className = `trace-line ${traceLineClass(line)}`;
                        lineEl.textContent = line;
                        detailEl.appendChild(lineEl);
                    }
                }
            } else {
                detailEl.textContent = detail;
            }
            row.appendChild(detailEl);
        }

        instrumentationSteps.appendChild(row);
        instrumentationSteps.scrollTop = instrumentationSteps.scrollHeight;
    }

    function formatIntentDetail(payload) {
        const parts = [];
        if (payload.reasoning_pattern) {
            parts.push(`Reasoning pattern: ${payload.reasoning_pattern}`);
        }
        parts.push(payload.continues_previous ? "Continuing Conversation" : "New Conversation");
        if (payload.reasoning) {
            parts.push(payload.reasoning);
        }
        parts.push(`Entities: ${formatEntities(payload.entities)}`);
        if (payload.error) {
            parts.push(`Error: ${payload.error}`);
        }
        return parts;
    }

    function formatEntities(entities) {
        if (!entities || typeof entities !== "object") {
            return "(none)";
        }
        const visible = Object.entries(entities)
            .filter(([_, value]) => value !== null && value !== undefined && value !== "")
            .map(([key, value]) => `${key}=${value}`);
        return visible.length ? visible.join(", ") : "(none)";
    }

    function formatStepDetail(stepPayload) {
        if (stepPayload && stepPayload.action === "dispatch") {
            return [" "];
        }
        const detail = (stepPayload && stepPayload.detail && typeof stepPayload.detail === "object")
            ? stepPayload.detail
            : null;
        if (!detail) {
            return [];
        }
        if (stepPayload.action === "decide") {
            const lines = [];
            if (detail.next_agent) {
                const agentName = String(detail.next_agent);
                lines.push(agentName === "stop"
                    ? "Stopping - request already satisfied"
                    : `Calling ${agentName.charAt(0).toUpperCase() + agentName.slice(1)} agent`);
            }
            if (detail.confidence) {
                lines.push(`Confidence: ${detail.confidence}`);
            }
            if (detail.reasoning) {
                lines.push(`Reasoning: ${detail.reasoning}`);
            }
            return lines;
        }
        if (!("tool" in detail)) {
            // Non-agent trace step (dispatch) - render whatever keys it carries.
            return Object.entries(detail).map(([key, value]) => `${key}: ${value}`);
        }
        const question = detail.question || "(not provided)";
        const tool = detail.tool || "ask";
        const reasoning = detail.reasoning || "(not provided)";
        const rows = detail.rows || "(unknown)";
        const lines = [
            `Question: ${question}`,
            `Tool: ${tool}`,
        ];
        if (detail.sql) {
            lines.push(`SQL: ${detail.sql}`);
        }
        lines.push(`Reasoning: ${reasoning}`);
        if (detail.error) {
            lines.push(`Error: ${detail.error}`);
        } else {
            lines.push(`Rows: ${rows}`);
        }
        return lines;
    }

    function traceLineClass(line) {
        const text = String(line || "").toLowerCase();
        if (text.startsWith("agent:")) return "trace-line-agent";
        if (text.startsWith("question:")) return "trace-line-question";
        if (text.startsWith("tool:")) return "trace-line-tool";
        if (text.startsWith("sql:")) return "trace-line-sql";
        if (text.startsWith("reasoning:")) return "trace-line-reasoning";
        if (text.startsWith("rows:")) return "trace-line-rows";
        if (text.startsWith("error:")) return "trace-line-error";
        if (text.startsWith("entities:")) return "trace-line-entities";
        return "trace-line-default";
    }

});
