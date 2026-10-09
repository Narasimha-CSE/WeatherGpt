# -*- coding: utf-8 -*-
"""WeatherGPT feature APIs: forecast intelligence, alerts, recommendations, travel,
farmer advisory, climate analytics, map tiles and reverse geocoding."""

import base64
import math
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from flask import Blueprint, Response, jsonify, request

from i18n_data import LANG_INSTRUCTION, tr

bp = Blueprint("features", __name__)

_ctx = {"groq": None, "weather_key": None}


def init_features(app, groq_fn, weather_key):
    """Register blueprint. groq_fn(prompt) -> (text, error)."""
    _ctx["groq"] = groq_fn
    _ctx["weather_key"] = weather_key
    app.register_blueprint(bp)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_cache = {}


def cache_get(key, ttl):
    item = _cache.get(key)
    if item and time.time() - item[0] < ttl:
        return item[1]
    return None


def cache_set(key, value):
    if len(_cache) > 300:
        for k in list(_cache)[:100]:
            _cache.pop(k, None)
    _cache[key] = (time.time(), value)
    return value


def norm_lang(value):
    v = str(value or "en").strip().lower()
    if v.startswith("te"):
        return "te"
    if v.startswith("hi"):
        return "hi"
    return "en"


def num(arr, i, default=0.0):
    try:
        v = arr[i]
        return default if v is None else float(v)
    except (IndexError, TypeError, ValueError):
        return default


def get_coords(src):
    try:
        lat = float(src.get("lat"))
        lon = float(src.get("lon"))
    except (TypeError, ValueError):
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None
    return lat, lon


def cond_group(code):
    code = int(code or 0)
    if code in (0, 1):
        return "clear"
    if code == 2:
        return "partly"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 57:
        return "drizzle"
    if 61 <= code <= 67:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if 80 <= code <= 82:
        return "showers"
    if code >= 95:
        return "storm"
    return "cloudy"


def fmt_hour(h):
    return "%02d:00" % (int(h) % 24)


def span(hours):
    """'17:00–20:00' for a list of hourly dicts."""
    if not hours:
        return ""
    return "%s–%s" % (fmt_hour(hours[0]["hour"]), fmt_hour(hours[-1]["hour"] + 1))


# ---------------------------------------------------------------------------
# Open-Meteo bundle (hourly + daily)
# ---------------------------------------------------------------------------

OM_FORECAST = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = ("temperature_2m,apparent_temperature,relative_humidity_2m,precipitation_probability,"
               "precipitation,weather_code,visibility,wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
               "uv_index,cloud_cover,is_day")
DAILY_VARS = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
              "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,uv_index_max,"
              "et0_fao_evapotranspiration,sunrise,sunset")


def fetch_bundle(lat, lon):
    key = ("bundle", round(lat, 2), round(lon, 2))
    hit = cache_get(key, 600)
    if hit:
        return hit

    params = {"latitude": lat, "longitude": lon, "hourly": HOURLY_VARS, "daily": DAILY_VARS,
              "timezone": "auto", "forecast_days": 7, "wind_speed_unit": "kmh"}
    resp = requests.get(OM_FORECAST, params=params, timeout=15)
    resp.raise_for_status()
    j = resp.json()
    h, d = j.get("hourly", {}), j.get("daily", {})
    times = h.get("time", [])
    offset = int(j.get("utc_offset_seconds", 0) or 0)
    now_local = datetime.now(timezone.utc) + timedelta(seconds=offset)
    now_key = now_local.strftime("%Y-%m-%dT%H:00")
    start = times.index(now_key) if now_key in times else 0

    hourly = []
    for i in range(start, min(start + 72, len(times))):
        t = times[i]
        hourly.append({
            "time": t, "date": t[:10], "hour": int(t[11:13]),
            "temp": num(h.get("temperature_2m"), i), "feels": num(h.get("apparent_temperature"), i),
            "hum": num(h.get("relative_humidity_2m"), i), "pp": num(h.get("precipitation_probability"), i),
            "mm": num(h.get("precipitation"), i), "code": int(num(h.get("weather_code"), i)),
            "vis": num(h.get("visibility"), i, 10000) / 1000.0, "wind": num(h.get("wind_speed_10m"), i),
            "gust": num(h.get("wind_gusts_10m"), i), "wdir": num(h.get("wind_direction_10m"), i),
            "uv": num(h.get("uv_index"), i), "cloud": num(h.get("cloud_cover"), i),
            "day": int(num(h.get("is_day"), i, 1)),
        })

    daily = []
    for i, date in enumerate(d.get("time", [])):
        daily.append({
            "date": date, "tmax": num(d.get("temperature_2m_max"), i), "tmin": num(d.get("temperature_2m_min"), i),
            "pp": num(d.get("precipitation_probability_max"), i), "mm": num(d.get("precipitation_sum"), i),
            "wind": num(d.get("wind_speed_10m_max"), i), "gust": num(d.get("wind_gusts_10m_max"), i),
            "uv": num(d.get("uv_index_max"), i), "et0": num(d.get("et0_fao_evapotranspiration"), i, 4.0),
            "code": int(num(d.get("weather_code"), i)),
            "sunrise": (d.get("sunrise") or [""] * (i + 1))[i][11:16] if d.get("sunrise") else "",
            "sunset": (d.get("sunset") or [""] * (i + 1))[i][11:16] if d.get("sunset") else "",
        })

    bundle = {"hourly": hourly, "daily": daily, "offset": offset, "today": now_local.strftime("%Y-%m-%d")}
    return cache_set(key, bundle)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

