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
    const sizeSelect = document.getElementById("label-size");
    const columnsSelect = document.getElementById("label-columns");
    const showTextCheck = document.getElementById("label-show-text");
    const printArea = document.getElementById("print-area");
    const printGrid = document.getElementById("print-grid");

    // --- Queue Management (localStorage) ---
    function getQueue() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
        } catch { return []; }
    }

    function saveQueue(queue) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
        renderQueue();
    }

    function addToQueue(text, itemId, itemName) {
        const queue = getQueue();
        // Avoid exact duplicates
        if (queue.some(l => l.text === text)) return;
        queue.push({ text, itemId: itemId || null, itemName: itemName || text, addedAt: Date.now() });
        saveQueue(queue);
    }

    function removeFromQueue(text) {
        const queue = getQueue().filter(l => l.text !== text);
        saveQueue(queue);
    }

    // --- Render Queue ---
    function renderQueue() {
        const queue = getQueue();
        labelCount.textContent = `(${queue.length} label${queue.length !== 1 ? "s" : ""})`;
        printBtn.disabled = queue.length === 0;
        clearBtn.disabled = queue.length === 0;

        if (queue.length === 0) {
            queueEmpty.classList.remove("d-none");
            queueContainer.innerHTML = "";
            return;
        }
        queueEmpty.classList.add("d-none");
        queueContainer.innerHTML = queue.map(label => `
            <div class="col-6 col-sm-4 col-md-3">
                <div class="card card-sm">
                    <div class="card-body text-center p-2">
                        <img src="/labels/qr.svg?text=${encodeURIComponent(label.text)}" alt="QR" class="label-qr-preview mb-1">
                        <div class="text-truncate small">${escapeHtml(label.itemName || label.text)}</div>
                        ${label.itemId ? '<span class="badge bg-green-lt">Mapped</span>' : '<span class="badge bg-azure-lt">Generic</span>'}
                        <button class="btn btn-icon btn-ghost-danger mt-1 label-remove" data-text="${escapeAttr(label.text)}" title="Remove">
                            <i class="ti ti-x icon"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join("");

        // Attach remove handlers
        queueContainer.querySelectorAll(".label-remove").forEach(btn => {
            btn.addEventListener("click", () => removeFromQueue(btn.dataset.text));
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
        // Pre-register the mapping
        registerLabel(itemName, itemId);
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
        // Register and check for fuzzy matches
        registerAndMaybeMatch(text);
    }

    addFreeBtn.addEventListener("click", addFreeText);
    freeTextInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); addFreeText(); }
    });

    // --- Server Registration ---
    async function registerLabel(text, itemId) {
        try {
            await fetch("/labels/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, item_id: itemId || undefined }),
            });
        } catch (err) {
            console.error("Failed to register label:", err);
        }
    }

    async function registerAndMaybeMatch(text) {
        try {
            const res = await fetch("/labels/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text }),
            });
            const data = await res.json();

            if (data.status === "candidates" && data.candidates.length > 0) {
                showFuzzyModal(text, data.candidates);
            } else {
                // No match or already added
                addToQueue(text, null, text);
            }
        } catch (err) {
            console.error("Failed to register:", err);
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
                <span class="badge bg-blue-lt">${c.score}%</span>
            </a>
        `).join("");

        container.querySelectorAll(".fuzzy-pick").forEach(el => {
            el.addEventListener("click", (e) => {
                e.preventDefault();
                const id = el.dataset.id;
                const name = el.dataset.name;
                // Re-register with the item_id
                registerLabel(text, id);
                addToQueue(text, id, name);
                bootstrap.Modal.getInstance(document.getElementById("modal-fuzzy")).hide();
            });
        });

        // Show modal — also allow skip (just adds without mapping)
        const modal = new bootstrap.Modal(document.getElementById("modal-fuzzy"));
        const modalEl = document.getElementById("modal-fuzzy");
        modalEl.addEventListener("hidden.bs.modal", function handler() {
            modalEl.removeEventListener("hidden.bs.modal", handler);
            // If nothing was picked, add without mapping
            if (!getQueue().some(l => l.text === text)) {
                addToQueue(text, null, text);
            }
        });
        modal.show();
    }

    // --- Print ---
    printBtn.addEventListener("click", () => {
        const queue = getQueue();
        if (queue.length === 0) return;

        const size = sizeSelect.value;
        const columns = parseInt(columnsSelect.value);
        const showText = showTextCheck.checked;

        // Set CSS variables for print
        const sizeMap = { small: "25mm", medium: "35mm", large: "50mm" };
        printGrid.style.setProperty("--label-size", sizeMap[size]);
        printGrid.style.setProperty("--label-columns", columns);

        printGrid.innerHTML = queue.map(label => `
            <div class="label-cell">
                <img src="/labels/qr.svg?text=${encodeURIComponent(label.text)}" alt="${escapeAttr(label.text)}">
                ${showText ? `<span class="label-text">${escapeHtml(label.itemName || label.text)}</span>` : ""}
            </div>
        `).join("");

        // Small delay to let images load, then print
        setTimeout(() => window.print(), 300);
    });

    // --- Clear All ---
    clearBtn.addEventListener("click", () => {
        if (confirm("Remove all labels from the queue?")) {
            localStorage.removeItem(STORAGE_KEY);
            renderQueue();
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
})();
