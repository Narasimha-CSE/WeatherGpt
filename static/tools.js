/* WeatherGPT - quick weather toolkit (unit converter, heat index / dew point, Beaufort wind scale). */
(function () {
    "use strict";
    var $ = function (id) { return document.getElementById(id); };
    if (!$("convType")) return;

    function fmt(n, d) {
        if (!isFinite(n)) return "--";
        var s = n.toFixed(d == null ? 3 : d);
        return s.indexOf(".") >= 0 ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
    }
    function liveNumber(id) {
        var el = $(id);
        var v = el ? parseFloat(String(el.textContent).replace(",", ".")) : NaN;
        return isFinite(v) ? v : null;
    }

    /* ---------- unit converter ---------- */
    var UNITS = {
        temp: ["°C", "°F", "K"],
        wind: { "m/s": 1, "km/h": 1 / 3.6, "mph": 0.44704, "knots": 0.514444 },
        rain: { "mm": 1, "cm": 10, "in": 25.4 },
        pressure: { "hPa": 1, "kPa": 10, "inHg": 33.8639, "mmHg": 1.33322 },
        distance: { "km": 1000, "mi": 1609.344, "m": 1, "ft": 0.3048 }
    };
    function names(type) { return Array.isArray(UNITS[type]) ? UNITS[type] : Object.keys(UNITS[type]); }
    function fillUnits() {
        var list = names($("convType").value);
        [$("convFrom"), $("convTo")].forEach(function (sel, i) {
            sel.innerHTML = list.map(function (u) { return "<option>" + u + "</option>"; }).join("");
            sel.selectedIndex = Math.min(i, list.length - 1);
        });
    }
    function convert() {
        var type = $("convType").value, v = parseFloat($("convValue").value), from = $("convFrom").value, to = $("convTo").value, out;
        if (!isFinite(v)) { $("convResult").textContent = "--"; return; }
        if (type === "temp") {
            var c = from === "°C" ? v : from === "°F" ? (v - 32) * 5 / 9 : v - 273.15;
            out = to === "°C" ? c : to === "°F" ? c * 9 / 5 + 32 : c + 273.15;
        } else {
            out = v * UNITS[type][from] / UNITS[type][to];
        }
        $("convResult").textContent = fmt(v) + " " + from + " = " + fmt(out) + " " + to;
    }
    $("convType").addEventListener("change", function () { fillUnits(); convert(); });
    ["convValue", "convFrom", "convTo"].forEach(function (id) { $(id).addEventListener("input", convert); $(id).addEventListener("change", convert); });
    fillUnits(); convert();

    /* ---------- heat index + dew point ---------- */
    function heatIndexC(tc, rh) {
        var t = tc * 9 / 5 + 32;
        var hi = 0.5 * (t + 61 + (t - 68) * 1.2 + rh * 0.094);
        if ((hi + t) / 2 >= 80) {
            hi = -42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh - 0.00683783 * t * t - 0.05481717 * rh * rh +
                0.00122874 * t * t * rh + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh;
            if (rh < 13 && t >= 80 && t <= 112) hi -= ((13 - rh) / 4) * Math.sqrt((17 - Math.abs(t - 95)) / 17);
            else if (rh > 85 && t >= 80 && t <= 87) hi += ((rh - 85) / 10) * ((87 - t) / 5);
        }
        return (hi - 32) * 5 / 9;
    }
    function dewPointC(tc, rh) {
        var a = 17.62, b = 243.12, g = Math.log(rh / 100) + a * tc / (b + tc);
        return b * g / (a - g);
    }
    function comfort(td) {
        if (td < 10) return "Dry and comfortable";
        if (td < 16) return "Comfortable";
        if (td < 18) return "Slightly humid";
        if (td < 21) return "Humid and muggy";
        if (td < 24) return "Oppressive";
        return "Extremely uncomfortable";
    }
    function heat() {
        var t = parseFloat($("hiTemp").value), rh = parseFloat($("hiHum").value), el = $("hiResult");
        if (!isFinite(t) || !isFinite(rh) || rh <= 0 || rh > 100) { el.textContent = "Enter a temperature and a humidity between 1 and 100%."; return; }
        var hi = heatIndexC(t, rh), td = dewPointC(t, rh);
        el.innerHTML = "Feels like " + fmt(hi, 1) + " °C<small>Dew point " + fmt(td, 1) + " °C · " + comfort(td) + "</small>";
    }
    ["hiTemp", "hiHum"].forEach(function (id) { $(id).addEventListener("input", heat); });
    $("hiUseLive").addEventListener("click", function () {
        var t = liveNumber("temperature"), h = liveNumber("humidity");
        if (t == null || h == null) { $("hiResult").textContent = "Search for a city on the Home page first."; return; }
        $("hiTemp").value = t; $("hiHum").value = h; heat();
    });
    heat();

    /* ---------- Beaufort wind scale ---------- */
    var BF = [
        [0.3, "Calm", "Smoke rises straight up."], [1.6, "Light air", "Smoke drifts slowly."], [3.4, "Light breeze", "Leaves rustle."],
        [5.5, "Gentle breeze", "Leaves and small twigs move."], [8, "Moderate breeze", "Dust and loose paper lift."], [10.8, "Fresh breeze", "Small trees sway."],
        [13.9, "Strong breeze", "Umbrellas are hard to use."], [17.2, "Near gale", "Walking against the wind is difficult."], [20.8, "Gale", "Twigs break off trees."],
        [24.5, "Strong gale", "Slight structural damage is possible."], [28.5, "Storm", "Trees can be uprooted."], [32.7, "Violent storm", "Widespread damage."],
        [Infinity, "Hurricane force", "Devastating damage. Stay indoors."]
    ];
    function beaufort() {
        var v = parseFloat($("bfSpeed").value), el = $("bfResult");
        if (!isFinite(v) || v < 0) { el.textContent = "Enter a wind speed in m/s."; return; }
        var i = 0;
        while (i < BF.length - 1 && v >= BF[i][0]) i++;
        el.innerHTML = "Force " + i + " · " + BF[i][1] + "<small>" + fmt(v, 1) + " m/s = " + fmt(v * 3.6, 1) + " km/h. " + BF[i][2] + "</small>";
    }
    $("bfSpeed").addEventListener("input", beaufort);
    $("bfUseLive").addEventListener("click", function () {
        var w = liveNumber("wind");
        if (w == null) { $("bfResult").textContent = "Search for a city on the Home page first."; return; }
        $("bfSpeed").value = w; beaufort();
    });
    beaufort();
})();
