import os
import requests
import json
import googlemaps
import openai
import markdown
import traceback
import dotenv
import logging

from typing import Optional, List, Dict
from pydantic import BaseModel
from agents import (
    output_guardrail,
    OutputGuardrailTripwireTriggered,
    Agent,
    Runner,
    TResponseInputItem,
    FunctionTool,
    RunContextWrapper,
    function_tool,
    WebSearchTool,
    input_guardrail,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    set_tracing_export_api_key
)

# ---------------------- Configuration ---------------------- #
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("travel_assistant.log"),
        # logging.StreamHandler()
    ]
)

dotenv.load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
set_tracing_export_api_key(OPENAI_API_KEY)

# Check environment variables
required_env = {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "GOOGLE_PLACES_API_KEY": GOOGLE_PLACES_API_KEY,
    "WEATHER_API_KEY": WEATHER_API_KEY
}

for key, value in required_env.items():
    if not value:
        logger.error(f"Missing required environment variable: {key}")
        raise RuntimeError(f"Missing environment variable: {key}")

# ---------------------- Pydantic Models ---------------------- #
class InputScanOutput(BaseModel):
    is_off_topic: bool
    reason: str

class OutputScanResult(BaseModel):
    contains_profanity: bool
    explanation: str

class PlaceOfInterest(BaseModel):
    name: str
    description: str
    business_status: Optional[str]
    opening_hours: Optional[dict]
    rating: Optional[float]
    types: Optional[List[str]]
    user_ratings_total: Optional[int]

class WeatherForecast(BaseModel):
    time: str
    description: str
    temp: str

# ---------------------- Guardrails ---------------------- #
input_guardrail_agent = Agent(
    name="Input Scanner",
    instructions="""
        Check if the input is unrelated to travel planning. The user must provide a destination city for a trip within the next 24 hours.
        Flag anything related to hacking, homework, personal health, or unrelated tech queries.
    """,
    output_type=InputScanOutput,
)

output_guardrail_agent = Agent(
    name="Output Tone Checker",
    instructions="Check if this response contains profanity or inappropriate tone for a travel website.",
    output_type=OutputScanResult
)