LEVEL_RANK = {"extreme": 0, "warning": 1, "advisory": 2, "ok": 3}


def compute_alerts(b, lang):
    h24 = b["hourly"][:24]
    if not h24:
        return []
    alerts = []

    def add(level, kind, hours, **kw):
        alerts.append({"id": kind, "level": level, "title": tr(lang, kind + "_t"),
                       "message": tr(lang, kind + "_m", when=span(hours) if hours else "", **kw)})

    storm = [x for x in h24 if x["code"] in (95, 96, 99)]
    if storm:
        add("extreme" if any(x["code"] == 99 for x in storm) else "warning", "th", storm)

    total = sum(x["mm"] for x in h24)
    intense = [x for x in h24 if x["mm"] >= 7.6]
    if total >= 115.6:
        add("extreme", "rain", [x for x in h24 if x["mm"] > 0], val=round(total))
    elif total >= 64.5 or intense:
        add("warning", "rain", intense or [x for x in h24 if x["mm"] > 0], val=round(total))
    elif total >= 15:
        add("advisory", "rain", [x for x in h24 if x["mm"] > 0.5], val=round(total))

    peak = max(x["temp"] for x in h24)
    hot = [x for x in h24 if x["temp"] >= min(peak, 37) - 0.01 and x["temp"] >= 37]
    if peak >= 45:
        add("extreme", "heat", hot, val=round(peak))
    elif peak >= 40:
        add("warning", "heat", hot, val=round(peak))
    elif peak >= 37 or max(x["feels"] for x in h24) >= 41:
        add("advisory", "heat", hot, val=round(peak))

    gust = max(x["gust"] for x in h24)
    windy = [x for x in h24 if x["gust"] >= 35]
    if gust >= 75:
        add("extreme", "wind", windy, val=round(gust))
    elif gust >= 50:
        add("warning", "wind", windy, val=round(gust))
    elif gust >= 35:
        add("advisory", "wind", windy, val=round(gust))

    low = min(x["temp"] for x in h24)
    if low <= 0:
        add("warning", "cold", [], val=round(low))
    elif low <= 4:
        add("advisory", "cold", [], val=round(low))

    foggy = [x for x in h24 if x["vis"] < 1.0]
    if foggy:
        add("advisory", "fog", foggy)

    uv = max(x["uv"] for x in h24)
    if uv >= 11:
        add("warning", "uv", [], val=round(uv))
    elif uv >= 8:
        add("advisory", "uv", [], val=round(uv))

    if not alerts:
        alerts.append({"id": "ok", "level": "ok", "title": tr(lang, "ok_t"), "message": tr(lang, "ok_m")})
    alerts.sort(key=lambda a: LEVEL_RANK[a["level"]])
    return alerts


# ---------------------------------------------------------------------------
# Travel intelligence
# ---------------------------------------------------------------------------

def hour_penalty(x):
    rain = min(35.0, x["pp"] * 0.2 + x["mm"] * 2.5)
    wind = min(25.0, max(0.0, x["gust"] - 25.0) * 0.6)
    f = x["feels"]
    temp = min(20.0, max(0.0, f - 35.0) * 3.0) + min(15.0, max(0.0, 5.0 - f) * 2.0)
    vis = min(20.0, max(0.0, 5.0 - x["vis"]) * 4.0)
    cond = 25.0 if x["code"] in (95, 96, 99) else (10.0 if x["code"] in (45, 48, 65, 67, 75, 82, 86) else 0.0)
    return {"rain": rain, "wind": wind, "temp": temp, "vis": vis, "cond": cond}


