# -*- coding: utf-8 -*-
"""
WeatherGPT
Weather intelligence, Groq AI, weather analytics,
and Brevo email OTP authentication.
"""


import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    request,
    render_template,
    send_from_directory,
)
from groq import Groq

from auth import init_auth, current_user
from features import init_features, forecast_context



# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables from this project's .env file.
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Brevo settings are loaded here to verify configuration at startup.
# The actual email delivery is handled by auth.py.
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "").strip()

print("=" * 60)
print("WeatherGPT Starting...")
print("Weather API Key Loaded:", bool(WEATHER_API_KEY))
print("Groq API Key Loaded:", bool(GROQ_API_KEY))
print("Brevo API Key Loaded:", bool(BREVO_API_KEY))
print("Brevo Sender Email Configured:", bool(BREVO_SENDER_EMAIL))
print("=" * 60)


# =========================================================
# GROQ CLIENT
# =========================================================

groq_client = None

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)


# =========================================================
# PUBLIC SEARCH-ENGINE FILES (BYPASS AUTH HOOKS)
# =========================================================

@app.before_request
def allow_public_search_files():
    if request.path == "/sitemap.xml":
        return sitemap()
    if request.path == "/robots.txt":
        return robots_txt()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html", user=current_user())


# XML sitemap for search engines
@app.route("/sitemap.xml", methods=["GET"])
def sitemap():
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://weathergpt-o42w.onrender.com/</loc>
  </url>