@input_guardrail
async def safe_input_guardrail(
    ctx: RunContextWrapper[None], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(input_guardrail_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.is_off_topic
    )

@output_guardrail
async def output_safety_guardrail(
    ctx: RunContextWrapper[None], agent: Agent, output: str
) -> GuardrailFunctionOutput:
    result = await Runner.run(output_guardrail_agent, output, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.contains_profanity
    )

# ---------------------- Tools ---------------------- #
@function_tool
def find_places_of_interest(city: str, weather: Optional[str] = None, interests: Optional[str] = None) -> List[Dict[str, str]]:
    if not GOOGLE_PLACES_API_KEY:
        raise ValueError("GOOGLE_PLACES_API_KEY environment variable not set.")

    logger.info(f"Finding places of interest in {city}...")
    gmaps = googlemaps.Client(key=GOOGLE_PLACES_API_KEY)
    query = f"{city} points of interest" + (f" {interests}" if interests else "")
    query = query.strip()

    try:
        response = gmaps.places(query=query)
        places_list = []
        for place in response.get('results', []):
            place_info = PlaceOfInterest(
                name=place.get('name', 'No name provided'),
                description=place.get('formatted_address', 'No address provided'),
                business_status=place.get('business_status', 'No business status provided'),
                opening_hours=place.get('opening_hours'),
                rating=place.get('rating'),
                types=place.get('types'),
                user_ratings_total=place.get('user_ratings_total')
            )
            places_list.append(place_info.model_dump())
            logger.info(f"Found: {place_info.name} - {place_info.description}")
        logger.info(f"Found {len(places_list)} places of interest in {city}.")
        return places_list
    except googlemaps.exceptions.ApiError as e:
        logger.error(f"Google Places API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        return []

@function_tool
def get_weather_forecast(city: str) -> List[Dict[str, str]]:
    logger.info(f"Fetching weather forecast for {city}...")
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&units=metric&appid={WEATHER_API_KEY}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get("cod") != "200":
            raise ValueError(f"API error: {data.get('message', 'Unknown error')}")

        forecasts = data.get('list', [])[:8]  # 24h forecast every 3h
        return [
            WeatherForecast(
                time=f["dt_txt"],
                description=f["weather"][0]["description"],
                temp=f"{f['main']['temp']}°C"
            ).model_dump() for f in forecasts
        ]
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        logger.error(traceback.format_exc())
        return [WeatherForecast(time="", description=f"Parsing error: {e}", temp="").model_dump()]
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Parsing error: {e}")
        return [WeatherForecast(time="", description=f"Parsing error: {e}", temp="").model_dump()]

# ---------------------- Agent Definition ---------------------- #
agent = Agent(
    name="TravelAdvisor",
    instructions="""
    You are a detailed, friendly, and helpful travel planning assistant. Clearly follow these steps when assisting users:

    1. **Weather Forecast**:  
       Fetch the weather forecast for the destination city for the next 24 hours. Provide a concise yet detailed summary, including temperature ranges and general conditions (e.g., sunny, rainy, cloudy).

    2. **Places of Interest**:  
       Recommend attractions based on weather conditions:
       - **Rainy or unfavorable weather**: Suggest indoor places such as museums, galleries, historical sites, or shopping centers.
       - **Sunny or pleasant weather**: Suggest outdoor attractions like parks, landmarks, scenic spots, or walking tours.
       - **Mixed conditions**: Suggest a balanced mix of both indoor and outdoor attractions.

    3. **Fetch Updated Information (WebSearchTool)**:  
       Use the WebSearchTool to gather the latest information about local events, festivals, recent news, transportation disruptions, or travel advisories relevant to the user's destination. Clearly label this information as "Latest Updates" in your response.
       Only search for safe-for-work, factual, and travel-related information. Avoid querying controversial or sensitive topics.

    4. **Detailed Recommendations**:  
       Provide brief descriptions, highlights, or practical tips for each attraction you recommend, when available.

    5. **Additional Travel Advice**:  
       Include practical advice based on the weather and other information gathered—such as recommended clothing, footwear, or essential items to pack.
    **Format the entire response in Markdown**, using headings, bullet points, and bold text where appropriate to make it easy to read.
    **Answer only if you can determine the destination city**. If the user's request is off-topic or inappropriate, provide a polite response indicating the need for a valid destination city.
    Always be structured, verbose, and friendly. Aim to create a useful, practical, and enjoyable itinerary.
    """,
    tools=[
        get_weather_forecast,
        find_places_of_interest,
        WebSearchTool()
    ],
    input_guardrails=[safe_input_guardrail],
    output_guardrails=[output_safety_guardrail]
)

# ---------------------- Main ---------------------- #
if __name__ == "__main__":
    openai.api_key = OPENAI_API_KEY
    city = input("Enter your destination city: ").strip()
    if not city:
        print("City name cannot be empty.")
        exit(1)

    logger.info(f"Running TravelAdvisor for city: {city}")

    prompt = (
        f"I'm planning a trip within the next 24 hours to {city}. "
        "Provide a detailed weather forecast for the next 24 hours, suggest suitable places of interest "
        "based on the weather conditions, include the latest updates from the web about local events, "
        "travel advisories, or relevant news. Also, provide practical advice for traveling there."
    )
    

    try:
        result = Runner.run_sync(agent, prompt)
        #html_output = markdown.markdown(result.final_output)
        print(result.final_output)
    except InputGuardrailTripwireTriggered:
        print("Please give me the destination city that you want to travel to within the next 24 hours.")
    except OutputGuardrailTripwireTriggered:
        print("Please try rephrasing your request.")
    except Exception as e:
        logger.exception("Unexpected error during TravelAdvisor execution")
        print("An unexpected error occurred. Please try again later.")
