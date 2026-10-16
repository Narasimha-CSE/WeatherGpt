/* =====================================================================
   WeatherGPT — feature modules
   Forecast intelligence · alerts · recommendations · travel · farmer ·
   climate intelligence · interactive map · logout · speaker toggle
===================================================================== */
(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);
    const qa = (sel, root) => Array.from((root || document).querySelectorAll(sel));
    const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const lang = () => (window.WG && window.WG.getLanguage && window.WG.getLanguage()) || "en";
    const LOCALE = { en: "en-IN", te: "te-IN", hi: "hi-IN" };
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

    /* ------------------------------------------------------------------
       Session handling: any API call answered with 401 sends you to /login
    ------------------------------------------------------------------ */
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async function () {
        const res = await nativeFetch.apply(null, arguments);
        if (res.status === 401) {
            try { const j = await res.clone().json(); if (j && j.login_required) window.location.href = "/login"; } catch (_) { /* ignore */ }
        }
        return res;
    };
    /* ------------------------------------------------------------------
       Translations (UI labels)
    ------------------------------------------------------------------ */
    const T = {
        en: {
            nav_forecast: "📅 Forecast", nav_alerts: "🚨 Alerts", nav_recs: "👕 Advice", nav_travel: "✈️ Travel", nav_farm: "🌾 Farmer", nav_climate: "📊 Climate", nav_map: "🗺️ Map",
            forecast_label: "FORECAST INTELLIGENCE", forecast_title: "Hourly and multi-day forecast",
            alerts_label: "SMART WEATHER ALERTS", alerts_title: "What to watch in the next 24 hours",
            recs_label: "SMART RECOMMENDATIONS", recs_title: "Weather turned into practical advice",
            travel_label: "TRAVEL INTELLIGENCE", travel_title: "Is it a good time to travel?",
            farm_label: "AGRICULTURE ADVISORY", farm_title: "Farmer weather advisory",
            climate_label: "CLIMATE INTELLIGENCE", climate_title: "Historical climate, trends and anomalies",
            map_label: "INTERACTIVE WEATHER MAP", map_title: "Rain, wind, temperature, clouds and radar",
            empty_search: "Search for a city to see this section.", ai_explains: "AI explains the forecast", crop_label: "Crop",
            farm_ai_btn: "🤖 Get AI advice for this crop", years_label: "Period",
            tab_temp: "🌡️ Temperature", tab_rain: "🌧️ Rainfall", tab_anomaly: "⚠️ Anomalies", tab_compare: "⚖️ Compare periods",
            layer_rain: "🌧️ Rain", layer_wind: "💨 Wind", layer_temp: "🌡️ Temperature", layer_clouds: "☁️ Clouds", layer_radar: "📡 Radar",
            map_hint: "Tip: click anywhere on the map to check the weather at that spot.",
            uv_label: "UV INDEX", wdir_label: "WIND DIRECTION", now: "Now", today: "Today", yr: "yr",
            uv_low: "Low", uv_mod: "Moderate", uv_high: "High", uv_vhigh: "Very high", uv_ext: "Extreme",
            lvl_extreme: "EXTREME", lvl_warning: "WARNING", lvl_advisory: "ADVISORY", lvl_ok: "ALL CLEAR",
            rec_clothing: "Clothing", rec_umbrella: "Umbrella", rec_outdoor: "Outdoor activity", rec_sun: "Sun protection", rec_health: "Health precautions", rec_travel: "Travel",
            farm_irrigation: "Irrigation", farm_spraying: "Spraying", farm_pest: "Pest & disease risk", farm_harvest: "Harvest guidance", farm_protection: "Crop protection",
            crop_rice: "Rice", crop_cotton: "Cotton", crop_chilli: "Chilli", crop_maize: "Maize", crop_groundnut: "Groundnut", crop_tobacco: "Tobacco", crop_banana: "Banana", crop_sugarcane: "Sugarcane", crop_tomato: "Tomato", crop_wheat: "Wheat",
            f_rain: "Rain", f_wind: "Wind gusts", f_temp: "Feels like", f_vis: "Visibility", f_cond: "Conditions",
            g_clear: "Clear", g_partly: "Partly cloudy", g_cloudy: "Cloudy", g_fog: "Fog", g_drizzle: "Drizzle", g_rain: "Rain", g_showers: "Showers", g_snow: "Snow", g_storm: "Thunderstorm",
            loading: "Loading…", err_generic: "Could not load this section.", ai_wait: "Thinking…", ai_fail: "AI advice is unavailable right now.",
            chart_temp: "Temperature (°C)", chart_rain: "Rain chance (%)", chart_rain_mm: "Rainfall (mm)", chart_trend: "Trend", chart_anom: "Deviation from normal (°C)", chart_avg: "Average", chart_a: "Earlier period", chart_b: "Recent period",
            clim_loading: "Loading climate history…", clim_fail: "Could not load climate history.",
            st_trend: "TEMPERATURE TREND", st_hot: "HOTTEST YEAR", st_cold: "COLDEST YEAR", st_avg: "AVERAGE", per_decade: "per decade",
            st_rtrend: "RAINFALL TREND", st_wet: "WETTEST YEAR", st_dry: "DRIEST YEAR", st_arain: "AVG ANNUAL RAIN",
            st_anoms: "ANOMALIES FOUND", st_strong: "STRONGEST", st_period: "PERIOD",
            st_dtemp: "TEMPERATURE CHANGE", st_drain: "RAINFALL CHANGE", st_dhot: "HOT DAYS (≥40°C)", st_drainy: "RAINY DAYS", vs: "vs earlier",
            anom_hot: "Unusually warm", anom_cold: "Unusually cool", anom_wet: "Unusually wet", anom_dry: "Unusually dry", anom_none: "No significant anomalies in this period.", normal: "normal",
            map_view: "View full weather here", map_loading: "Checking weather…", map_fail: "Weather unavailable here.",
            lg_rain: "Rain intensity", lg_wind: "Wind speed (m/s)", lg_temp: "Temperature (°C)", lg_clouds: "Cloud cover (%)", lg_radar: "Radar reflectivity", radar_fail: "Radar is unavailable right now.",
            read_aloud: "Read aloud", per_day: "mm", mm: "mm", kmh: "km/h",
        },
        te: {
            nav_forecast: "📅 అంచనా", nav_alerts: "🚨 హెచ్చరికలు", nav_recs: "👕 సలహాలు", nav_travel: "✈️ ప్రయాణం", nav_farm: "🌾 రైతు", nav_climate: "📊 వాతావరణ చరిత్ర", nav_map: "🗺️ మ్యాప్",
            forecast_label: "వాతావరణ అంచనా", forecast_title: "గంటవారీ మరియు రోజువారీ అంచనా",
            alerts_label: "స్మార్ట్ వాతావరణ హెచ్చరికలు", alerts_title: "రాబోయే 24 గంటల్లో గమనించవలసినవి",
            recs_label: "స్మార్ట్ సిఫార్సులు", recs_title: "వాతావరణాన్ని ఉపయోగకరమైన సలహాగా మార్చాం",
            travel_label: "ప్రయాణ సమాచారం", travel_title: "ప్రయాణానికి ఇది మంచి సమయమా?",
            farm_label: "వ్యవసాయ సలహా", farm_title: "రైతుల కోసం వాతావరణ సలహా",
            climate_label: "వాతావరణ విశ్లేషణ", climate_title: "చారిత్రక వాతావరణం, ధోరణులు, అసాధారణతలు",
            map_label: "ఇంటరాక్టివ్ వాతావరణ మ్యాప్", map_title: "వర్షం, గాలి, ఉష్ణోగ్రత, మేఘాలు, రాడార్",
            empty_search: "ఈ విభాగం చూడటానికి ముందు ఒక నగరాన్ని వెతకండి.", ai_explains: "AI అంచనాను వివరిస్తుంది", crop_label: "పంట",
            farm_ai_btn: "🤖 ఈ పంటకు AI సలహా పొందండి", years_label: "కాలం",
            tab_temp: "🌡️ ఉష్ణోగ్రత", tab_rain: "🌧️ వర్షపాతం", tab_anomaly: "⚠️ అసాధారణతలు", tab_compare: "⚖️ కాలాల పోలిక",
            layer_rain: "🌧️ వర్షం", layer_wind: "💨 గాలి", layer_temp: "🌡️ ఉష్ణోగ్రత", layer_clouds: "☁️ మేఘాలు", layer_radar: "📡 రాడార్",
            map_hint: "చిట్కా: ఆ ప్రదేశ వాతావరణం చూడటానికి మ్యాప్‌పై ఎక్కడైనా క్లిక్ చేయండి.",
            uv_label: "UV సూచిక", wdir_label: "గాలి దిశ", now: "ఇప్పుడు", today: "ఈ రోజు", yr: "సం.",
            uv_low: "తక్కువ", uv_mod: "మధ్యస్థం", uv_high: "ఎక్కువ", uv_vhigh: "చాలా ఎక్కువ", uv_ext: "అత్యంత ఎక్కువ",
            lvl_extreme: "తీవ్రం", lvl_warning: "హెచ్చరిక", lvl_advisory: "సూచన", lvl_ok: "సురక్షితం",
            rec_clothing: "దుస్తులు", rec_umbrella: "గొడుగు", rec_outdoor: "బయట కార్యకలాపాలు", rec_sun: "ఎండ నుంచి రక్షణ", rec_health: "ఆరోగ్య జాగ్రత్తలు", rec_travel: "ప్రయాణం",
            farm_irrigation: "నీటిపారుదల", farm_spraying: "పిచికారీ", farm_pest: "చీడపీడల ప్రమాదం", farm_harvest: "కోత సలహా", farm_protection: "పంట రక్షణ",
            crop_rice: "వరి", crop_cotton: "పత్తి", crop_chilli: "మిరప", crop_maize: "మొక్కజొన్న", crop_groundnut: "వేరుశనగ", crop_tobacco: "పొగాకు", crop_banana: "అరటి", crop_sugarcane: "చెరకు", crop_tomato: "టమాటా", crop_wheat: "గోధుమ",
            f_rain: "వర్షం", f_wind: "గాలి ఝంఝ", f_temp: "అనుభూతి", f_vis: "దృశ్యమానత", f_cond: "పరిస్థితి",
            g_clear: "నిర్మలం", g_partly: "పాక్షిక మేఘావృతం", g_cloudy: "మేఘావృతం", g_fog: "పొగమంచు", g_drizzle: "తుంపర", g_rain: "వర్షం", g_showers: "జల్లులు", g_snow: "మంచు", g_storm: "ఉరుములతో వర్షం",
            loading: "లోడ్ అవుతోంది…", err_generic: "ఈ విభాగాన్ని లోడ్ చేయలేకపోయాం.", ai_wait: "ఆలోచిస్తోంది…", ai_fail: "AI సలహా ప్రస్తుతం అందుబాటులో లేదు.",
            chart_temp: "ఉష్ణోగ్రత (°C)", chart_rain: "వర్షం అవకాశం (%)", chart_rain_mm: "వర్షపాతం (మి.మీ.)", chart_trend: "ధోరణి", chart_anom: "సాధారణం నుంచి తేడా (°C)", chart_avg: "సగటు", chart_a: "ముందు కాలం", chart_b: "ఇటీవలి కాలం",
            clim_loading: "వాతావరణ చరిత్ర లోడ్ అవుతోంది…", clim_fail: "వాతావరణ చరిత్రను లోడ్ చేయలేకపోయాం.",
            st_trend: "ఉష్ణోగ్రత ధోరణి", st_hot: "అత్యంత వేడి సంవత్సరం", st_cold: "అత్యంత చల్లని సంవత్సరం", st_avg: "సగటు", per_decade: "దశాబ్దానికి",
            st_rtrend: "వర్షపాత ధోరణి", st_wet: "అత్యంత తడి సంవత్సరం", st_dry: "అత్యంత పొడి సంవత్సరం", st_arain: "సగటు వార్షిక వర్షం",
            st_anoms: "కనుగొన్న అసాధారణతలు", st_strong: "అత్యంత తీవ్రమైనది", st_period: "కాలం",
            st_dtemp: "ఉష్ణోగ్రత మార్పు", st_drain: "వర్షపాత మార్పు", st_dhot: "వేడి రోజులు (≥40°C)", st_drainy: "వర్షపు రోజులు", vs: "ముందు కాలంతో పోలిస్తే",
            anom_hot: "అసాధారణంగా వేడి", anom_cold: "అసాధారణంగా చల్లగా", anom_wet: "అసాధారణంగా తడి", anom_dry: "అసాధారణంగా పొడి", anom_none: "ఈ కాలంలో గణనీయమైన అసాధారణతలు లేవు.", normal: "సాధారణం",
            map_view: "ఇక్కడి పూర్తి వాతావరణం చూడండి", map_loading: "వాతావరణం చూస్తోంది…", map_fail: "ఇక్కడ వాతావరణం అందుబాటులో లేదు.",
            lg_rain: "వర్షం తీవ్రత", lg_wind: "గాలి వేగం (మీ/సె)", lg_temp: "ఉష్ణోగ్రత (°C)", lg_clouds: "మేఘాల కవరేజ్ (%)", lg_radar: "రాడార్ ప్రతిబింబం", radar_fail: "రాడార్ ప్రస్తుతం అందుబాటులో లేదు.",
            read_aloud: "చదివి వినిపించు", mm: "మి.మీ.", kmh: "కి.మీ./గం.",
        },
        hi: {
            nav_forecast: "📅 पूर्वानुमान", nav_alerts: "🚨 चेतावनी", nav_recs: "👕 सलाह", nav_travel: "✈️ यात्रा", nav_farm: "🌾 किसान", nav_climate: "📊 जलवायु", nav_map: "🗺️ नक्शा",
            forecast_label: "मौसम पूर्वानुमान", forecast_title: "घंटेवार और बहु-दिवसीय पूर्वानुमान",
            alerts_label: "स्मार्ट मौसम चेतावनी", alerts_title: "अगले 24 घंटों में ध्यान देने योग्य बातें",
            recs_label: "स्मार्ट सुझाव", recs_title: "मौसम को उपयोगी सलाह में बदला गया",
            travel_label: "यात्रा जानकारी", travel_title: "क्या यात्रा के लिए यह अच्छा समय है?",
            farm_label: "कृषि सलाह", farm_title: "किसानों के लिए मौसम सलाह",
            climate_label: "जलवायु विश्लेषण", climate_title: "ऐतिहासिक जलवायु, रुझान और असामान्यताएं",
            map_label: "इंटरैक्टिव मौसम नक्शा", map_title: "बारिश, हवा, तापमान, बादल और रडार",
            empty_search: "यह अनुभाग देखने के लिए पहले कोई शहर खोजें।", ai_explains: "AI पूर्वानुमान समझाता है", crop_label: "फसल",
            farm_ai_btn: "🤖 इस फसल के लिए AI सलाह लें", years_label: "अवधि",
            tab_temp: "🌡️ तापमान", tab_rain: "🌧️ वर्षा", tab_anomaly: "⚠️ असामान्यताएं", tab_compare: "⚖️ अवधियों की तुलना",
            layer_rain: "🌧️ बारिश", layer_wind: "💨 हवा", layer_temp: "🌡️ तापमान", layer_clouds: "☁️ बादल", layer_radar: "📡 रडार",
            map_hint: "सुझाव: उस जगह का मौसम देखने के लिए नक्शे पर कहीं भी क्लिक करें।",
            uv_label: "UV सूचकांक", wdir_label: "हवा की दिशा", now: "अभी", today: "आज", yr: "वर्ष",
            uv_low: "कम", uv_mod: "मध्यम", uv_high: "अधिक", uv_vhigh: "बहुत अधिक", uv_ext: "अत्यधिक",
            lvl_extreme: "गंभीर", lvl_warning: "चेतावनी", lvl_advisory: "सलाह", lvl_ok: "सब सामान्य",
            rec_clothing: "कपड़े", rec_umbrella: "छाता", rec_outdoor: "बाहरी गतिविधि", rec_sun: "धूप से सुरक्षा", rec_health: "स्वास्थ्य सावधानियां", rec_travel: "यात्रा",
            farm_irrigation: "सिंचाई", farm_spraying: "छिड़काव", farm_pest: "कीट और रोग जोखिम", farm_harvest: "कटाई सलाह", farm_protection: "फसल सुरक्षा",
            crop_rice: "धान", crop_cotton: "कपास", crop_chilli: "मिर्च", crop_maize: "मक्का", crop_groundnut: "मूंगफली", crop_tobacco: "तंबाकू", crop_banana: "केला", crop_sugarcane: "गन्ना", crop_tomato: "टमाटर", crop_wheat: "गेहूं",
            f_rain: "बारिश", f_wind: "हवा के झोंके", f_temp: "महसूस तापमान", f_vis: "दृश्यता", f_cond: "स्थिति",
            g_clear: "साफ", g_partly: "आंशिक बादल", g_cloudy: "बादल", g_fog: "कोहरा", g_drizzle: "फुहार", g_rain: "बारिश", g_showers: "बौछारें", g_snow: "बर्फ", g_storm: "आंधी-तूफान",
            loading: "लोड हो रहा है…", err_generic: "यह अनुभाग लोड नहीं हो सका।", ai_wait: "सोच रहा है…", ai_fail: "AI सलाह अभी उपलब्ध नहीं है।",
            chart_temp: "तापमान (°C)", chart_rain: "बारिश की संभावना (%)", chart_rain_mm: "वर्षा (मिमी)", chart_trend: "रुझान", chart_anom: "सामान्य से अंतर (°C)", chart_avg: "औसत", chart_a: "पहले की अवधि", chart_b: "हाल की अवधि",
            clim_loading: "जलवायु इतिहास लोड हो रहा है…", clim_fail: "जलवायु इतिहास लोड नहीं हो सका।",
            st_trend: "तापमान रुझान", st_hot: "सबसे गर्म वर्ष", st_cold: "सबसे ठंडा वर्ष", st_avg: "औसत", per_decade: "प्रति दशक",
            st_rtrend: "वर्षा रुझान", st_wet: "सबसे गीला वर्ष", st_dry: "सबसे सूखा वर्ष", st_arain: "औसत वार्षिक वर्षा",
            st_anoms: "मिली असामान्यताएं", st_strong: "सबसे तीव्र", st_period: "अवधि",
            st_dtemp: "तापमान परिवर्तन", st_drain: "वर्षा परिवर्तन", st_dhot: "गर्म दिन (≥40°C)", st_drainy: "बारिश के दिन", vs: "पहले की तुलना में",
            anom_hot: "असामान्य रूप से गर्म", anom_cold: "असामान्य रूप से ठंडा", anom_wet: "असामान्य रूप से गीला", anom_dry: "असामान्य रूप से सूखा", anom_none: "इस अवधि में कोई महत्वपूर्ण असामान्यता नहीं।", normal: "सामान्य",
            map_view: "यहां का पूरा मौसम देखें", map_loading: "मौसम देख रहे हैं…", map_fail: "यहां का मौसम उपलब्ध नहीं है।",
            lg_rain: "बारिश की तीव्रता", lg_wind: "हवा की गति (मी/से)", lg_temp: "तापमान (°C)", lg_clouds: "बादल आवरण (%)", lg_radar: "रडार परावर्तन", radar_fail: "रडार अभी उपलब्ध नहीं है।",
            read_aloud: "पढ़कर सुनाएं", mm: "मिमी", kmh: "किमी/घंटा",
        },
    };
    const tx = (k) => (T[lang()] && T[lang()][k]) || T.en[k] || k;

    const ICONS = { clear: ["☀️", "🌙"], partly: ["⛅", "☁️"], cloudy: ["☁️", "☁️"], fog: ["🌫️", "🌫️"], drizzle: ["🌦️", "🌧️"], rain: ["🌧️", "🌧️"], showers: ["🌦️", "🌧️"], snow: ["❄️", "❄️"], storm: ["⛈️", "⛈️"] };
    const icon = (group, day) => (ICONS[group] || ICONS.cloudy)[day === 0 ? 1 : 0];
    const ALERT_ICON = { th: "⛈️", rain: "🌧️", heat: "🌡️", wind: "💨", cold: "🥶", fog: "🌫️", uv: "☀️", ok: "✅" };
    const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
    const CROPS = ["rice", "cotton", "chilli", "maize", "groundnut", "tobacco", "banana", "sugarcane", "tomato", "wheat"];

    /* ------------------------------------------------------------------
       State
    ------------------------------------------------------------------ */
    const S = { lat: null, lon: null, name: "", data: null, crop: "rice", token: 0, charts: {}, explain: "", climate: null, climateKey: "", climView: "temp", climVisible: false, map: null, mapVisible: false };
    const SECTIONS = ["forecastSection", "alertsSection", "recsSection", "travelSection", "farmSection", "climateSection"];

    /* ------------------------------------------------------------------
       Helpers
    ------------------------------------------------------------------ */
    function setBody(id, state) { // state: "empty" | "loading" | "ready"
        const sec = $(id); if (!sec) return;
        const empty = sec.querySelector(".fx-empty"), body = sec.querySelector(".fx-body");
        if (!empty || !body) return;
        empty.hidden = state !== "empty";
        body.hidden = state === "empty";
        sec.classList.toggle("loading", state === "loading");
    }
    function sectionError(id, msg) {
        const sec = $(id); if (!sec) return;
        const body = sec.querySelector(".fx-body"); sec.classList.remove("loading");
        sec.querySelector(".fx-empty").hidden = true; body.hidden = false;
        body.innerHTML = '<div class="fx-error">' + esc(msg || tx("err_generic")) + "</div>";
    }
    function animateNumber(el, to, ms) {
        if (!el) return;
        if (reduce) { el.textContent = to; return; }
        const from = Number(el.textContent) || 0, t0 = performance.now();
        (function step(now) {
            const p = Math.min(1, (now - t0) / (ms || 1200)), e = 1 - Math.pow(1 - p, 3);
            el.textContent = Math.round(from + (to - from) * e);
            if (p < 1) requestAnimationFrame(step);
        })(t0);
    }
    async function typeInto(el, text, speed) {
        const mine = (el._tw = (el._tw || 0) + 1);
        if (reduce) { el.textContent = text; return; }
        el.classList.add("typing"); el.textContent = "";
        for (let i = 1; i <= text.length; i++) {
            if (el._tw !== mine) return;
            el.textContent = text.slice(0, i);
            if (i % 2 === 0) await sleep(speed || 14);
        }
        el.classList.remove("typing");
    }
    function chartDefaults() {
        if (!window.Chart) return false;
        Chart.defaults.color = "#8d9aab"; Chart.defaults.borderColor = "rgba(255,255,255,.07)";
        Chart.defaults.font.family = 'Inter, -apple-system, "Segoe UI", sans-serif';
        return true;
    }
    function mkChart(key, canvasId, cfg) {
        if (!chartDefaults()) return null;
        if (S.charts[key]) { S.charts[key].destroy(); S.charts[key] = null; }
        const cv = $(canvasId); if (!cv) return null;
        cfg.type = cfg.type || "bar";
        S.charts[key] = new Chart(cv, cfg);
        return S.charts[key];
    }
    const hh = (t) => t.slice(11, 13);
    const fmtDay = (date, i) => i === 0 ? tx("today") : new Date(date + "T00:00:00").toLocaleDateString(LOCALE[lang()], { weekday: "short" });
    const monthName = (m) => new Date(2000, m - 1, 1).toLocaleString(LOCALE[lang()], { month: "short" });

    /* ------------------------------------------------------------------
       Static label translation
    ------------------------------------------------------------------ */
    function applyStatic() {
        qa("[data-i18n]").forEach((el) => { el.textContent = tx(el.dataset.i18n); });
        const uv = $("uvLabel"); if (uv) uv.textContent = tx("uv_label");
        const wd = $("windDirLabel"); if (wd) wd.textContent = tx("wdir_label");
        const cs = $("cropSelect");
        if (cs) {
            if (!cs.options.length) CROPS.forEach((c) => { const o = document.createElement("option"); o.value = c; cs.appendChild(o); });
            qa("option", cs).forEach((o) => { o.textContent = tx("crop_" + o.value); });
            cs.value = S.crop;
        }
        qa("#climateYears option").forEach((o) => { o.textContent = o.value + " " + tx("yr"); });
        const eb = $("explainSpeak"); if (eb) eb.setAttribute("aria-label", tx("read_aloud"));
        renderLegend();
    }

    /* ------------------------------------------------------------------
       Overview loading
    ------------------------------------------------------------------ */
    window.addEventListener("wg:weather", (e) => {
        const d = e.detail || {};
        const lat = Number(d.latitude), lon = Number(d.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
        S.lat = lat; S.lon = lon; S.name = d.city || "";
        S.data = null; S.climate = null; S.climateKey = ""; S.explain = "";
        const place = $("fxPlace"); if (place) { place.hidden = false; place.textContent = "📍 " + S.name; }
        setBody("climateSection", "ready");
        const cst = $("climateStatus"); if (cst) cst.innerHTML = '<div><div class="spinner"></div>' + esc(tx("clim_loading")) + "</div>";
        if (S.charts.climate) { S.charts.climate.destroy(); S.charts.climate = null; }
        $("climateStats").innerHTML = "";
        loadOverview();
        ensureClimate();
        moveMap();
    });

    async function loadOverview() {
        if (S.lat == null) return;
        const token = ++S.token;
        SECTIONS.forEach((id) => { if (id !== "climateSection") setBody(id, "loading"); });
        try {
            const res = await fetch("/api/overview?lat=" + S.lat + "&lon=" + S.lon + "&language=" + lang() + "&crop=" + S.crop);
            const j = await res.json();
            if (token !== S.token) return;
            if (!res.ok) throw new Error(j.error || tx("err_generic"));
            S.data = j;
            renderAll(j);
            loadExplain(token);
        } catch (err) {
            if (token !== S.token) return;
            ["forecastSection", "alertsSection", "recsSection", "travelSection", "farmSection"].forEach((id) => sectionError(id, err.message));
        }
    }

    function renderAll(j) {
        ["forecastSection", "alertsSection", "recsSection", "travelSection", "farmSection"].forEach((id) => setBody(id, "ready"));
        renderNow(j.now);
        renderHourly(j.hourly);
        renderForecastChart(j.hourly);
        renderDaily(j.daily);
        renderAlerts(j.alerts);
        renderRecs(j.recommendations);
        renderTravel(j.travel);
        renderFarm(j.farm);
        setBody("climateSection", S.climate ? "ready" : "ready");
    }

    /* ---- current-weather extras (UV + wind direction) ---- */
    function uvLevel(uv) { return uv < 3 ? "low" : uv < 6 ? "mod" : uv < 8 ? "high" : uv < 11 ? "vhigh" : "ext"; }
    function renderNow(n) {
        const uvEl = $("uvIndex");
        if (uvEl) { const lv = uvLevel(n.uv); uvEl.innerHTML = esc(n.uv.toFixed(1)) + ' <span class="uv-pill uv-' + lv + '">' + esc(tx("uv_" + lv)) + "</span>"; }
        const wd = $("windDir");
        if (wd) {
            const name = COMPASS[Math.round(n.wdir / 22.5) % 16];
            wd.innerHTML = '<span class="wind-arrow" style="--r:' + Math.round(n.wdir + 90) + 'deg">➤</span>' + esc(name) + " · " + Math.round(n.wdir) + "°";
        }
    }

    /* ---- hourly strip / chart / daily ---- */
    function renderHourly(list) {
        const el = $("hourlyStrip"); if (!el) return;
        el.innerHTML = list.slice(0, 24).map((h, i) =>
            '<div class="hour' + (i === 0 ? " now" : "") + '" style="--i:' + i + '"><small>' + (i === 0 ? esc(tx("now")) : hh(h.time) + ":00") + '</small><span class="hi">' + icon(h.group, h.day) + "</span><b>" + Math.round(h.temp) + '°</b><div class="rp" style="--w:' + Math.round(h.pp) + '%"><i></i></div><em>' + Math.round(h.pp) + "%</em></div>").join("");
    }
    function renderForecastChart(list) {
        const rows = list.slice(0, 48);
        mkChart("forecast", "forecastChart", {
            data: {
                labels: rows.map((h) => hh(h.time) + ":00"),
                datasets: [
                    { type: "line", label: tx("chart_temp"), data: rows.map((h) => Math.round(h.temp * 10) / 10), yAxisID: "y", borderColor: "#fbbf24", backgroundColor: "rgba(251,191,36,.12)", fill: true, tension: .4, pointRadius: 0, pointHoverRadius: 5, borderWidth: 3, order: 1 },
                    { type: "bar", label: tx("chart_rain"), data: rows.map((h) => Math.round(h.pp)), yAxisID: "y1", backgroundColor: "rgba(93,120,255,.5)", borderRadius: 4, order: 2 },
                ],
            },
            options: {
                maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
                animation: { duration: reduce ? 0 : 1200, easing: "easeOutQuart" },
                plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8 } } },
                scales: {
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 12, maxRotation: 0 } },
                    y: { position: "left", title: { display: true, text: "°C" }, grid: { color: "rgba(255,255,255,.05)" } },
                    y1: { position: "right", min: 0, max: 100, title: { display: true, text: "%" }, grid: { display: false } },
                },
            },
        });
    }
    function renderDaily(list) {
        const el = $("dailyGrid"); if (!el) return;
        el.innerHTML = list.map((d, i) =>
            '<div class="day" style="--i:' + i + '"><div class="dn">' + esc(fmtDay(d.date, i)) + '</div><span class="di">' + icon(d.group, 1) + '</span><div class="dt">' + Math.round(d.tmax) + '° <span>/ ' + Math.round(d.tmin) + '°</span></div><small>☔ ' + Math.round(d.pp) + "% · " + d.mm.toFixed(1) + " " + esc(tx("mm")) + '</small><div class="dc">' + esc(tx("g_" + d.group)) + "</div></div>").join("");
    }

    /* ---- AI explanation ---- */
    async function loadExplain(token) {
        const p = $("explainText"); if (!p) return;
        p.textContent = tx("ai_wait"); p.classList.add("typing");
        try {
            const res = await fetch("/api/forecast-explain", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lat: S.lat, lon: S.lon, language: lang(), location: S.name }) });
            const j = await res.json();
            if (token !== S.token) return;
            if (!res.ok) throw new Error(j.error);
            S.explain = (j.explanation || "").replace(/[*#_`]/g, "").trim();
            await typeInto(p, S.explain, 12);
        } catch (_) {
            if (token === S.token) { p.classList.remove("typing"); p.textContent = (S.data && S.data.summary) || tx("err_generic"); S.explain = p.textContent; }
        }
    }
    function speakAloud(text, btn) {
        if (!("speechSynthesis" in window) || !text) return;
        if (speechSynthesis.speaking) { speechSynthesis.cancel(); if (btn) btn.classList.remove("playing"); return; }
        const u = new SpeechSynthesisUtterance(text); u.lang = LOCALE[lang()]; u.rate = .95;
        u.onend = u.onerror = () => btn && btn.classList.remove("playing");
        if (btn) btn.classList.add("playing");
        speechSynthesis.speak(u);
    }

    /* ---- alerts ---- */
    function renderAlerts(list) {
        const el = $("alertsList"); if (!el) return;
        el.innerHTML = list.map((a, i) =>
            '<div class="alert ' + esc(a.level) + '" style="--i:' + i + '"><div class="ai">' + (ALERT_ICON[a.id] || "⚠️") + '</div><div><h4>' + esc(a.title) + ' <span class="lvl">' + esc(tx("lvl_" + a.level)) + "</span></h4><p>" + esc(a.message) + "</p></div></div>").join("");
        const link = document.querySelector('.feature-nav a[href="#alertsSection"]');
        if (link) link.dataset.count = list.filter((a) => a.level !== "ok").length;
    }

    /* ---- recommendations ---- */
    function renderRecs(list) {
        const el = $("recsGrid"); if (!el) return;
        el.innerHTML = list.map((r, i) =>
            '<article class="rec" style="--i:' + i + '"><div class="ri">' + r.icon + "</div><h3>" + esc(tx("rec_" + r.id)) + "</h3><ul>" + r.tips.map((t) => "<li>" + esc(t) + "</li>").join("") + "</ul></article>").join("");
    }

    /* ---- travel ---- */
    function renderTravel(t) {
        if (!t || t.score == null) return;
        const ring = $("travelRing");
        ring.className = "travel-ring " + (t.level === "excellent" ? "" : t.level);
        ring.style.setProperty("--p", 0);
        requestAnimationFrame(() => requestAnimationFrame(() => ring.style.setProperty("--p", t.score)));
        $("travelScore").textContent = "0";
        animateNumber($("travelScore"), t.score, 1300);
        $("travelVerdict").textContent = t.verdict;
        const chips = ['<div class="tchip">' + esc(t.summary) + "</div>"];
        if (t.best) chips.push('<div class="tchip best">✅ ' + esc(t.best.text) + "</div>");
        if (t.avoid) chips.push('<div class="tchip avoid">⚠️ ' + esc(t.avoid.text) + "</div>");
        $("travelChips").innerHTML = chips.join("");
        const FI = { rain: "🌧️", wind: "💨", temp: "🌡️", vis: "👁️", cond: "⛅" }, W = { ok: 92, warn: 58, bad: 26 };
        const val = (f) => f.key === "rain" ? f.value + "% · " + f.extra + " " + tx("mm") : f.key === "wind" ? f.value + " " + tx("kmh") : f.key === "temp" ? f.value + "°C" : f.key === "vis" ? f.value + " km" : tx("g_" + f.value);
        $("travelFactors").innerHTML = t.factors.map((f, i) =>
            '<div class="factor ' + f.status + '" style="--i:' + i + '"><span>' + FI[f.key] + "</span><span>" + esc(tx("f_" + f.key)) + "</span><b>" + esc(val(f)) + '</b><div class="fb"><i style="--w:0%"></i></div></div>').join("");
        setTimeout(() => qa("#travelFactors .factor").forEach((el) => { const st = el.classList.contains("ok") ? "ok" : el.classList.contains("warn") ? "warn" : "bad"; el.querySelector(".fb i").style.setProperty("--w", W[st] + "%"); }), 120);
    }

    /* ---- farmer ---- */
    function renderFarm(f) {
        const el = $("farmGrid"); if (!el) return;
        el.innerHTML = f.cards.map((c, i) =>
            '<article class="fcard-farm st-' + c.status + '" style="--i:' + i + '"><header><span><i>' + c.icon + "</i>" + esc(tx("farm_" + c.id)) + '</span><b class="dot"></b></header><p>' + esc(c.text) + "</p></article>").join("");
        $("farmAIOut").hidden = true;
    }
    async function farmAI() {
        const btn = $("farmAIBtn"), out = $("farmAIOut");
        if (S.lat == null) return;
        btn.disabled = true; out.hidden = false; out.textContent = tx("ai_wait");
        try {
            const res = await fetch("/api/farmer-ai", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lat: S.lat, lon: S.lon, language: lang(), crop: S.crop, location: S.name }) });
            const j = await res.json();
            if (!res.ok) throw new Error(j.error);
            const text = (j.advice || "").replace(/[*#`]/g, "").replace(/^\s*-\s*/gm, "• ").trim();
            await typeInto(out, text, 8);
            if (window.WG && window.WG.isSpeechOn && window.WG.isSpeechOn()) window.WG.speak(text.replace(/•/g, ""), lang());
        } catch (_) { out.textContent = tx("ai_fail"); }
        finally { btn.disabled = false; }
    }

    /* ------------------------------------------------------------------
       Climate intelligence
    ------------------------------------------------------------------ */
    function ensureClimate() {
        if (S.lat == null || !S.climVisible) return;
        const years = Number($("climateYears").value) || 10;
        const key = [S.lat.toFixed(2), S.lon.toFixed(2), years].join("|");
        if (S.climateKey === key) return;
        S.climateKey = key;
        setBody("climateSection", "ready");
        const status = $("climateStatus"); status.innerHTML = '<div><div class="spinner"></div>' + esc(tx("clim_loading")) + "</div>";
        fetch("/api/climate?lat=" + S.lat + "&lon=" + S.lon + "&years=" + years)
            .then((r) => r.json().then((j) => ({ ok: r.ok, j })))
            .then(({ ok, j }) => {
                if (S.climateKey !== key) return;
                if (!ok) throw new Error(j.error);
                S.climate = j; status.textContent = ""; renderClimate();
            })
            .catch((e) => { if (S.climateKey === key) { status.textContent = e.message || tx("clim_fail"); S.climateKey = ""; } });
    }
    function regress(xs, ys) {
        const n = xs.length, mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
        let num = 0, den = 0; xs.forEach((x, i) => { num += (x - mx) * (ys[i] - my); den += (x - mx) * (x - mx); });
        const m = den ? num / den : 0; return xs.map((x) => my + m * (x - mx));
    }
    const arrow = (v) => v > 0.05 ? "▲" : v < -0.05 ? "▼" : "▶";
    const sgn = (v, d) => (v > 0 ? "+" : "") + v.toFixed(d == null ? 1 : d);

    function renderClimate() {
        const c = S.climate; if (!c) return;
        const v = S.climView, stats = [], list = $("anomalyList");
        list.hidden = v !== "anomaly";
        const yearly = c.yearly, avg = (k) => yearly.reduce((a, y) => a + y[k], 0) / yearly.length;
        if (v === "temp") {
            stats.push([tx("st_trend"), sgn(c.trend.temp_per_decade, 2) + "°C", tx("per_decade"), arrow(c.trend.temp_per_decade) === "▲" ? "up" : "down"], [tx("st_hot"), c.highlights.hottest, "", ""], [tx("st_cold"), c.highlights.coldest, "", ""], [tx("st_avg"), avg("temp").toFixed(1) + "°C", c.from + "–" + c.to, ""]);
        } else if (v === "rain") {
            stats.push([tx("st_rtrend"), sgn(c.trend.rain_pct_per_decade, 1) + "%", tx("per_decade"), c.trend.rain_pct_per_decade >= 0 ? "down" : "up"], [tx("st_wet"), c.highlights.wettest, "", ""], [tx("st_dry"), c.highlights.driest, "", ""], [tx("st_arain"), Math.round(avg("rain")) + " " + tx("mm"), c.from + "–" + c.to, ""]);
        } else if (v === "anomaly") {
            const top = c.anomalies[0];
            stats.push([tx("st_anoms"), c.anomaly_count, c.from + "–" + c.to, ""], [tx("st_strong"), top ? top.ym : "—", top ? (top.type === "temp" ? "🌡️ " : "🌧️ ") + sgn(top.z, 1) + "σ" : "", ""]);
        } else {
            const d = c.compare.delta, a = c.compare.a, b = c.compare.b;
            stats.push([tx("st_dtemp"), sgn(d.temp, 2) + "°C", a.from + "–" + a.to + " → " + b.from + "–" + b.to, d.temp > 0 ? "up" : "down"], [tx("st_drain"), sgn(d.rain_pct, 1) + "%", sgn(d.rain, 0) + " " + tx("mm"), d.rain >= 0 ? "down" : "up"], [tx("st_dhot"), sgn(d.hot_days, 1), b.hot_days + " / " + a.hot_days, d.hot_days > 0 ? "up" : "down"], [tx("st_drainy"), sgn(d.rainy_days, 1), b.rainy_days + " / " + a.rainy_days, ""]);
        }
        $("climateStats").innerHTML = stats.map((s, i) => '<div class="stat" style="--i:' + i + '"><small>' + esc(s[0]) + "</small><b>" + esc(s[1]) + '</b><span class="' + s[3] + '">' + esc(s[2]) + "</span></div>").join("");

        const months = Array.from({ length: 12 }, (_, i) => monthName(i + 1));
        const baseOpts = { maintainAspectRatio: false, animation: { duration: reduce ? 0 : 1100, easing: "easeOutQuart" }, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8 } } } };
        const longTicks = { callback: function (val) { const l = this.getLabelForValue(val); return l.endsWith("-01") ? l.slice(0, 4) : ""; }, autoSkip: false, maxRotation: 0 };

        if (v === "temp") {
            const xs = c.monthly.map((_, i) => i), ys = c.monthly.map((m) => m.temp);
            mkChart("climate", "climateIntelChart", { data: { labels: c.monthly.map((m) => m.ym), datasets: [
                { type: "line", label: tx("chart_temp"), data: ys, borderColor: "#fbbf24", backgroundColor: "rgba(251,191,36,.1)", fill: true, tension: .35, pointRadius: 0, borderWidth: 2 },
                { type: "line", label: tx("chart_trend"), data: regress(xs, ys), borderColor: "#f87171", borderDash: [6, 5], pointRadius: 0, borderWidth: 2.5 }] },
                options: Object.assign({}, baseOpts, { scales: { x: { grid: { display: false }, ticks: longTicks }, y: { title: { display: true, text: "°C" } } } }) });
        } else if (v === "rain") {
            const m = avg("rain");
            mkChart("climate", "climateIntelChart", { data: { labels: yearly.map((y) => y.year), datasets: [
                { type: "bar", label: tx("chart_rain_mm"), data: yearly.map((y) => y.rain), backgroundColor: yearly.map((y) => y.rain >= m ? "rgba(56,189,248,.7)" : "rgba(93,120,255,.45)"), borderRadius: 6 },
                { type: "line", label: tx("chart_avg"), data: yearly.map(() => Math.round(m)), borderColor: "#fbbf24", borderDash: [6, 5], pointRadius: 0, borderWidth: 2 }] },
                options: Object.assign({}, baseOpts, { scales: { x: { grid: { display: false } }, y: { title: { display: true, text: tx("mm") } } } }) });
        } else if (v === "anomaly") {
            const flagged = new Set(c.anomalies.filter((a) => a.type === "temp").map((a) => a.ym));
            const dev = c.monthly.map((m) => Math.round((m.temp - c.climatology.temp[m.month - 1]) * 100) / 100);
            mkChart("climate", "climateIntelChart", { data: { labels: c.monthly.map((m) => m.ym), datasets: [
                { type: "bar", label: tx("chart_anom"), data: dev, backgroundColor: c.monthly.map((m, i) => flagged.has(m.ym) ? (dev[i] > 0 ? "rgba(248,113,113,.95)" : "rgba(56,189,248,.95)") : (dev[i] > 0 ? "rgba(248,113,113,.35)" : "rgba(56,189,248,.35)")), borderWidth: 0 }] },
                options: Object.assign({}, baseOpts, { scales: { x: { grid: { display: false }, ticks: longTicks }, y: { title: { display: true, text: "°C" } } } }) });
            list.innerHTML = c.anomalies.length ? c.anomalies.map((a, i) => {
                const hot = a.value > a.normal, label = a.type === "temp" ? (hot ? tx("anom_hot") : tx("anom_cold")) : (hot ? tx("anom_wet") : tx("anom_dry"));
                const unit = a.type === "temp" ? "°C" : " " + tx("mm"), mon = monthName(Number(a.ym.slice(5))) + " " + a.ym.slice(0, 4);
                return '<div class="anomaly" style="--i:' + i + '"><span class="zi">' + (a.type === "temp" ? (hot ? "🔥" : "🧊") : (hot ? "🌊" : "🏜️")) + "</span><div><b>" + esc(label) + " · " + esc(mon) + "</b><small>" + a.value + unit + " (" + esc(tx("normal")) + " " + a.normal + unit + ')</small></div><span class="z ' + (a.z < 0 ? "neg" : "") + '">' + sgn(a.z, 1) + "σ</span></div>";
            }).join("") : '<div class="anomaly"><span class="zi">✅</span><div><b>' + esc(tx("anom_none")) + "</b></div></div>";
        } else {
            const mA = c.compare.monthly.a, mB = c.compare.monthly.b;
            mkChart("climate", "climateIntelChart", { data: { labels: months, datasets: [
                { type: "bar", label: tx("chart_a") + " · " + tx("chart_rain_mm"), data: mA.rain, yAxisID: "y1", backgroundColor: "rgba(93,120,255,.4)", borderRadius: 4 },
                { type: "bar", label: tx("chart_b") + " · " + tx("chart_rain_mm"), data: mB.rain, yAxisID: "y1", backgroundColor: "rgba(56,189,248,.65)", borderRadius: 4 },
                { type: "line", label: tx("chart_a") + " · °C", data: mA.temp, yAxisID: "y", borderColor: "#a78bfa", tension: .4, pointRadius: 3, borderWidth: 2.5, borderDash: [5, 4] },
                { type: "line", label: tx("chart_b") + " · °C", data: mB.temp, yAxisID: "y", borderColor: "#fbbf24", tension: .4, pointRadius: 3, borderWidth: 3 }] },
                options: Object.assign({}, baseOpts, { scales: { x: { grid: { display: false } }, y: { position: "left", title: { display: true, text: "°C" } }, y1: { position: "right", grid: { display: false }, title: { display: true, text: tx("mm") } } } }) });
        }
    }

    /* ------------------------------------------------------------------
       Interactive map (Leaflet + OpenWeather tiles via server proxy + RainViewer radar)
    ------------------------------------------------------------------ */
    const OWM = { rain: "precipitation_new", wind: "wind_new", temp: "temp_new", clouds: "clouds_new" };
    const LEGENDS = {
        rain: { k: "lg_rain", g: "linear-gradient(90deg,#8be9fd,#50fa7b,#f1fa8c,#ffb86c,#ff5555,#b4009e)", l: ["0", "1", "5", "20", "50+"] },
        wind: { k: "lg_wind", g: "linear-gradient(90deg,#ffffff,#aec3ec,#6e8fe8,#6a4dc4,#a02e6b,#e63b1c)", l: ["0", "5", "10", "15", "25+"] },
        temp: { k: "lg_temp", g: "linear-gradient(90deg,#8a6cf0,#3b82f6,#38bdf8,#a3e635,#fbbf24,#f97316,#ef4444)", l: ["-20", "0", "15", "30", "45"] },
        clouds: { k: "lg_clouds", g: "linear-gradient(90deg,rgba(255,255,255,0),rgba(255,255,255,.5),#fff)", l: ["0", "50", "100"] },
        radar: { k: "lg_radar", g: "linear-gradient(90deg,#00d4ff,#00ff6a,#ffe600,#ff8a00,#ff1f1f,#d100ff)", l: ["light", "", "heavy"] },
    };
    S.layer = "rain"; S.overlay = null; S.radar = { frames: [], layers: [], idx: 0, timer: null, host: "", ready: false };

    function renderLegend(note) {
        const el = $("mapLegend"); if (!el) return;
        const L = LEGENDS[S.layer];
        el.innerHTML = "<b>" + esc(tx(L.k)) + '</b><div class="lgb" style="background:' + L.g + '"></div><div class="lgl">' + L.l.map((x) => "<span>" + esc(x) + "</span>").join("") + "</div>" + (note ? '<div class="note">' + esc(note) + "</div>" : "");
    }
    function initMap() {
        if (S.map || !window.L || !$("weatherMap")) return;
        S.map = L.map("weatherMap", { zoomControl: true, worldCopyJump: true, minZoom: 3, scrollWheelZoom: false }).setView(S.lat != null ? [S.lat, S.lon] : [20.6, 79], S.lat != null ? 7 : 5);
        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { subdomains: "abcd", maxZoom: 18, attribution: "&copy; OpenStreetMap &copy; CARTO" }).addTo(S.map);
        S.map.createPane("overlayPane2"); S.map.getPane("overlayPane2").style.zIndex = 350;
        S.map.on("click", onMapClick);
        S.map.on("popupopen", (e) => { const b = e.popup.getElement().querySelector(".pop-btn"); if (b) b.addEventListener("click", () => { window.scrollTo({ top: 0, behavior: "smooth" }); window.WG.loadCoordinates(b.dataset.lat, b.dataset.lon, b.dataset.name); S.map.closePopup(); }); });
        const mapEl = $("weatherMap");
        mapEl.addEventListener("click", () => S.map.scrollWheelZoom.enable(), { once: true });
        moveMap(true);
        setLayer(S.layer);
        setTimeout(() => S.map.invalidateSize(), 250);
    }
    function moveMap(initial) {
        if (!S.map || S.lat == null) return;
        if (S.marker) S.marker.setLatLng([S.lat, S.lon]);
        else S.marker = L.marker([S.lat, S.lon], { icon: L.divIcon({ className: "", html: '<div class="wg-pin"></div>', iconSize: [22, 22], iconAnchor: [11, 11] }), keyboard: false }).addTo(S.map).bindTooltip(S.name || "", { direction: "top", offset: [0, -10] });
        if (S.marker.getTooltip()) S.marker.setTooltipContent(S.name || "");
        if (!initial) S.map.flyTo([S.lat, S.lon], Math.max(S.map.getZoom(), 7), { duration: reduce ? 0 : 1.6 });
    }
    function clearOverlay() {
        if (S.overlay) { S.map.removeLayer(S.overlay); S.overlay = null; }
        stopRadar(); S.radar.layers.forEach((l) => S.map.removeLayer(l)); S.radar.layers = [];
        $("radarBar").hidden = true;
    }
    function setLayer(name) {
        S.layer = name;
        qa("#mapLayers button").forEach((b) => b.classList.toggle("on", b.dataset.layer === name));
        if (!S.map) { renderLegend(); return; }
        clearOverlay(); renderLegend();
        if (name === "radar") { loadRadar(); return; }
        S.overlay = L.tileLayer("/map-tile/" + OWM[name] + "/{z}/{x}/{y}.png", { opacity: .8, maxNativeZoom: 8, maxZoom: 18, pane: "overlayPane2" }).addTo(S.map);
    }
    async function loadRadar() {
        try {
            const res = await fetch("https://api.rainviewer.com/public/weather-maps.json");
            const j = await res.json();
            if (S.layer !== "radar") return;
            const frames = ((j.radar && j.radar.past) || []).concat((j.radar && j.radar.nowcast) || []);
            if (!frames.length) throw new Error("no frames");
            const R = S.radar; R.frames = frames; R.host = j.host || "https://tilecache.rainviewer.com"; R.idx = frames.length - 1;
            R.layers = frames.map((f) => L.tileLayer(R.host + f.path + "/256/{z}/{x}/{y}/2/1_1.png", { opacity: 0, maxNativeZoom: 7, maxZoom: 18, pane: "overlayPane2" }).addTo(S.map));
            const sl = $("radarSlider"); sl.max = frames.length - 1; sl.value = R.idx;
            $("radarBar").hidden = false;
            showFrame(R.idx);
            if (!reduce) startRadar();
        } catch (_) { renderLegend(tx("radar_fail")); }
    }
    function showFrame(i) {
        const R = S.radar; if (!R.layers.length) return;
        R.layers.forEach((l, k) => l.setOpacity(k === i ? .75 : 0));
        R.idx = i; $("radarSlider").value = i;
        const t = new Date(R.frames[i].time * 1000);
        $("radarTime").textContent = t.toLocaleTimeString(LOCALE[lang()], { hour: "2-digit", minute: "2-digit" });
    }
    function startRadar() {
        stopRadar(); const R = S.radar; $("radarPlay").textContent = "⏸";
        R.timer = setInterval(() => showFrame((R.idx + 1) % R.layers.length), 700);
    }
    function stopRadar() { if (S.radar.timer) { clearInterval(S.radar.timer); S.radar.timer = null; } const b = $("radarPlay"); if (b) b.textContent = "▶"; }

    async function onMapClick(e) {
        const { lat, lng } = e.latlng, la = lat.toFixed(4), lo = lng.toFixed(4);
        const popup = L.popup({ closeButton: true, autoPan: true }).setLatLng(e.latlng).setContent("<div>" + esc(tx("map_loading")) + "</div>").openOn(S.map);
        try {
            const [w, r] = await Promise.all([
                fetch("/weather-coordinates?lat=" + la + "&lon=" + lo + "&location=" + encodeURIComponent("Selected location")).then((x) => x.json()),
                fetch("/reverse?lat=" + la + "&lon=" + lo).then((x) => x.json()).catch(() => ({})),
            ]);
            if (w.error) throw new Error(w.error);
            const name = r.name || "Selected location", label = r.label || name;
            popup.setContent('<div class="pop-title">📍 ' + esc(label) + '</div><div class="pop-temp">' + Math.round(w.temperature) + "°C</div><div>" + esc(w.description || "") + " · 💧 " + w.humidity + '%</div><button type="button" class="pop-btn" data-lat="' + la + '" data-lon="' + lo + '" data-name="' + esc(label) + '">' + esc(tx("map_view")) + "</button>");
        } catch (_) { popup.setContent("<div>" + esc(tx("map_fail")) + "</div>"); }
    }

    /* ------------------------------------------------------------------
       Wiring
    ------------------------------------------------------------------ */
    function wire() {
        document.documentElement.style.scrollBehavior = reduce ? "auto" : "smooth";
        applyStatic();

        const ls = $("languageSelect");
        if (ls) ls.addEventListener("change", () => { setTimeout(() => { applyStatic(); if (S.lat != null) { loadOverview(); if (S.climate) renderClimate(); if (S.layer === "radar") showFrame(S.radar.idx); } }, 60); });

        $("cropSelect").addEventListener("change", (e) => { S.crop = e.target.value; loadOverview(); });
        $("farmAIBtn").addEventListener("click", farmAI);
        $("climateYears").addEventListener("change", () => { S.climate = null; S.climateKey = ""; ensureClimate(); });
        $("climateTabs").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; S.climView = b.dataset.view; qa("#climateTabs button").forEach((x) => x.classList.toggle("on", x === b)); renderClimate(); });
        $("mapLayers").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setLayer(b.dataset.layer); });
        $("radarPlay").addEventListener("click", () => { S.radar.timer ? stopRadar() : startRadar(); });
        $("radarSlider").addEventListener("input", (e) => { stopRadar(); showFrame(Number(e.target.value)); });
        $("explainSpeak").addEventListener("click", (e) => speakAloud(S.explain, e.currentTarget));

        const speak = $("speakToggle");
        if (speak) speak.addEventListener("click", () => {
            const on = !speak.classList.contains("on");
            speak.classList.toggle("on", on); speak.classList.toggle("off", !on);
            speak.textContent = on ? "🔊" : "🔇"; speak.setAttribute("aria-pressed", on);
            if (window.WG) window.WG.setSpeech(on);
        });

        const out = $("logoutBtn");
        if (out) out.addEventListener("click", async () => { try { await fetch("/auth/logout", { method: "POST" }); } catch (_) { /* ignore */ } window.location.href = "/login"; });

        /* reveal + lazy init + nav highlight */
        const secs = qa(".fx-section");
        secs.forEach((s) => s.classList.add("fx-reveal"));
        if ("IntersectionObserver" in window) {
            const io = new IntersectionObserver((entries) => entries.forEach((en) => {
                const id = en.target.id;
                if (en.isIntersecting) {
                    en.target.classList.add("in");
                    if (id === "climateSection") { S.climVisible = true; ensureClimate(); }
                    if (id === "mapSection") { S.mapVisible = true; initMap(); }
                }
            }), { threshold: [0, 0.15], rootMargin: "0px 0px -10% 0px" });
            secs.forEach((s) => io.observe(s));
        } else { secs.forEach((s) => s.classList.add("in")); S.climVisible = true; initMap(); }

        /* highlight exactly one nav link: the last section whose top has passed the sticky bars */
        const links = qa(".feature-nav a");
        let ticking = false;
        function markActive() {
            ticking = false;
            let current = null;
            secs.forEach((sec) => { if (sec.getBoundingClientRect().top <= 230) current = sec.id; });
            const last = secs[secs.length - 1].getBoundingClientRect();
            if (last.bottom < 0) current = null;
            links.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === "#" + current));
        }
        window.addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(markActive); } }, { passive: true });
        markActive();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire); else wire();
})();