def score_of(x):
    return max(0.0, 100.0 - sum(hour_penalty(x).values()))


def status_of(pen):
    return "ok" if pen < 5 else ("warn" if pen < 15 else "bad")


def compute_travel(b, lang):
    hours = b["hourly"]
    if not hours:
        return {}
    nxt = hours[:3]
    score = round(sum(score_of(x) for x in nxt) / len(nxt))
    verdict_key = "v_excellent" if score >= 80 else "v_good" if score >= 60 else "v_risky" if score >= 40 else "v_avoid"

    six = hours[:6]
    pen = hour_penalty({
        "pp": max(x["pp"] for x in six), "mm": sum(x["mm"] for x in six), "gust": max(x["gust"] for x in six),
        "feels": hours[0]["feels"], "vis": min(x["vis"] for x in six),
        "code": max((x["code"] for x in six), key=lambda c: (c in (95, 96, 99), c in (45, 48, 65, 67, 82), c)),
    })
    factors = [
        {"key": "rain", "status": status_of(pen["rain"]), "value": round(max(x["pp"] for x in six)), "extra": round(sum(x["mm"] for x in six), 1)},
        {"key": "wind", "status": status_of(pen["wind"]), "value": round(max(x["gust"] for x in six))},
        {"key": "temp", "status": status_of(pen["temp"]), "value": round(hours[0]["feels"])},
        {"key": "vis", "status": status_of(pen["vis"]), "value": round(min(x["vis"] for x in six), 1)},
        {"key": "cond", "status": status_of(pen["cond"]), "value": cond_group(max((x["code"] for x in six), key=lambda c: (c in (95, 96, 99), c)))},
    ]

    window_len = 3
    scored = []
    for i in range(0, max(0, min(24, len(hours)) - window_len + 1)):
        w = hours[i:i + window_len]
        avg = sum(score_of(x) for x in w) / window_len
        daytime = all(5 <= x["hour"] <= 21 for x in w)
        scored.append((avg, daytime, w))
    pool = [s for s in scored if s[1]] or scored
    best = max(pool, key=lambda s: (s[0], -hours.index(s[2][0]))) if pool else None
    worst = min(scored, key=lambda s: s[0]) if scored else None

    out = {"score": score, "verdict": tr(lang, verdict_key), "level": verdict_key[2:], "factors": factors}
    out["summary"] = tr(lang, "tr_sum", score=score, verdict=out["verdict"])
    if best:
        out["best"] = {"when": span(best[2]), "score": round(best[0]), "text": tr(lang, "tr_best", when=span(best[2]), score=round(best[0]))}
    if worst and worst[0] < 60:
        out["avoid"] = {"when": span(worst[2]), "score": round(worst[0]), "text": tr(lang, "tr_avoid", when=span(worst[2]))}
    return out


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def compute_recommendations(b, lang, travel):
    h = b["hourly"]
    now = h[0]
    h12 = h[:12]
    daily0 = b["daily"][0] if b["daily"] else {"uv": now["uv"]}
    rain_p = max(x["pp"] for x in h12)
    rain_hours = [x for x in h12 if x["pp"] >= 50 or x["mm"] >= 0.5]
    uv = max(daily0.get("uv", 0), now["uv"])
    feels = now["feels"]

    # clothing
    if feels >= 35:
        c = ["c_hot"]
    elif feels >= 28:
        c = ["c_warm"]
    elif feels >= 20:
        c = ["c_mild"]
    elif feels >= 12:
        c = ["c_cool"]
    else:
        c = ["c_cold"]
    if rain_p >= 50:
        c.append("c_rain")
    clothing = [tr(lang, k) for k in c]

    # umbrella
    if rain_p >= 60:
        umb = [tr(lang, "u_yes", p=round(rain_p), when=span(rain_hours))]
    elif rain_p >= 30:
        umb = [tr(lang, "u_maybe", p=round(rain_p))]
    else:
        umb = [tr(lang, "u_no", p=round(rain_p))]
    if uv >= 6 and rain_p < 60:
        umb.append(tr(lang, "u_sun"))

    # outdoor
    ok_hours = [x for x in h[:24] if 6 <= x["hour"] <= 20 and x["pp"] < 30 and x["mm"] == 0 and x["feels"] <= 34 and x["gust"] < 35]
    score_now = score_of(now)
    if score_now >= 75 and now["feels"] <= 34:
        out = [tr(lang, "o_good")]
    elif score_now >= 50:
        out = [tr(lang, "o_ok")]
    else:
        out = [tr(lang, "o_poor")]
    if ok_hours:
        best = min(ok_hours, key=lambda x: x["feels"])
        i = h.index(best)
        run = [best]
        for x in h[i + 1:i + 3]:
            if x in ok_hours:
                run.append(x)
        out.append(tr(lang, "o_best", when=span(run)))

    # sun protection
    key = "s_low" if uv < 3 else "s_mod" if uv < 6 else "s_high" if uv < 8 else "s_vhigh" if uv < 11 else "s_ext"
    sun = [tr(lang, key, uv=round(uv, 1))]

    # health
    health = []
    if feels >= 35 or now["temp"] >= 35:
        health.append(tr(lang, "h_heat"))
    if now["hum"] >= 80:
        health.append(tr(lang, "h_humid"))
    if feels <= 12:
        health.append(tr(lang, "h_cold"))
    if rain_p >= 60:
        health.append(tr(lang, "h_rain"))
    if not health:
        health.append(tr(lang, "h_ok"))

    travel_tips = [travel.get("summary", "")]
    if travel.get("best"):
        travel_tips.append(travel["best"]["text"])

    return [
        {"id": "clothing", "icon": "👕", "tips": clothing},
        {"id": "umbrella", "icon": "☂️", "tips": umb},
        {"id": "outdoor", "icon": "🏃", "tips": out},
        {"id": "sun", "icon": "🧴", "tips": sun, "uv": round(uv, 1)},
        {"id": "health", "icon": "❤️", "tips": health},
        {"id": "travel", "icon": "🚗", "tips": [t for t in travel_tips if t]},
    ]