</urlset>'''
    response = Response(xml, status=200, mimetype="application/xml")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# Public robots.txt for search engines
@app.route("/robots.txt", methods=["GET"])
def robots_txt():
    content = """User-agent: Googlebot
Allow: 

User-agent: *
Allow: /

Sitemap: https://weathergpt-o42w.onrender.com/sitemap.xml
"""
    response = Response(content, status=200, mimetype="text/plain")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# Google Search Console verification
@app.route("/google825a0e9664b14fbc.html", methods=["GET"])
def google_verification():
    return send_from_directory(
        BASE_DIR,
        "google825a0e9664b14fbc.html",
    )


# =========================================================
# WEATHER FUNCTION - CITY SEARCH
# =========================================================

def get_weather_data(city):
    if not WEATHER_API_KEY:
        return None, "Weather API key is missing."

    if not city:
        return None, "Please enter a city name."

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "q": city,
        "appid": WEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if response.status_code != 200:
            return None, data.get(
                "message",
                "Unable to get weather information.",
            )

        weather = {
            "city": data["name"],
            "country": data["sys"]["country"],
            "latitude": data["coord"]["lat"],
            "longitude": data["coord"]["lon"],
            "temperature": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"],
            "wind_speed": data["wind"]["speed"],
            "description": data["weather"][0]["description"],
            "condition": data["weather"][0]["main"],
            "visibility": data.get("visibility", 0) / 1000,
            "clouds": data["clouds"]["all"],
            "icon": data["weather"][0].get("icon", ""),
        }

        return weather, None

    except requests.RequestException:
        return None, "Unable to connect to the weather service."
    except (KeyError, TypeError, ValueError):
        return None, "The weather service returned an invalid response."


@app.route("/weather")
def weather():
    city = request.args.get("city", "").strip()

    data, error = get_weather_data(city)

    if error:
        return jsonify({"error": error}), 400

    return jsonify(data)


# =========================================================
# LOCATION SEARCH - OPENSTREETMAP NOMINATIM
# =========================================================

def _pick_village(address):
    for key in (
        "village",
        "hamlet",
        "town",
        "suburb",
        "city_district",
        "city",
    ):
        value = address.get(key)

        if value:
            return value

    return ""


def _pick_mandal(address):
    for key in (
        "county",
        "mandal",
        "taluk",
        "tehsil",
        "subdistrict",
    ):
        value = address.get(key)

        if value:
            return value

    return ""


def _pick_district(address):
    for key in ("state_district", "district"):
        value = address.get(key)

        if value:
            return value

    return ""


@app.route("/location-search")
def location_search():
    query = request.args.get("query", "").strip()

    if not query:
        return jsonify({"error": "Please enter a location."}), 400

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 10,
        "countrycodes": "in",
    }

    headers = {
        "User-Agent": "WeatherGPT/1.0 (location-search)",
        "Accept-Language": "en",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10,
        )

        if response.status_code != 200:
            return jsonify({"results": []})

        data = response.json()

        if not data:
            return jsonify({"results": []})

        locations = []

        for item in data:
            address = item.get("address", {}) or {}

            village = _pick_village(address)
            mandal = _pick_mandal(address)
            district = _pick_district(address)

            display_name = (
                village
                or item.get("name", "")
                or item.get("display_name", "").split(",")[0].strip()
            )

            if mandal and mandal == display_name:
                mandal = ""

            if district and district in (mandal, display_name):
                district = ""

            locations.append({
                "name": display_name,
                "village": village,
                "mandal": mandal,
                "district": district,
                "state": address.get("state", ""),
                "country": address.get("country", ""),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
            })

        return jsonify({"results": locations})

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to the location search service."
        }), 502
    except ValueError:
        return jsonify({
            "error": "The location search service returned invalid data."
        }), 502


# =========================================================
# WEATHER BY EXACT COORDINATES
# =========================================================

def get_weather_data_by_coordinates(
    lat,
    lon,
    location_name="Selected Location",
):
    if not WEATHER_API_KEY:
        return None, "Weather API key is missing."

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "lat": lat,
        "lon": lon,
        "appid": WEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if response.status_code != 200:
            return None, data.get(
                "message",
                "Unable to get weather information.",
            )

        weather = {
            "city": location_name or data.get(
                "name",
                "Selected Location",
            ),
            "weather_city": data.get("name", ""),
            "country": data.get("sys", {}).get("country", ""),
            "latitude": lat,
            "longitude": lon,
            "temperature": data.get("main", {}).get("temp"),
            "feels_like": data.get("main", {}).get("feels_like"),
            "humidity": data.get("main", {}).get("humidity"),
            "pressure": data.get("main", {}).get("pressure"),
            "wind_speed": data.get("wind", {}).get("speed"),
            "description": data.get("weather", [{}])[0].get(
                "description",
                "",
            ),
            "condition": data.get("weather", [{}])[0].get("main", ""),
            "visibility": (
                data.get("visibility", 0) / 1000
                if data.get("visibility") is not None
                else None
            ),
            "clouds": data.get("clouds", {}).get("all"),
            "icon": data.get("weather", [{}])[0].get("icon", ""),
        }

        return weather, None

    except requests.RequestException:
        return None, "Unable to connect to the weather service."
    except (KeyError, TypeError, ValueError):
        return None, "The weather service returned an invalid response."


@app.route("/weather-coordinates")
def weather_coordinates():
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()
    location_name = request.args.get(
        "location",
        "Selected Location",
    ).strip()

    try:
        if not lat or not lon:
            return jsonify({"error": "Latitude and longitude are required."}), 400

        lat_f = float(lat)
        lon_f = float(lon)

        if not -90 <= lat_f <= 90 or not -180 <= lon_f <= 180:
            return jsonify({"error": "Invalid coordinates."}), 400

        data, error = get_weather_data_by_coordinates(
            lat_f,
            lon_f,
            location_name,
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify(data)

    except ValueError:
        return jsonify({"error": "Invalid coordinates."}), 400


# =========================================================
# LANGUAGE NORMALIZER
# =========================================================

def normalize_language(language):
    lang = str(language or "auto").strip().lower()

    if lang in ("te", "te-in", "telugu"):
        return "te"

    if lang in ("hi", "hi-in", "hindi"):
        return "hi"

    if lang in ("en", "en-us", "en-in", "english"):
        return "en"

    return "en"


# =========================================================
# GROQ AI ENGINE
# =========================================================

def generate_groq_response(prompt):
    if not groq_client:
        return None, "Groq API key is missing."

    try:
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are WeatherGPT, a knowledgeable weather "
                        "assistant. Provide exact answers strictly "
                        "adhering to the requested target language."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
            max_tokens=1200,
        )

        if not response.choices:
            return None, "Groq returned an empty response."

        answer = response.choices[0].message.content

        if not answer:
            return None, "Groq returned an empty response."

        return answer.strip(), None

    except Exception:
        app.logger.exception("Groq request failed.")
        return None, "AI service unavailable."


# =========================================================
# AI CHAT - CITY
# =========================================================

@app.route("/ask", methods=["POST"])
def ask():
    if not groq_client:
        return jsonify({"error": "Groq API key is missing."}), 500

    data = request.get_json(silent=True) or {}

    city = str(data.get("city", "")).strip()
    question = str(data.get("question", "")).strip()
    language = normalize_language(data.get("language", "en"))

    if not city:
        return jsonify({"error": "Please search for a city first."}), 400

    if not question:
        return jsonify({
            "error": "Please enter or speak a question."
        }), 400

    weather_data, error = get_weather_data(city)

    if error:
        return jsonify({"error": error}), 400

    lang_instr = "Answer completely in fluent English."

    if language == "te":
        lang_instr = (
            "Answer completely in fluent Telugu using Telugu script."
        )
    elif language == "hi":
        lang_instr = (
            "Answer completely in fluent Hindi using Devanagari script."
        )

    forecast_info = forecast_context(
        weather_data.get("latitude"),
        weather_data.get("longitude"),
        weather_data["city"],
    )

    prompt = f"""You are WeatherGPT. {lang_instr}
Live Weather in {weather_data['city']}: {weather_data['temperature']}°C,
Feels like {weather_data['feels_like']}°C,
Condition {weather_data['condition']} ({weather_data['description']}),
Humidity {weather_data['humidity']}%, Wind {weather_data['wind_speed']} m/s.

Forecast data:
{forecast_info}

Keep the answer short (maximum 4 sentences) and practical.
User Question: {question}"""

    answer, groq_error = generate_groq_response(prompt)

    if groq_error:
        return jsonify({"error": "AI service unavailable"}), 500

    return jsonify({
        "answer": answer,
        "weather": weather_data,
    })


# =========================================================
# AI CHAT - COORDINATES
# =========================================================

@app.route("/ask-coordinates", methods=["POST"])
def ask_coordinates():
    if not groq_client:
        return jsonify({"error": "Groq API key is missing."}), 500

    data = request.get_json(silent=True) or {}

    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid coordinates are required."}), 400

    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return jsonify({"error": "Invalid coordinates."}), 400

    loc = str(data.get("location", "Selected Location")).strip()
    question = str(data.get("question", "")).strip()
    language = normalize_language(data.get("language", "en"))

    if not question:
        return jsonify({
            "error": "Please enter or speak a question."
        }), 400

    weather_data, error = get_weather_data_by_coordinates(
        lat,
        lon,
        loc,
    )

    if error:
        return jsonify({"error": error}), 400

    lang_instr = "Answer completely in fluent English."

    if language == "te":
        lang_instr = (
            "Answer completely in fluent Telugu using Telugu script."
        )
    elif language == "hi":
        lang_instr = (
            "Answer completely in fluent Hindi using Devanagari script."
        )

    forecast_info = forecast_context(
        lat,
        lon,
        weather_data["city"],
    )

    prompt = f"""You are WeatherGPT. {lang_instr}
Live Weather in {weather_data['city']}: {weather_data['temperature']}°C,
Feels like {weather_data['feels_like']}°C,
Condition {weather_data['condition']},
Humidity {weather_data['humidity']}%,
Wind {weather_data['wind_speed']} m/s.

Forecast data:
{forecast_info}

Keep the answer short (maximum 4 sentences) and practical.
User Question: {question}"""

    answer, groq_error = generate_groq_response(prompt)

    if groq_error:
        return jsonify({"error": "AI service unavailable"}), 500

    return jsonify({
        "answer": answer,
        "weather": weather_data,
    })


# =========================================================
# SMART INSIGHTS & PRECAUTIONS - MULTILINGUAL
# =========================================================

def build_insights_prompt(weather_data, language):
    if language == "te":
        lang_directive = """
Write every bullet point in fluent Telugu using Telugu script.
Use these exact section headers:
STATUS:
ALERT:
CLOTHING:
HEALTH:
TRAVEL:
"""
    elif language == "hi":
        lang_directive = """
Write every bullet point in fluent Hindi using Devanagari script.
Use these exact section headers:
STATUS:
ALERT:
CLOTHING:
HEALTH:
TRAVEL:
"""
    else:
        lang_directive = """
Write every bullet point in clear, practical English.
Use these exact section headers:
STATUS:
ALERT:
CLOTHING:
HEALTH:
TRAVEL:
"""

    return f"""
Analyze the live weather data and generate short, practical advice.
{lang_directive}

CITY: {weather_data.get('city', 'Selected Location')},
{weather_data.get('country', '')}
TEMP: {weather_data.get('temperature')} °C
FEELS LIKE: {weather_data.get('feels_like')} °C
CONDITION: {weather_data.get('condition')}
DESCRIPTION: {weather_data.get('description')}
HUMIDITY: {weather_data.get('humidity')}%
WIND: {weather_data.get('wind_speed')} m/s

FORMAT:
STATUS:
- Short overview
- Sky or condition note

ALERT:
- Safety precaution
- Weather warning

CLOTHING:
- Clothing advice
- Footwear or accessory suggestion

HEALTH:
- Hydration advice
- Health protection precaution

TRAVEL:
- Outdoor activity advice
- Travel safety suggestion

RULES:
- Provide 2 short bullet points per section.
- Do not use Markdown headings.
- Follow the requested language.
"""


@app.route("/insights", methods=["POST"])
def insights():
    if not groq_client:
        return jsonify({"error": "Groq API key is missing."}), 500

    data = request.get_json(silent=True) or {}

    city = str(data.get("city", "")).strip()
    language = normalize_language(data.get("language", "en"))

    if not city:
        return jsonify({
            "error": "Please search for a city first."
        }), 400

    weather_data, error = get_weather_data(city)

    if error:
        return jsonify({"error": error}), 400

    prompt = build_insights_prompt(weather_data, language)
    insights_text, groq_error = generate_groq_response(prompt)

    if groq_error:
        return jsonify({"error": "Unable to generate insights"}), 500

    return jsonify({
        "insights": insights_text,
        "language": language,
    })


@app.route("/insights-coordinates", methods=["POST"])
def insights_coordinates():
    if not groq_client:
        return jsonify({"error": "Groq API key is missing."}), 500

    data = request.get_json(silent=True) or {}

    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid coordinates are required."}), 400

    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return jsonify({"error": "Invalid coordinates."}), 400

    location_name = str(
        data.get("location", "Selected Location")
    ).strip()

    language = normalize_language(data.get("language", "en"))

    weather_data, error = get_weather_data_by_coordinates(
        lat,
        lon,
        location_name,
    )

    if error:
        return jsonify({"error": error}), 400

    prompt = build_insights_prompt(weather_data, language)
    insights_text, groq_error = generate_groq_response(prompt)

    if groq_error:
        return jsonify({"error": "Unable to generate insights"}), 500

    return jsonify({
        "insights": insights_text,
        "language": language,
    })


# =========================================================
# CITY COORDINATES
# =========================================================

def get_city_coordinates(city):
    if not WEATHER_API_KEY:
        return None, "Weather API key is missing."

    url = "https://api.openweathermap.org/geo/1.0/direct"

    try:
        response = requests.get(
            url,
            params={
                "q": city,
                "limit": 1,
                "appid": WEATHER_API_KEY,
            },
            timeout=10,
        )

        data = response.json()

        if response.status_code != 200:
            return None, data.get(
                "message",
                "Unable to find city coordinates.",
            )

        if not data:
            return None, "City not found."

        return {
            "lat": data[0]["lat"],
            "lon": data[0]["lon"],
            "name": data[0]["name"],
            "country": data[0].get("country", ""),
        }, None

    except requests.RequestException:
        return None, "Unable to connect to the weather service."
    except (ValueError, KeyError, TypeError):
        return None, "Invalid response from the weather service."


# =========================================================
# HISTORICAL WEATHER - PREVIOUS 7 DAYS
# =========================================================

@app.route("/historical")
def historical():
    city = request.args.get("city", "").strip()
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    loc_name = city
    loc_country = ""

    if lat and lon:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except ValueError:
            return jsonify({"error": "Invalid coordinates"}), 400

        if not -90 <= lat_f <= 90 or not -180 <= lon_f <= 180:
            return jsonify({"error": "Invalid coordinates"}), 400
    else:
        if not city:
            return jsonify({
                "error": "Please search for a city first."
            }), 400

        loc, error = get_city_coordinates(city)

        if error:
            return jsonify({"error": error}), 400

        lat_f = loc["lat"]
        lon_f = loc["lon"]
        loc_name = loc["name"]
        loc_country = loc["country"]

    try:
        url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": lat_f,
            "longitude": lon_f,
            "daily": (
                "temperature_2m_max,temperature_2m_min,"
                "temperature_2m_mean,relative_humidity_2m_mean,"
                "wind_speed_10m_max,precipitation_sum,weather_code"
            ),
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "auto",
        }

        response = requests.get(url, params=params, timeout=12)
        response.raise_for_status()
        result = response.json()

        daily = result.get("daily", {})
        times = daily.get("time", [])

        rows = []

        # Use the location's local date provided by Open-Meteo.
        today = times[-1] if times else datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d")

        wmo_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            80: "Rain showers",
            95: "Thunderstorm",
        }

        for i, day in enumerate(times):
            if day >= today:
                continue

            max_t = daily["temperature_2m_max"][i]
            min_t = daily["temperature_2m_min"][i]

            mean_values = daily.get("temperature_2m_mean", [])
            avg_t = (
                mean_values[i]
                if i < len(mean_values) and mean_values[i] is not None
                else round((max_t + min_t) / 2, 1)
            )

            w_code = daily.get("weather_code", [0] * len(times))[i]

            humidity_values = daily.get(
                "relative_humidity_2m_mean",
                [],
            )
            wind_values = daily.get("wind_speed_10m_max", [])
            rain_values = daily.get("precipitation_sum", [])

            rows.append({
                "date": day,
                "temperature": avg_t,
                "min_temperature": min_t,
                "max_temperature": max_t,
                "humidity": (
                    round(humidity_values[i])
                    if i < len(humidity_values)
                    and humidity_values[i] is not None
                    else None
                ),
                "wind_speed": (
                    round(wind_values[i], 1)
                    if i < len(wind_values)
                    and wind_values[i] is not None
                    else None
                ),
                "precipitation": (
                    round(rain_values[i], 1)
                    if i < len(rain_values)
                    and rain_values[i] is not None
                    else None
                ),
                "condition": (
                    "Clear"
                    if w_code <= 1
                    else "Rain"
                    if w_code in (51, 53, 55, 61, 63, 65, 80, 95)
                    else "Cloudy"
                ),
                "description": wmo_codes.get(
                    w_code,
                    "Normal weather conditions",
                ),
            })

        return jsonify({
            "city": loc_name,
            "country": loc_country,
            "data": rows[-7:],
        })

    except requests.RequestException:
        return jsonify({
            "error": "Failed to retrieve historical weather."
        }), 502
    except (KeyError, TypeError, ValueError, IndexError):
        app.logger.exception("Historical weather processing failed.")
        return jsonify({
            "error": "Invalid historical weather response."
        }), 502


# =========================================================
# WEATHER ANALYTICS - 5-DAY FORECAST
# =========================================================

@app.route("/forecast")
def forecast():
    if not WEATHER_API_KEY:
        return jsonify({"error": "Weather API key is missing."}), 500

    city = request.args.get("city", "").strip()
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if lat and lon:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except ValueError:
            return jsonify({"error": "Invalid coordinates"}), 400

        if not -90 <= lat_f <= 90 or not -180 <= lon_f <= 180:
            return jsonify({"error": "Invalid coordinates"}), 400

        loc_name = city or "Selected Location"
        loc_country = ""
    else:
        if not city:
            return jsonify({
                "error": "Please search for a city first."
            }), 400

        loc, error = get_city_coordinates(city)

        if error:
            return jsonify({"error": error}), 400

        lat_f = loc["lat"]
        lon_f = loc["lon"]
        loc_name = loc["name"]
        loc_country = loc["country"]

    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "lat": lat_f,
        "lon": lon_f,
        "appid": WEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(url, params=params, timeout=12)
        data = response.json()

        if response.status_code != 200:
            return jsonify({
                "error": data.get(
                    "message",
                    "Unable to get forecast.",
                )
            }), response.status_code

        grouped = {}

        for item in data.get("list", []):
            date_key = datetime.fromtimestamp(
                item["dt"],
                timezone.utc,
            ).date().isoformat()

            grouped.setdefault(date_key, []).append(item)

        rows = []

        for date_key, items in list(grouped.items())[:5]:
            temps = [
                float(item["main"]["temp"])
                for item in items
            ]

            humidities = [
                float(item["main"]["humidity"])
                for item in items
            ]

            winds = [
                float(item.get("wind", {}).get("speed", 0))
                for item in items
            ]

            rains = [
                float(item.get("rain", {}).get("3h", 0))
                for item in items
            ]

            conditions = [
                item.get("weather", [{}])[0]
                for item in items
            ]

            dominant = (
                max(conditions, key=lambda item: item.get("id", 0))
                if conditions
                else {}
            )

            rows.append({
                "date": date_key,
                "temperature": round(sum(temps) / len(temps), 1),
                "min_temperature": round(min(temps), 1),
                "max_temperature": round(max(temps), 1),
                "humidity": round(
                    sum(humidities) / len(humidities)
                ),
                "wind_speed": round(
                    sum(winds) / len(winds),
                    1,
                ),
                "precipitation": round(sum(rains), 1),
                "condition": dominant.get("main", ""),
                "description": dominant.get("description", ""),
            })

        return jsonify({
            "city": loc_name,
            "country": loc_country,
            "data": rows,
        })

    except requests.RequestException:
        return jsonify({
            "error": "Unable to connect to the forecast service."
        }), 502
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        app.logger.exception("Forecast processing failed.")
        return jsonify({
            "error": "Invalid forecast response."
        }), 502


# =========================================================
# AUTHENTICATION + FEATURE APIS
# =========================================================

# Authentication routes such as /login, /register,
# /auth/register, /auth/login, /auth/verify and /auth/resend
# are defined in auth.py.
init_auth(app)

# Keep the existing WeatherGPT feature APIs.
init_features(app, generate_groq_response, WEATHER_API_KEY)


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)