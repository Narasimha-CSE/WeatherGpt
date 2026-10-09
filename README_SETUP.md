# WeatherGPT — setup

## Run (Windows PowerShell)
```powershell
cd WeatherGPT
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 — you will be sent to the **login page**. Click *Create an account* the first time.

Your `.env` must contain `WEATHER_API_KEY` (OpenWeather) and `GROQ_API_KEY`.
Email OTP login uses Gmail SMTP: `.env` also needs `SMTP_EMAIL` and `SMTP_APP_PASSWORD` (a Google App Password).
Optional: add `SECRET_KEY=any-long-random-string` (otherwise one is generated and stored in `data/secret.key`).

## What was added
| Area | Where |
|---|---|
| Login / Register with emailed 6-digit OTP (SQLite, sessions, Gmail SMTP, no passwords) | `auth.py`, `templates/auth.html`, `static/auth.css`, `static/auth.js` |
| Forecast, alerts, advice, travel score, farmer advisory, climate, map APIs | `features.py`, `i18n_data.py` (English / Telugu / Hindi text) |
| New website sections + animations | `templates/index.html`, `static/features.css`, `static/features.js` |
| Chat AI now sees the forecast (answers "tomorrow?" questions) | `app.py` |

User accounts are stored in `data/weathergpt.db` (created automatically). Delete the `data/` folder to reset all accounts.

## Data sources
* OpenWeather — current weather, geocoding, map tiles (proxied by the server so your key is never sent to the browser)
* Open-Meteo (no key) — hourly/daily forecast, UV, wind direction, 10–20 year climate history
* RainViewer (no key) — animated radar
* Groq — chat, forecast explanation, crop advice

## Notes
* Weather map layers (rain/wind/temp/clouds) need an OpenWeather key that has access to the *Weather Maps* tiles; if your plan does not include them the layer is simply blank. Radar is independent of that.
* Internet access is required in the browser for Leaflet, Chart.js and map tiles (loaded from CDNs).


## Sign-in options
* **Email OTP (works out of the box)** - Create account: name + email -> code by email -> account created -> the *Log in* section opens with your email filled in -> Send OTP -> "Welcome, <name>!" with a done mark -> app.
  Needs `SMTP_EMAIL` and `SMTP_APP_PASSWORD` (Google App Password) in `.env`.
* **Google / Facebook** - fill `GOOGLE_CLIENT_ID/SECRET` or `FACEBOOK_APP_ID/SECRET` in `.env` and register these redirect URIs in the provider console:
  `http://127.0.0.1:5000/auth/social/google/callback` and `http://127.0.0.1:5000/auth/social/facebook/callback`
  (use your real domain in production, or set `OAUTH_REDIRECT_BASE`). Without keys the buttons show a "not set up yet" message.
* **Phone number** - SMS code through Twilio: fill `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`. For local testing only, set `PHONE_OTP_DEV=1` to print the code in the server console.

## Pages (bottom navigation after login)
| Page | Contents |
|------|----------|
| Home | weather animation scene, city search, live weather, WeatherGPT AI chat |
| Graphs | weather analytics (previous/next days + trend graph), hourly & 5-day forecast chart, climate history charts |
| Tools | interactive weather map, travel intelligence, unit converter, heat index / dew point, Beaufort wind scale |
| AI Advisory | smart insights and precautions, smart alerts, personal recommendations, farmer advisory |