# ---------------------------------------------------------------------------
# Farmer advisory
# ---------------------------------------------------------------------------

CROPS = {"rice": 1.2, "cotton": 1.0, "chilli": 0.9, "maize": 1.0, "groundnut": 0.9,
         "tobacco": 0.9, "banana": 1.1, "sugarcane": 1.2, "tomato": 1.0, "wheat": 1.0}


def day_label(b, date, lang):
    today = b["today"]
    tomorrow = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    if date == today:
        return tr(lang, "day_today")
    if date == tomorrow:
        return tr(lang, "day_tomorrow")
    return date[5:]


def compute_farm(b, lang, crop):
    kc = CROPS.get(crop, 1.0)
    h, d = b["hourly"], b["daily"]
    h48, h24 = h[:48], h[:24]
    cards = []

    # irrigation
    rain48 = sum(x["mm"] for x in h48)
    rain72 = sum(x["mm"] for x in d[:3])
    et3 = sum(x["et0"] for x in d[:3]) * kc
    balance = rain72 - et3
    if rain48 >= 10:
        irr = ("good", tr(lang, "i_skip", mm=round(rain48)))
    elif balance <= -8:
        irr = ("caution", tr(lang, "i_now", mm=round(-balance)))
    else:
        irr = ("good", tr(lang, "i_light"))
    cards.append({"id": "irrigation", "icon": "💧", "status": irr[0], "text": irr[1]})

    # spraying windows
    ok = []
    for i, x in enumerate(h48):
        nxt = h48[i + 1:i + 4]
        good = (x["wind"] <= 15 and x["gust"] <= 28 and x["pp"] <= 25 and x["mm"] == 0 and x["temp"] <= 33
                and 5 <= x["hour"] <= 19 and all(y["mm"] == 0 and y["pp"] <= 40 for y in nxt))
        ok.append(good)
    runs, cur = [], []
    for i, g in enumerate(ok):
        if g:
            cur.append(h48[i])
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
    if len(cur) >= 2:
        runs.append(cur)
    windows = []
    top = sorted(runs, key=lambda r: (-len(r), r[0]["time"]))[:2]
    for r in sorted(top, key=lambda r: r[0]["time"]):
        windows.append("%s %s" % (day_label(b, r[0]["date"], lang), span(r)))
    if windows:
        spray = ("good", tr(lang, "sp_window", when=" · ".join(windows)) + " " + tr(lang, "sp_tip"))
    else:
        spray = ("alert", tr(lang, "sp_none"))
    cards.append({"id": "spraying", "icon": "🧪", "status": spray[0], "text": spray[1], "windows": windows})

    # pest & disease
    avg_h = sum(x["hum"] for x in h24) / len(h24)
    avg_t = sum(x["temp"] for x in h24) / len(h24)
    wet = max(x["pp"] for x in h24) >= 50 or sum(x["mm"] for x in h24) > 2
    if avg_h >= 85 and 20 <= avg_t <= 32 and wet:
        pest = ("alert", tr(lang, "p_high", h=round(avg_h)))
    elif avg_h >= 75 and 18 <= avg_t <= 34:
        pest = ("caution", tr(lang, "p_med"))
    elif avg_t >= 32 and avg_h <= 55:
        pest = ("caution", tr(lang, "p_suck"))
    else:
        pest = ("good", tr(lang, "p_low"))
    cards.append({"id": "pest", "icon": "🐛", "status": pest[0], "text": pest[1]})

    # harvest
    run = 0
    for x in d[:5]:
        if x["mm"] < 2 and x["pp"] < 40:
            run += 1
        else:
            break
    rain_soon = next((x for x in h24 if x["pp"] >= 60 or x["mm"] >= 1), None)
    if run >= 3:
        hv = ("good", tr(lang, "hv_good", days=run))
    elif rain_soon:
        hv = ("alert", tr(lang, "hv_rain", when="%s %s" % (day_label(b, rain_soon["date"], lang), fmt_hour(rain_soon["hour"]))))
    else:
        hv = ("caution", tr(lang, "hv_wait"))
    cards.append({"id": "harvest", "icon": "🌾", "status": hv[0], "text": hv[1]})

    # protection
    msgs, status = [], "good"
    gust = max(x["gust"] for x in h24)
    rain24 = sum(x["mm"] for x in h24)
    tmax = max(x["temp"] for x in h24)
    tmin = min(x["temp"] for x in h24)
    if any(x["code"] in (95, 96, 99) for x in h24):
        msgs.append(tr(lang, "pr_storm")); status = "alert"
    if gust >= 45:
        msgs.append(tr(lang, "pr_wind", g=round(gust))); status = "alert" if gust >= 60 else max(status, "caution", key=["good", "caution", "alert"].index)
    if rain24 >= 50:
        msgs.append(tr(lang, "pr_rain")); status = "alert"
    if tmax >= 40:
        msgs.append(tr(lang, "pr_heat", t=round(tmax))); status = "alert" if tmax >= 43 else max(status, "caution", key=["good", "caution", "alert"].index)
    if tmin <= 5:
        msgs.append(tr(lang, "pr_cold", t=round(tmin))); status = max(status, "caution", key=["good", "caution", "alert"].index)
    if not msgs:
        msgs.append(tr(lang, "pr_ok"))
    cards.append({"id": "protection", "icon": "🛡️", "status": status, "text": " ".join(msgs)})

    return {"crop": crop, "cards": cards, "balance": round(balance, 1), "rain48": round(rain48, 1)}


