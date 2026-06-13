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
    const formatSelect = document.getElementById("label-format");
    const sizeRange = document.getElementById("label-size");
    const sizeValue = document.getElementById("label-size-value");
    const gapRange = document.getElementById("label-gap");
    const gapValue = document.getElementById("label-gap-value");
    const paddingRange = document.getElementById("label-padding");
    const paddingValue = document.getElementById("label-padding-value");
    const marginRange = document.getElementById("label-margin");
    const marginValue = document.getElementById("label-margin-value");
    const pageFormatSelect = document.getElementById("label-page-format");
    const fontSizeSelect = document.getElementById("label-font-size");
    const showTextCheck = document.getElementById("label-show-text");
    const showBorderCheck = document.getElementById("label-show-border");
    const printArea = document.getElementById("print-area");
    const printGrid = document.getElementById("print-grid");
    const previewPage = document.getElementById("preview-page");
    const previewGrid = document.getElementById("preview-grid");
    const previewSummary = document.getElementById("preview-summary");

    // Format ratio lookup: width:height → multiplier for height = width * ratio
    const FORMAT_RATIOS = { "1:1": 1, "3:2": 2/3, "2:1": 1/2, "2:3": 3/2 };
    function getHeightMm(widthMm) {
        const ratio = FORMAT_RATIOS[formatSelect.value] || 1;
        return Math.round(widthMm * ratio);
    }
    function isLandscape() {
        // Only use side-by-side layout for very wide ratios (2:1 or wider)
        const ratio = FORMAT_RATIOS[formatSelect.value] || 1;
        return ratio <= 0.5;
    }

    // --- Range slider live value display ---
    sizeRange.addEventListener("input", () => { sizeValue.textContent = sizeRange.value; updatePreview(); });
    gapRange.addEventListener("input", () => { gapValue.textContent = gapRange.value; updatePreview(); });
    paddingRange.addEventListener("input", () => { paddingValue.textContent = paddingRange.value; updatePreview(); });
    marginRange.addEventListener("input", () => { marginValue.textContent = marginRange.value; updatePreview(); });
    formatSelect.addEventListener("change", updatePreview);
    pageFormatSelect.addEventListener("change", updatePreview);
    fontSizeSelect.addEventListener("change", updatePreview);
    showTextCheck.addEventListener("change", updatePreview);
    showBorderCheck.addEventListener("change", updatePreview);

    // --- Preset buttons ---
    document.querySelectorAll(".label-preset").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".label-preset").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            if (btn.dataset.format) formatSelect.value = btn.dataset.format;
            sizeRange.value = btn.dataset.size;
            sizeValue.textContent = btn.dataset.size;
            gapRange.value = btn.dataset.gap;
            gapValue.textContent = btn.dataset.gap;
            if (btn.dataset.padding) {
                paddingRange.value = btn.dataset.padding;
                paddingValue.textContent = btn.dataset.padding;
            }
            marginRange.value = btn.dataset.margin;
            marginValue.textContent = btn.dataset.margin;
            fontSizeSelect.value = btn.dataset.font;
            updatePreview();
        });
    });
    // Deactivate preset active state when user manually adjusts
    [sizeRange, gapRange, paddingRange, marginRange].forEach(el => {
        el.addEventListener("input", () => {
            document.querySelectorAll(".label-preset").forEach(b => b.classList.remove("active"));
        });
    });
    formatSelect.addEventListener("change", () => {
        document.querySelectorAll(".label-preset").forEach(b => b.classList.remove("active"));
    });

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
                        <div class="mt-1 d-flex align-items-center justify-content-center">
                            <div class="label-qty">
                                <button type="button" class="label-qty-minus" data-text="${escapeAttr(label.text)}">−</button>
                                <span>${qty}</span>
                                <button type="button" class="label-qty-plus" data-text="${escapeAttr(label.text)}">+</button>
                            </div>
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
        const heightMm = getHeightMm(parseInt(sizeRange.value)) + "mm";
        const gapMm = gapRange.value + "mm";
        const fontSize = fontSizeSelect.value + "pt";
        const showText = showTextCheck.checked;
        const pageFormat = pageFormatSelect.value;
        const landscape = isLandscape();

        // Set CSS variables for print
        printGrid.style.setProperty("--label-width", sizeMm);
        printGrid.style.setProperty("--label-height", heightMm);
        printGrid.style.setProperty("--label-gap", gapMm);
        printGrid.style.setProperty("--label-padding", paddingRange.value + "mm");
        printGrid.style.setProperty("--label-font-size", fontSize);

        // Cap image size for consistent QR sizing in print
        const paddingMmVal = parseFloat(paddingRange.value);
        if (showText && !landscape) {
            const sizeVal = getHeightMm(parseInt(sizeRange.value));
            const fontPt = parseInt(fontSizeSelect.value);
            const fontMm = fontPt * 0.353; // 1pt ≈ 0.353mm
            const gapBetween = paddingMmVal / 2; // QR-to-text gap = half padding
            const textReserveMm = 2.4 * fontMm + gapBetween;
            const imgMaxMm = sizeVal - 2 * paddingMmVal - textReserveMm;
            printGrid.style.setProperty("--label-img-max", Math.max(0, imgMaxMm.toFixed(1)) + "mm");
        } else if (landscape && showText) {
            const hVal = getHeightMm(parseInt(sizeRange.value));
            const imgMaxMm = hVal - 2 * paddingMmVal;
            printGrid.style.setProperty("--label-img-max", Math.max(0, imgMaxMm.toFixed(1)) + "mm");
        } else {
            printGrid.style.removeProperty("--label-img-max");
        }

        // Inject @page rule for page format and margin
        let pageStyle = document.getElementById("label-page-style");
        if (!pageStyle) {
            pageStyle = document.createElement("style");
            pageStyle.id = "label-page-style";
            document.head.appendChild(pageStyle);
        }
        const pageMargin = marginRange.value + "mm";
        if (pageFormat === "auto") {
            pageStyle.textContent = `@page { margin: ${pageMargin}; }`;
        } else {
            pageStyle.textContent = `@page { size: ${pageFormat}; margin: ${pageMargin}; }`;
        }

        // Build grid cells — repeat per qty
        const showBorder = showBorderCheck.checked;
        const layoutClass = landscape ? " landscape" : "";
        printGrid.innerHTML = queue.map(label => {
            const qty = label.qty || 1;
            const cell = `<div class="label-cell${showBorder ? ' has-border' : ''}${layoutClass}">
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
        const widthMm = parseInt(sizeRange.value);
        const heightMm = getHeightMm(widthMm);
        const gapMm = parseInt(gapRange.value);
        const marginMm = parseInt(marginRange.value);
        const showText = showTextCheck.checked;
        const pageFormat = pageFormatSelect.value;
        const landscape = isLandscape();

        // Page dimensions in mm
        let pageW = 210, pageH = 297; // A4 default
        if (pageFormat === "Letter") { pageW = 216; pageH = 279; }

        // Scale: fit the preview container width
        const containerWidth = previewPage.clientWidth || 400;
        const scale = containerWidth / pageW;

        // Set landscape class on page
        previewPage.classList.remove("landscape");

        // Compute columns and rows that fit
        const printableW = pageW - 2 * marginMm;
        const printableH = pageH - 2 * marginMm;
        const cols = Math.max(1, Math.floor((printableW + gapMm) / (widthMm + gapMm)));
        const rows = Math.max(1, Math.floor((printableH + gapMm) / (heightMm + gapMm)));
        const perPage = cols * rows;

        // Set CSS variables for preview (in px)
        const previewWidth = Math.round(widthMm * scale);
        const previewHeight = Math.round(heightMm * scale);
        const previewGap = Math.round(gapMm * scale);
        const previewMargin = Math.round(marginMm * scale);
        const previewFontSize = Math.round(parseInt(fontSizeSelect.value) * scale * 0.4);

        previewGrid.style.setProperty("--preview-width", previewWidth + "px");
        previewGrid.style.setProperty("--preview-height", previewHeight + "px");
        previewGrid.style.setProperty("--preview-gap", previewGap + "px");
        previewGrid.style.setProperty("--preview-margin", previewMargin + "px");
        previewGrid.style.setProperty("--preview-font-size", Math.max(5, previewFontSize) + "px");

        // Padding in px (from mm slider, scaled)
        const paddingMmVal = parseFloat(paddingRange.value);
        const previewPadding = Math.max(2, Math.round(paddingMmVal * scale));
        previewGrid.style.setProperty("--preview-padding", previewPadding + "px");

        // Cap image size for consistent QR sizing
        if (showText && !landscape) {
            const actualFontSize = Math.max(5, previewFontSize);
            const gapBetween = previewPadding / 2; // QR-to-text gap = half padding
            const textReserve = 2.4 * actualFontSize + gapBetween;
            const imgMax = previewHeight - 2 * previewPadding - textReserve;
            previewGrid.style.setProperty("--preview-img-max", Math.max(0, Math.round(imgMax)) + "px");
        } else if (landscape && showText) {
            const imgMax = previewHeight - 2 * previewPadding;
            previewGrid.style.setProperty("--preview-img-max", Math.max(0, Math.round(imgMax)) + "px");
        } else {
            previewGrid.style.removeProperty("--preview-img-max");
        }

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
        const borderClass = showBorderCheck.checked ? " has-border" : "";
        const layoutClass = landscape ? " landscape" : "";
        queue.forEach(label => {
            const qty = label.qty || 1;
            const cell = `<div class="label-preview-cell${borderClass}${layoutClass}">
                <img src="/labels/qr.svg?text=${encodeURIComponent(label.text)}" alt="">
                ${showText ? `<span class="label-preview-text">${escapeHtml(label.itemName || label.text)}</span>` : ""}
            </div>`;
            cells += cell.repeat(qty);
        });
        previewGrid.innerHTML = cells;

        // Summary
        previewSummary.textContent = `${cols} × ${rows} — ${totalLabels} label${totalLabels !== 1 ? "s" : ""} (${widthMm}×${heightMm}mm)${pages > 1 ? ` — ${pages} pages` : ""}`;
    }

    // Update preview when switching to preview tab
    document.querySelector('[href="#tab-preview"]').addEventListener("shown.bs.tab", updatePreview);

    // --- Clear All ---
    clearBtn.addEventListener("click", () => {
        window.showConfirm("Remove all labels from the queue?", "", () => {
            localStorage.removeItem(STORAGE_KEY);
            renderQueue();
            updatePreview();
        }, "Clear");
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
