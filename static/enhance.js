/* WeatherGPT — UI polish helpers (visual only; does not touch app logic) */
(function () {
    "use strict";
    const ready = (fn) => document.readyState !== "loading" ? fn() : document.addEventListener("DOMContentLoaded", fn);

    ready(() => {
        /* 1. Ripple on buttons */
        const rippleSel = ".search-area button, .send-button, .mic-button, .quick-questions button, .climate-btn";
        document.addEventListener("pointerdown", (e) => {
            const btn = e.target.closest(rippleSel);
            if (!btn) return;
            const r = btn.getBoundingClientRect();
            const size = Math.max(r.width, r.height);
            const dot = document.createElement("span");
            dot.className = "wg-ripple";
            dot.style.width = dot.style.height = size + "px";
            dot.style.left = (e.clientX - r.left - size / 2) + "px";
            dot.style.top = (e.clientY - r.top - size / 2) + "px";
            if (getComputedStyle(btn).position === "static") btn.style.position = "relative";
            btn.style.overflow = "hidden";
            btn.appendChild(dot);
            setTimeout(() => dot.remove(), 700);
        });

        /* 2. Scroll reveal */
        const targets = document.querySelectorAll(".main-grid > *, .insights-section, .insight-card");
        document.querySelectorAll(".insight-card").forEach((c, i) => c.style.setProperty("--i", i));
        if ("IntersectionObserver" in window) {
            const io = new IntersectionObserver((entries) => {
                entries.forEach((en) => {
                    if (en.isIntersecting) { en.target.classList.add("wg-in"); io.unobserve(en.target); }
                });
            }, { threshold: 0.12 });
            targets.forEach((t) => { t.classList.add("wg-reveal"); io.observe(t); });
        }

        /* 3. Cursor-follow glow on weather panel */
        const panel = document.querySelector(".weather-panel");
        if (panel) {
            panel.addEventListener("pointermove", (e) => {
                const r = panel.getBoundingClientRect();
                panel.style.setProperty("--mx", (e.clientX - r.left) + "px");
                panel.style.setProperty("--my", (e.clientY - r.top) + "px");
            });
        }

        /* 4. Pop animation when temperature / insight lists update */
        const watch = (el, cb) => el && new MutationObserver(cb).observe(el, { childList: true, characterData: true, subtree: true });
        const temp = document.getElementById("temperature");
        watch(temp, () => { temp.classList.remove("pop"); void temp.offsetWidth; temp.classList.add("pop"); });
        ["insightStatus", "insightAlert", "insightClothing", "insightHealth", "insightTravel"].forEach((id) => {
            const ul = document.getElementById(id);
            watch(ul, () => {
                if (ul.classList.contains("refresh")) return;
                ul.classList.add("refresh");
                setTimeout(() => ul.classList.remove("refresh"), 900);
            });
        });

        /* 5. Smooth auto-scroll for new chat messages */
        const chat = document.getElementById("chatContainer");
        watch(chat, () => chat.scrollTo({ top: chat.scrollHeight, behavior: "smooth" }));
    });
})();
