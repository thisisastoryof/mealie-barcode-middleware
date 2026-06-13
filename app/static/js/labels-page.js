(function () {
    "use strict";

    const STORAGE_KEY = "label-queue";
    const searchInput = document.getElementById("label-item-search");
    const searchResults = document.getElementById("label-search-results");
    const freeTextInput = document.getElementById("label-free-text");
    const addFreeBtn = document.getElementById("label-add-free");
    const queueContainer = document.getElementById("label-queue");
    const queueEmpty = document.getElementById("label-queue-empty");
    const labelCount = document.getElementById("label-count");
    const printBtn = document.getElementById("label-print");
    const clearBtn = document.getElementById("label-clear");
    const sizeRange = document.getElementById("label-size");
    const sizeValue = document.getElementById("label-size-value");
    const gapRange = document.getElementById("label-gap");
    const gapValue = document.getElementById("label-gap-value");
    const marginRange = document.getElementById("label-margin");
    const marginValue = document.getElementById("label-margin-value");
    const pageFormatSelect = document.getElementById("label-page-format");
    const fontSizeSelect = document.getElementById("label-font-size");
    const showTextCheck = document.getElementById("label-show-text");
    const printArea = document.getElementById("print-area");
    const printGrid = document.getElementById("print-grid");
    const previewPage = document.getElementById("preview-page");
    const previewGrid = document.getElementById("preview-grid");
    const previewSummary = document.getElementById("preview-summary");

    // --- Range slider live value display ---
    sizeRange.addEventListener("input", () => { sizeValue.textContent = sizeRange.value; updatePreview(); });
    gapRange.addEventListener("input", () => { gapValue.textContent = gapRange.value; updatePreview(); });
    marginRange.addEventListener("input", () => { marginValue.textContent = marginRange.value; updatePreview(); });
    pageFormatSelect.addEventListener("change", updatePreview);
    fontSizeSelect.addEventListener("change", updatePreview);
    showTextCheck.addEventListener("change", updatePreview);

    // --- Queue Management (localStorage) ---
    function getQueue() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
        } catch { return []; }
    }

    function saveQueue(queue) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
        renderQueue();
        updatePreview();
    }

    function addToQueue(text, itemId, itemName) {
        const queue = getQueue();
        // Avoid exact duplicates
        if (queue.some(l => l.text === text)) return;
        queue.push({ text, itemId: itemId || null, itemName: itemName || text, qty: 1, addedAt: Date.now() });
        saveQueue(queue);
    }

    function removeFromQueue(text) {
        const queue = getQueue().filter(l => l.text !== text);
        saveQueue(queue);
    }

    function updateQty(text, delta) {
        const queue = getQueue();
        const item = queue.find(l => l.text === text);
        if (item) {
            item.qty = Math.max(1, (item.qty || 1) + delta);
            saveQueue(queue);
        }
    }

    // --- Render Queue ---
    function renderQueue() {
        const queue = getQueue();
        const totalLabels = queue.reduce((sum, l) => sum + (l.qty || 1), 0);
        labelCount.textContent = `(${totalLabels} label${totalLabels !== 1 ? "s" : ""})`;
        printBtn.disabled = queue.length === 0;
        clearBtn.disabled = queue.length === 0;

        if (queue.length === 0) {
            queueEmpty.classList.remove("d-none");
            queueContainer.innerHTML = "";
            return;
        }
        queueEmpty.classList.add("d-none");
        queueContainer.innerHTML = queue.map(label => {
            const qty = label.qty || 1;
            const statusHtml = label.itemId
                ? '<span class="status-dot status-dot-animated bg-green me-1"></span><span class="small text-secondary">Linked</span>'
                : '<span class="status-dot bg-azure me-1"></span><span class="small text-secondary">Generic</span>';
            return `
            <div class="col-6 col-sm-4 col-md-3">
                <div class="card card-sm label-card${label.itemId ? ' cursor-pointer' : ''}"${label.itemId ? ` data-href="/items/${encodeURIComponent(label.itemId)}"` : ''}>
                    <button type="button" class="btn btn-icon btn-ghost-danger label-remove" data-text="${escapeAttr(label.text)}" title="Remove">
                        <i class="ti ti-x icon"></i>
                    </button>
                    <div class="card-body text-center p-2">
                        <img src="/labels/qr.svg?text=${encodeURIComponent(label.text)}" alt="QR" class="label-qr-preview mb-1">
                        <div class="text-truncate small">${escapeHtml(label.itemName || label.text)}</div>
                        <div class="mt-1 d-flex align-items-center justify-content-center">${statusHtml}</div>
                        <div class="mt-1 d-flex align-items-center justify-content-center gap-1">
                            <button type="button" class="btn btn-icon btn-sm btn-ghost-secondary label-qty-minus" data-text="${escapeAttr(label.text)}"><i class="ti ti-minus icon"></i></button>
                            <span class="small fw-bold label-qty-display">${qty}</span>
                            <button type="button" class="btn btn-icon btn-sm btn-ghost-secondary label-qty-plus" data-text="${escapeAttr(label.text)}"><i class="ti ti-plus icon"></i></button>
                        </div>
                    </div>
                </div>
            </div>`;
        }).join("");

        // Attach remove handlers
        queueContainer.querySelectorAll(".label-remove").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                e.preventDefault();
                removeFromQueue(btn.dataset.text);
            });
        });
        // Attach qty handlers
        queueContainer.querySelectorAll(".label-qty-minus").forEach(btn => {
            btn.addEventListener("click", (e) => { e.stopPropagation(); updateQty(btn.dataset.text, -1); });
        });
        queueContainer.querySelectorAll(".label-qty-plus").forEach(btn => {
            btn.addEventListener("click", (e) => { e.stopPropagation(); updateQty(btn.dataset.text, 1); });
        });
        // Attach card click → navigate to item
        queueContainer.querySelectorAll(".label-card[data-href]").forEach(card => {
            card.addEventListener("click", () => {
                window.location.href = card.dataset.href;
            });
        });
    }

    // --- Item Search / Autocomplete ---
    let searchTimeout;
    searchInput.addEventListener("input", () => {
        clearTimeout(searchTimeout);
        const q = searchInput.value.trim();
        if (q.length < 2) { searchResults.classList.remove("show"); return; }
        searchTimeout = setTimeout(() => fetchSearch(q), 250);
    });

    async function fetchSearch(q) {
        const res = await fetch(`/labels/search?q=${encodeURIComponent(q)}`);
        if (!res.ok) return;
        const items = await res.json();
        if (items.length === 0) {
            searchResults.innerHTML = '<div class="dropdown-item text-secondary">No items found</div>';
        } else {
            searchResults.innerHTML = items.map(item => `
                <a href="#" class="dropdown-item search-result-item" data-id="${escapeAttr(item.id)}" data-name="${escapeAttr(item.name)}">
                    ${escapeHtml(item.name)}
                    <small class="text-secondary ms-1">${escapeHtml(item.source || "")}</small>
                </a>
            `).join("");
        }
        searchResults.classList.add("show");

        searchResults.querySelectorAll(".search-result-item").forEach(el => {
            el.addEventListener("click", (e) => {
                e.preventDefault();
                selectItem(el.dataset.id, el.dataset.name);
            });
        });
    }

    function selectItem(itemId, itemName) {
        searchResults.classList.remove("show");
        searchInput.value = "";
        addToQueue(itemName, itemId, itemName);
    }

    // Close dropdown on click outside
    document.addEventListener("click", (e) => {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.remove("show");
        }
    });

    // --- Free Text Add ---
    function addFreeText() {
        const text = freeTextInput.value.trim();
        if (!text) return;
        freeTextInput.value = "";
        // Check for fuzzy matches (read-only) before adding
        fuzzyCheckAndAdd(text);
    }

    addFreeBtn.addEventListener("click", addFreeText);
    freeTextInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); addFreeText(); }
    });

    // --- Fuzzy Check (read-only, no mutations) ---
    async function fuzzyCheckAndAdd(text) {
        try {
            const res = await fetch(`/labels/fuzzy?q=${encodeURIComponent(text)}`);
            const data = await res.json();

            if (data.candidates && data.candidates.length > 0) {
                showFuzzyModal(text, data.candidates);
            } else {
                addToQueue(text, null, text);
            }
        } catch (err) {
            console.error("Fuzzy check failed:", err);
            addToQueue(text, null, text);
        }
    }

    // --- Fuzzy Match Modal ---
    function showFuzzyModal(text, candidates) {
        document.getElementById("fuzzy-text").textContent = text;
        const container = document.getElementById("fuzzy-candidates");
        container.innerHTML = candidates.map(c => `
            <a href="#" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center fuzzy-pick" data-id="${escapeAttr(c.id)}" data-name="${escapeAttr(c.name)}">
                ${escapeHtml(c.name)}
                <span class="text-secondary small">${c.score}%</span>
            </a>
        `).join("");

        container.querySelectorAll(".fuzzy-pick").forEach(el => {
            el.addEventListener("click", (e) => {
                e.preventDefault();
                addToQueue(text, el.dataset.id, el.dataset.name);
                fuzzyModalEl.querySelector("[data-bs-dismiss='modal']").click();
            });
        });

        // Show modal — also allow skip (just adds without mapping)
        const fuzzyModalEl = document.getElementById("modal-fuzzy");
        fuzzyModalEl.addEventListener("hidden.bs.modal", function handler() {
            fuzzyModalEl.removeEventListener("hidden.bs.modal", handler);
            if (!getQueue().some(l => l.text === text)) {
                addToQueue(text, null, text);
            }
        });
        document.getElementById("fuzzy-modal-trigger").click();
    }

    // --- Register & Print ---
    printBtn.addEventListener("click", async () => {
        const queue = getQueue();
        if (queue.length === 0) return;

        // Batch-register all labels
        printBtn.disabled = true;
        printBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Registering…';
        try {
            const payload = queue.map(l => ({ text: l.text, item_id: l.itemId || null }));
            await fetch("/labels/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ labels: payload }),
            });
        } catch (err) {
            console.error("Batch registration failed:", err);
        }
        printBtn.innerHTML = '<i class="ti ti-printer icon"></i> Register &amp; Print';
        printBtn.disabled = false;

        const sizeMm = sizeRange.value + "mm";
        const gapMm = gapRange.value + "mm";
        const marginMm = marginRange.value + "mm";
        const fontSize = fontSizeSelect.value + "pt";
        const showText = showTextCheck.checked;
        const pageFormat = pageFormatSelect.value;

        // Set CSS variables for print
        printGrid.style.setProperty("--label-size", sizeMm);
        printGrid.style.setProperty("--label-gap", gapMm);
        printGrid.style.setProperty("--label-margin", marginMm);
        printGrid.style.setProperty("--label-font-size", fontSize);

        // Inject @page rule for page format
        let pageStyle = document.getElementById("label-page-style");
        if (!pageStyle) {
            pageStyle = document.createElement("style");
            pageStyle.id = "label-page-style";
            document.head.appendChild(pageStyle);
        }
        if (pageFormat === "auto") {
            pageStyle.textContent = "";
        } else {
            pageStyle.textContent = `@page { size: ${pageFormat}; }`;
        }

        // Build grid cells — repeat per qty
        printGrid.innerHTML = queue.map(label => {
            const qty = label.qty || 1;
            const cell = `<div class="label-cell">
                <img src="/labels/qr.svg?text=${encodeURIComponent(label.text)}" alt="${escapeAttr(label.text)}">
                ${showText ? `<span class="label-text">${escapeHtml(label.itemName || label.text)}</span>` : ""}
            </div>`;
            return cell.repeat(qty);
        }).join("");

        // Small delay to let images load, then print
        setTimeout(() => window.print(), 300);
    });

    // --- Preview ---
    function updatePreview() {
        const queue = getQueue();
        const sizeMm = parseInt(sizeRange.value);
        const gapMm = parseInt(gapRange.value);
        const marginMm = parseInt(marginRange.value);
        const showText = showTextCheck.checked;
        const pageFormat = pageFormatSelect.value;

        // Page dimensions in mm
        let pageW = 210, pageH = 297; // A4 default
        if (pageFormat === "Letter") { pageW = 216; pageH = 279; }

        // Scale: fit the preview container width
        // The preview-page element has a fixed aspect-ratio via CSS
        // We compute a px-per-mm scale based on the container width
        const containerWidth = previewPage.clientWidth || 400;
        const scale = containerWidth / pageW;

        // Set landscape class
        previewPage.classList.remove("landscape");

        // Compute columns that fit
        const printableW = pageW - 2 * marginMm;
        const cols = Math.max(1, Math.floor((printableW + gapMm) / (sizeMm + gapMm)));

        // Set CSS variables for preview (in px)
        const previewSize = Math.round(sizeMm * scale);
        const previewGap = Math.round(gapMm * scale);
        const previewMargin = Math.round(marginMm * scale);
        const previewFontSize = Math.round(parseInt(fontSizeSelect.value) * scale * 0.4);

        previewGrid.style.setProperty("--preview-size", previewSize + "px");
        previewGrid.style.setProperty("--preview-gap", previewGap + "px");
        previewGrid.style.setProperty("--preview-margin", previewMargin + "px");
        previewGrid.style.setProperty("--preview-font-size", Math.max(5, previewFontSize) + "px");

        // Compute how many rows fit
        const printableH = pageH - 2 * marginMm;
        const cellH = sizeMm + (showText ? 3 : 0); // rough text height ~3mm
        const rows = Math.max(1, Math.floor((printableH + gapMm) / (cellH + gapMm)));
        const perPage = cols * rows;

        // Total labels (with copies)
        const totalLabels = queue.reduce((sum, l) => sum + (l.qty || 1), 0);
        const pages = Math.max(1, Math.ceil(totalLabels / perPage));

        // Build cells
        if (totalLabels === 0) {
            previewGrid.innerHTML = '<div class="label-preview-empty text-center text-secondary py-4">Add labels to see preview</div>';
            previewSummary.textContent = "";
            return;
        }

        let cells = "";
        queue.forEach(label => {
            const qty = label.qty || 1;
            const cell = `<div class="label-preview-cell">
                <img src="/labels/qr.svg?text=${encodeURIComponent(label.text)}" alt="">
                ${showText ? `<span class="label-preview-text">${escapeHtml(label.itemName || label.text)}</span>` : ""}
            </div>`;
            cells += cell.repeat(qty);
        });
        previewGrid.innerHTML = cells;

        // Summary
        previewSummary.textContent = `${cols} columns × ${rows} rows — ${totalLabels} label${totalLabels !== 1 ? "s" : ""}${pages > 1 ? ` (${pages} pages)` : ""}`;
    }

    // Update preview when switching to preview tab
    document.querySelector('[href="#tab-preview"]').addEventListener("shown.bs.tab", updatePreview);

    // --- Clear All ---
    clearBtn.addEventListener("click", () => {
        if (confirm("Remove all labels from the queue?")) {
            localStorage.removeItem(STORAGE_KEY);
            renderQueue();
            updatePreview();
        }
    });

    // --- Helpers ---
    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function escapeAttr(str) {
        return str.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // --- Init ---
    renderQueue();
    updatePreview();
})();