# ---------------------------------------------------------------------------
# Overview payload
# ---------------------------------------------------------------------------

def build_overview(lat, lon, lang, crop):
    b = fetch_bundle(lat, lon)
    if not b["hourly"]:
        raise ValueError("No forecast data available for this location.")
    now = b["hourly"][0]
    travel = compute_travel(b, lang)
    return {
        "lat": lat, "lon": lon, "language": lang, "offset": b["offset"],
        "now": {"temp": now["temp"], "feels": now["feels"], "hum": now["hum"], "wind": now["wind"], "gust": now["gust"],
                "wdir": now["wdir"], "uv": max(now["uv"], 0), "uv_max": b["daily"][0]["uv"] if b["daily"] else now["uv"],
                "pp": now["pp"], "vis": now["vis"], "cloud": now["cloud"], "group": cond_group(now["code"]), "day": now["day"]},
        "hourly": [dict(x, group=cond_group(x["code"])) for x in b["hourly"][:48]],
        "daily": [dict(x, group=cond_group(x["code"])) for x in b["daily"]],
        "alerts": compute_alerts(b, lang),
        "recommendations": compute_recommendations(b, lang, travel),
        "travel": travel,
        "farm": compute_farm(b, lang, crop),
        "summary": fallback_summary(b, lang),
    }


def fallback_summary(b, lang):
    d = b["daily"]
    if not d:
        return ""
    t0 = d[0]
    later = d[1:4]
    trend = "trend_flat"
    if later:
        avg = sum(x["tmax"] for x in later) / len(later)
        trend = "trend_up" if avg - t0["tmax"] >= 2 else "trend_down" if t0["tmax"] - avg >= 2 else "trend_flat"
    return tr(lang, "f_sum", tmin=round(t0["tmin"]), tmax=round(t0["tmax"]), p=round(t0["pp"]), trend=tr(lang, trend))


