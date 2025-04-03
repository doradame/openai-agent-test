# 🧳 TravelAssistant AI

A smart travel-planning assistant that helps you prepare a trip within the next 24 hours. Powered by OpenAI, Google Places, OpenWeatherMap, and WebSearch, it gives you:

- Detailed weather forecast
- Personalized places of interest (indoor/outdoor based on conditions)
- Recent local events, advisories, and travel updates
- Structured, readable Markdown output
- Input and output safety guardrails

Built with love for learning and sharing on [MojaLab](https://mojalab.it) 💡

---

## 🚀 Features

- ✅ AI-generated responses via OpenAI
- 🌦️ Weather forecast with OpenWeatherMap
- 📍 Places of interest using Google Maps API
- 🔎 Web updates with embedded search tool
- 🔐 Input/output guardrails (safe content enforcement)
- 📄 Markdown-formatted output
- 🪵 Logging to file for easy debugging

---

## 🛠️ Setup Instructions

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/travel-assistant-ai.git
cd travel-assistant-ai
```

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file

```env
OPENAI_API_KEY=your_openai_key
GOOGLE_PLACES_API_KEY=your_google_places_api_key
WEATHER_API_KEY=your_openweathermap_key
```

> 💡 You can generate these API keys from:
>
> - OpenAI: https://platform.openai.com/account/api-keys
> - Google Places: https://console.cloud.google.com
> - OpenWeatherMap: https://home.openweathermap.org/api_keys

---

## ▶️ Run the Travel Assistant

```bash
python travel_assistant.py
```

It will prompt for a **destination city**, then output a full travel plan in Markdown format.


## 📁 Output

Results are printed in **Markdown** format in the terminal. You can convert them to HTML using the built-in `markdown` module.

Logs are saved in:

```bash
travel_assistant.log
```

---

## 👨‍💻 Author

Created by [Domenico Radano](https://github.com/doradame) — sysadmin, developer & writer at [MojaLab](https://mojalab.it).
