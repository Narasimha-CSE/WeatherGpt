/* WeatherGPT - bottom navigation: shows only the features that belong to the selected page. */
(function () {
    "use strict";
    var TABS = ["home", "graphs", "tools", "advisory"];
    var body = document.body;
    var buttons = [].slice.call(document.querySelectorAll("#bottomTabs [data-go-tab]"));
    var nav = document.getElementById("featureNav");
    var ctx = document.getElementById("tabContext");
    var ctxCity = document.getElementById("tabCity");
    var cityName = document.getElementById("cityName");
    var initialCity = cityName ? cityName.textContent.trim() : "";
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var current = null;

    /* The "Previous days / Next days / Climate graph" tools are built inside the weather panel;
       move them (with their event listeners) into the Graphs page. */
    var host = document.getElementById("analyticsHost");
    if (host) ["climateTools", "climateDataPanel"].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) host.appendChild(el);
    });

    function refreshLayout() {
        window.dispatchEvent(new Event("resize"));
        if (window.Chart && Chart.instances) Object.keys(Chart.instances).forEach(function (k) { try { Chart.instances[k].resize(); } catch (e) { /* ignore */ } });
    }

    function updateNav() {
        if (!nav) return;
        var any = false;
        [].slice.call(nav.querySelectorAll("a[href^='#']")).forEach(function (a) {
            var t = document.querySelector(a.getAttribute("href"));
            var show = !!t && t.getAttribute("data-page") === current;
            a.classList.toggle("tab-hidden", !show);
            if (show) any = true;
        });
        nav.classList.toggle("tab-hidden", !any);
    }

    function updateContext() {
        if (!ctx) return;
        var text = cityName ? cityName.textContent.trim() : "";
        var has = text && text !== initialCity && text !== "--";
        ctx.hidden = current === "home";
        ctxCity.textContent = has ? text : "No city selected yet";
    }

    function setTab(tab, opts) {
        if (TABS.indexOf(tab) < 0) tab = "home";
        current = tab;
        body.setAttribute("data-active-tab", tab);
        body.classList.add("has-tabs");
        [].slice.call(document.querySelectorAll("[data-page]")).forEach(function (el) {
            el.classList.toggle("tab-hidden", el.getAttribute("data-page") !== tab);
        });
        buttons.forEach(function (b) {
            var on = b.getAttribute("data-go-tab") === tab;
            b.classList.toggle("on", on);
            b.setAttribute("aria-current", on ? "page" : "false");
        });
        updateNav();
        updateContext();
        try { sessionStorage.setItem("wgpt_tab", tab); } catch (e) { /* storage unavailable */ }
        if (!(opts && opts.noScroll)) window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
        setTimeout(refreshLayout, 80);
        setTimeout(refreshLayout, 500);
    }

    buttons.forEach(function (b) { b.addEventListener("click", function () { setTab(b.getAttribute("data-go-tab")); }); });

    var change = document.getElementById("tabChangeCity");
    if (change) change.addEventListener("click", function () {
        setTab("home");
        setTimeout(function () { var i = document.getElementById("cityInput"); if (i) i.focus({ preventScroll: true }); }, 350);
    });

    if (cityName && "MutationObserver" in window) new MutationObserver(updateContext).observe(cityName, { childList: true, characterData: true, subtree: true });

    /* highlight the sub-navigation link of the section currently in view (visible page only) */
    var ticking = false;
    function markActive() {
        ticking = false;
        if (!nav) return;
        var cur = null;
        [].slice.call(document.querySelectorAll(".fx-section")).forEach(function (sec) {
            if (sec.getAttribute("data-page") === current && sec.getBoundingClientRect().top <= 230) cur = sec.id;
        });
        [].slice.call(nav.querySelectorAll("a")).forEach(function (a) { a.classList.toggle("active", a.getAttribute("href") === "#" + cur); });
    }
    window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(markActive); } }, { passive: true });

    var start = "home";
    try { start = sessionStorage.getItem("wgpt_tab") || "home"; } catch (e) { /* ignore */ }
    setTab(start, { noScroll: true });
})();