@bp.route("/api/overview")
def api_overview():
    lat, lon = get_coords(request.args)
    if lat is None:
        return jsonify({"error": "Valid lat and lon are required."}), 400
    lang = norm_lang(request.args.get("language"))
    crop = request.args.get("crop", "rice").lower()
    crop = crop if crop in CROPS else "rice"
    try:
        return jsonify(build_overview(lat, lon, lang, crop))
    except Exception as e:  # network / parsing
        return jsonify({"error": "Unable to load forecast intelligence: %s" % e}), 502


# ---------------------------------------------------------------------------
# AI helpers (forecast explanation + crop advice) and chat context
# ---------------------------------------------------------------------------

def facts_text(b, place):
    d = b["daily"]
    h = b["hourly"]
    lines = ["Location: %s" % place]
    if h:
        n = h[0]
        lines.append("Now: %.0f°C (feels %.0f°C), humidity %.0f%%, wind %.0f km/h gusts %.0f km/h, UV %.1f, rain chance %.0f%%." %
                     (n["temp"], n["feels"], n["hum"], n["wind"], n["gust"], n["uv"], n["pp"]))
        nxt = []
        for x in h[:24:3]:
            nxt.append("%s %s %.0f°C rain %.0f%% (%.1f mm)" % (x["date"][5:], fmt_hour(x["hour"]), x["temp"], x["pp"], x["mm"]))
        lines.append("Next 24h (every 3h): " + "; ".join(nxt))
    for i, x in enumerate(d[:7]):
        lines.append("Day %d (%s): %.0f–%.0f°C, rain chance %.0f%%, %.1f mm, max wind %.0f km/h, %s." %
                     (i, x["date"], x["tmin"], x["tmax"], x["pp"], x["mm"], x["wind"], cond_group(x["code"])))
    return "\n".join(lines)


def forecast_context(lat, lon, place=""):
    """Compact forecast text injected into the chat prompt so the AI can answer
    'will it rain today?' and 'what about tomorrow?'."""
    try:
        return facts_text(fetch_bundle(float(lat), float(lon)), place or "selected location")
    except Exception:
        return ""


@bp.route("/api/forecast-explain", methods=["POST"])
def api_forecast_explain():
    data = request.get_json(silent=True) or {}
    lat, lon = get_coords(data)
    if lat is None:
        return jsonify({"error": "Valid lat and lon are required."}), 400
    lang = norm_lang(data.get("language"))
    place = str(data.get("location", "this location"))[:120]
    try:
        b = fetch_bundle(lat, lon)
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    fallback = fallback_summary(b, lang)
    groq = _ctx["groq"]
    if not groq:
        return jsonify({"explanation": fallback, "source": "rules"})
    prompt = ("You are WeatherGPT. %s\nExplain this forecast to an ordinary person in 4 short sentences: "
              "what the next 24 hours look like (including rain timing), the temperature trend over the week, "
              "and one practical tip. No markdown, no bullet points.\n\n%s") % (LANG_INSTRUCTION[lang], facts_text(b, place))
    text, err = groq(prompt)
    if err or not text:
        return jsonify({"explanation": fallback, "source": "rules"})
    return jsonify({"explanation": text, "source": "ai"})


@bp.route("/api/farmer-ai", methods=["POST"])
def api_farmer_ai():
    data = request.get_json(silent=True) or {}
    lat, lon = get_coords(data)
    if lat is None:
        return jsonify({"error": "Valid lat and lon are required."}), 400
    lang = norm_lang(data.get("language"))
    crop = str(data.get("crop", "rice")).lower()
    crop = crop if crop in CROPS else "rice"
    place = str(data.get("location", "this location"))[:120]
    stage = str(data.get("stage", "")).strip()[:40]
    try:
        b = fetch_bundle(lat, lon)
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    farm = compute_farm(b, "en", crop)
    rules = "\n".join("- %s: %s" % (c["id"], c["text"]) for c in farm["cards"])
    groq = _ctx["groq"]
    if not groq:
        return jsonify({"error": "AI service unavailable."}), 503
    prompt = ("You are WeatherGPT's agriculture advisor for Indian farmers. %s\n"
              "Crop: %s%s. Give 5 short, practical bullet points (start each with '-') covering irrigation, "
              "spraying, pest/disease, harvest and crop protection, specific to this crop and the weather below. "
              "No markdown headings.\n\nWeather facts:\n%s\n\nRule-based checks:\n%s") % (
        LANG_INSTRUCTION[lang], crop, (" (growth stage: %s)" % stage) if stage else "", facts_text(b, place), rules)
    text, err = groq(prompt)
    if err or not text:
        return jsonify({"error": "AI service unavailable."}), 502
    return jsonify({"advice": text})


