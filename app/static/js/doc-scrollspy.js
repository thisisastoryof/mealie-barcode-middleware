// Lightweight scroll-spy using IntersectionObserver.
// Highlights the matching TOC link in #doc-toc as h2 headings scroll into view.
(function () {
    "use strict";

    var toc = document.getElementById("doc-toc");
    if (!toc) return;

    var links = toc.querySelectorAll("a.nav-link");
    if (!links.length) return;

    // Build a map: heading id → nav link
    var linkMap = {};
    links.forEach(function (link) {
        var id = link.getAttribute("href");
        if (id && id.charAt(0) === "#") {
            linkMap[id.slice(1)] = link;
        }
    });

    var headingIds = Object.keys(linkMap);
    var headings = [];
    headingIds.forEach(function (id) {
        var el = document.getElementById(id);
        if (el) headings.push(el);
    });

    if (!headings.length) return;

    var currentId = null;

    function setActive(id) {
        if (id === currentId) return;
        currentId = id;
        links.forEach(function (l) { l.classList.remove("active"); });
        if (id && linkMap[id]) linkMap[id].classList.add("active");
    }

    // Use IntersectionObserver to detect which heading is at/near the top
    var observer = new IntersectionObserver(
        function (entries) {
            // Find the topmost visible heading
            var visible = [];
            entries.forEach(function (e) {
                if (e.isIntersecting) {
                    visible.push({ id: e.target.id, top: e.boundingClientRect.top });
                }
            });

            if (visible.length) {
                visible.sort(function (a, b) { return a.top - b.top; });
                setActive(visible[0].id);
                return;
            }

            // Fallback: find the last heading that scrolled past the viewport top
            var scrollY = window.scrollY || document.documentElement.scrollTop;
            var best = null;
            headings.forEach(function (h) {
                if (h.offsetTop <= scrollY + 120) best = h.id;
            });
            if (best) setActive(best);
        },
        { rootMargin: "-80px 0px -60% 0px", threshold: 0 }
    );

    headings.forEach(function (h) { observer.observe(h); });

    // Activate the first entry on load
    setActive(headings[0].id);
})();