# ---------------------------------------------------------------------------
# Climate intelligence (Open-Meteo archive)
# ---------------------------------------------------------------------------

OM_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def linreg(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0


def mean(v):
    return sum(v) / len(v) if v else 0.0


def std(v):
    if len(v) < 3:
        return 0.0
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def compute_climate(lat, lon, years):
    key = ("climate", round(lat, 1), round(lon, 1), years)
    hit = cache_get(key, 6 * 3600)
    if hit:
        return hit

    today = datetime.now(timezone.utc).date()
    last_year = today.year - 1
    first_year = last_year - years + 1
    params = {"latitude": lat, "longitude": lon, "start_date": "%d-01-01" % first_year, "end_date": "%d-12-31" % last_year,
              "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum", "timezone": "auto"}
    resp = requests.get(OM_ARCHIVE, params=params, timeout=40)
    resp.raise_for_status()
    daily = resp.json().get("daily", {})
    dates = daily.get("time", [])
    if not dates:
        raise ValueError("No historical data returned.")

    months, yearly = {}, {}
    for i, ds in enumerate(dates):
        y, m = int(ds[:4]), int(ds[5:7])
        tm = daily["temperature_2m_mean"][i]
        tx = daily["temperature_2m_max"][i]
        pr = daily["precipitation_sum"][i]
        mo = months.setdefault((y, m), {"t": [], "r": 0.0})
        ye = yearly.setdefault(y, {"t": [], "r": 0.0, "hot": 0, "wet": 0, "tmax": -99.0})
        if tm is not None:
            mo["t"].append(tm); ye["t"].append(tm)
        if pr is not None:
            mo["r"] += pr; ye["r"] += pr
            if pr >= 2.5:
                ye["wet"] += 1
        if tx is not None:
            ye["tmax"] = max(ye["tmax"], tx)
            if tx >= 40:
                ye["hot"] += 1

    monthly = [{"ym": "%d-%02d" % k, "year": k[0], "month": k[1], "temp": round(mean(v["t"]), 2), "rain": round(v["r"], 1)}
               for k, v in sorted(months.items())]
    ylist = [{"year": y, "temp": round(mean(v["t"]), 2), "rain": round(v["r"], 1), "hot_days": v["hot"],
              "rainy_days": v["wet"], "tmax": round(v["tmax"], 1)} for y, v in sorted(yearly.items())]

    clim_t, clim_r, sd_t, sd_r = [], [], [], []
    for m in range(1, 13):
        ts = [x["temp"] for x in monthly if x["month"] == m]
        rs = [x["rain"] for x in monthly if x["month"] == m]
        clim_t.append(round(mean(ts), 2)); clim_r.append(round(mean(rs), 1))
        sd_t.append(std(ts)); sd_r.append(std(rs))

    anomalies = []
    for x in monthly:
        m = x["month"] - 1
        if sd_t[m] > 0.05:
            z = (x["temp"] - clim_t[m]) / sd_t[m]
            if abs(z) >= 2:
                anomalies.append({"ym": x["ym"], "type": "temp", "value": x["temp"], "normal": clim_t[m], "z": round(z, 1)})
        if sd_r[m] > 1 and clim_r[m] > 5:
            z = (x["rain"] - clim_r[m]) / sd_r[m]
            if abs(z) >= 2:
                anomalies.append({"ym": x["ym"], "type": "rain", "value": x["rain"], "normal": clim_r[m], "z": round(z, 1)})
    anomalies.sort(key=lambda a: -abs(a["z"]))

    ys = [y["year"] for y in ylist]
    t_slope = linreg(ys, [y["temp"] for y in ylist]) * 10
    r_mean = mean([y["rain"] for y in ylist])
    r_slope = linreg(ys, [y["rain"] for y in ylist]) * 10
    half = len(ylist) // 2
    A, B = ylist[:half], ylist[half:]

    def period(rows):
        return {"from": rows[0]["year"], "to": rows[-1]["year"], "temp": round(mean([r["temp"] for r in rows]), 2),
                "rain": round(mean([r["rain"] for r in rows]), 1), "hot_days": round(mean([r["hot_days"] for r in rows]), 1),
                "rainy_days": round(mean([r["rainy_days"] for r in rows]), 1)}

    def month_avg(rows_years, field):
        out = []
        for m in range(1, 13):
            vals = [x[field] for x in monthly if x["month"] == m and x["year"] in rows_years]
            out.append(round(mean(vals), 2))
        return out

    pa, pb = period(A), period(B)
    ya, yb = {r["year"] for r in A}, {r["year"] for r in B}
    result = {
        "lat": lat, "lon": lon, "from": first_year, "to": last_year, "monthly": monthly, "yearly": ylist,
        "climatology": {"temp": clim_t, "rain": clim_r},
        "trend": {"temp_per_decade": round(t_slope, 2), "rain_pct_per_decade": round(r_slope / r_mean * 100, 1) if r_mean else 0.0},
        "anomalies": anomalies[:10], "anomaly_count": len(anomalies),
        "highlights": {"hottest": max(ylist, key=lambda y: y["temp"])["year"], "coldest": min(ylist, key=lambda y: y["temp"])["year"],
                       "wettest": max(ylist, key=lambda y: y["rain"])["year"], "driest": min(ylist, key=lambda y: y["rain"])["year"]},
        "compare": {"a": pa, "b": pb,
                    "delta": {"temp": round(pb["temp"] - pa["temp"], 2), "rain": round(pb["rain"] - pa["rain"], 1),
                              "rain_pct": round((pb["rain"] - pa["rain"]) / pa["rain"] * 100, 1) if pa["rain"] else 0.0,
                              "hot_days": round(pb["hot_days"] - pa["hot_days"], 1), "rainy_days": round(pb["rainy_days"] - pa["rainy_days"], 1)},
                    "monthly": {"a": {"temp": month_avg(ya, "temp"), "rain": month_avg(ya, "rain")},
                                "b": {"temp": month_avg(yb, "temp"), "rain": month_avg(yb, "rain")}}},
    }
    return cache_set(key, result)


@bp.route("/api/climate")
def api_climate():
    lat, lon = get_coords(request.args)
    if lat is None:
        return jsonify({"error": "Valid lat and lon are required."}), 400
    try:
        years = int(request.args.get("years", 10))
    except ValueError:
        years = 10
    years = years if years in (6, 10, 15, 20) else 10
    try:
        return jsonify(compute_climate(lat, lon, years))
    except Exception as e:
        return jsonify({"error": "Unable to load climate history: %s" % e}), 502


# ---------------------------------------------------------------------------
# Map tiles (proxy keeps the OpenWeather key on the server) + reverse geocode
# ---------------------------------------------------------------------------

TILE_LAYERS = {"precipitation_new", "wind_new", "temp_new", "clouds_new", "pressure_new"}
_BLANK_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


@bp.route("/map-tile/<layer>/<int:z>/<int:x>/<int:y>.png")
def map_tile(layer, z, x, y):
    key = _ctx["weather_key"]
    headers = {"Cache-Control": "public, max-age=600"}
    if layer not in TILE_LAYERS or not key or not (0 <= z <= 12):
        return Response(_BLANK_PNG, mimetype="image/png", headers=headers)
    try:
        r = requests.get("https://tile.openweathermap.org/map/%s/%d/%d/%d.png" % (layer, z, x, y),
                         params={"appid": key}, timeout=8)
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
            return Response(r.content, mimetype="image/png", headers=headers)
    except requests.RequestException:
        pass
    return Response(_BLANK_PNG, mimetype="image/png", headers={"Cache-Control": "no-store"})


@bp.route("/reverse")
def reverse_geocode():
    lat, lon = get_coords(request.args)
    if lat is None:
        return jsonify({"error": "Valid lat and lon are required."}), 400
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
                         params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 12, "addressdetails": 1},
                         headers={"User-Agent": "WeatherGPT/1.0 (reverse)", "Accept-Language": "en"}, timeout=8)
        a = (r.json() or {}).get("address", {}) or {}
        name = next((a[k] for k in ("village", "hamlet", "town", "suburb", "city_district", "city") if a.get(k)), "")
        parts = [name, a.get("county") or a.get("state_district") or "", a.get("state", ""), a.get("country", "")]
        label = ", ".join(p for p in parts if p) or "Selected location"
        return jsonify({"name": name or "Selected location", "label": label})
    except Exception:
        return jsonify({"name": "Selected location", "label": "Selected location"})
