from pathlib import Path
import requests
from fastapi import FastAPI, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="AI Climate Hazard Intelligence System")

# Secret key for session management (change in production)
app.add_middleware(SessionMiddleware, secret_key="super-secret-climate-key")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# State coordinates mapping for Open-Meteo API
STATE_COORDS = {
    "Rajasthan": {"lat": 26.9124, "lon": 75.7873},
    "Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Punjab": {"lat": 30.9010, "lon": 75.8573},
    "Madhya Pradesh": {"lat": 23.2599, "lon": 77.4126},
    "Maharashtra": {"lat": 19.7515, "lon": 75.7139},
    "Gujarat": {"lat": 22.2587, "lon": 71.1924}
}

def get_risk_badge(score):
    if score < 30:
        return "Low", "badge-low"
    elif 30 <= score < 50:
        return "Moderate", "badge-moderate"
    elif 50 <= score < 75:
        return "High", "badge-high"
    else:
        return "Severe", "badge-severe"

# Landing / Login Page Route
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    if request.session.get("authenticated"):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

# Login POST Handler
@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Demo credentials check (Accepts any non-empty input or admin/admin)
    if username and password:
        request.session["authenticated"] = True
        request.session["username"] = username
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"error": "Invalid username or password."}
    )

# Dashboard Route (Protected)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "states": list(STATE_COORDS.keys()),
            "username": request.session.get("username", "Officer")
        }
    )

# Logout Route
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@app.get("/api/fetch-live-weather")
async def fetch_live_weather(state: str):
    coords = STATE_COORDS.get(state, STATE_COORDS["Rajasthan"])
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={coords['lat']}&longitude={coords['lon']}"
        f"&current=temperature_2m,relative_humidity_2m"
        f"&daily=temperature_2m_max"
        f"&timezone=auto"
    )
    
    try:
        response = requests.get(url, timeout=6)
        response.raise_for_status()
        data = response.json()
        
        tmax = data.get("daily", {}).get("temperature_2m_max", [40.0])[0]
        humidity = data.get("current", {}).get("relative_humidity_2m", 30.0)
        source_info = "Open-Meteo Verified Global Model (ECMWF/NOAA)"
    except Exception:
        tmax, humidity = 42.0, 25.0
        source_info = "Fallback Station Data"

    return {
        "max_temp": tmax, 
        "humidity": humidity,
        "source": source_info
    }

@app.get("/api/assess-hazard")
async def assess_hazard(state: str, max_temp: float, humidity: float, hot_days: int):
    risk_score = round((0.55 * max_temp) + (0.25 * hot_days) + (0.20 * (100 - humidity)), 1)
    severity_level, severity_badge = get_risk_badge(risk_score)

    hazards = [
        {
            "title": "Drought Risk",
            "level": "High" if (hot_days >= 4 and humidity < 30) or state in ["Rajasthan", "Gujarat"] else "Moderate",
            "action": "Activate drought contingency plan; monitor reservoir/groundwater levels."
        },
        {
            "title": "Water Scarcity Risk",
            "level": "High" if risk_score > 40 else "Moderate",
            "action": "Deploy water tankers to vulnerable areas; enforce water rationing."
        },
        {
            "title": "Forest Fire Risk",
            "level": "High" if (max_temp > 40 and humidity < 20) or state == "Madhya Pradesh" else "Moderate",
            "action": "Alert forest department; pre-position fire-fighting crews near dry zones."
        },
        {
            "title": "Public Health Risk",
            "level": "Severe" if max_temp > 44 else "Moderate",
            "action": "Open heat shelters/ORS centres; issue advisories, especially for outdoor workers & elderly."
        },
        {
            "title": "Power Demand Risk",
            "level": "High" if max_temp > 40 or state == "Delhi" else "Moderate",
            "action": "Coordinate with power utilities for load management; prevent grid overload."
        },
        {
            "title": "Urban Heat Island Risk",
            "level": "High" if state in ["Delhi", "Maharashtra"] else "Moderate",
            "action": "Advise cooling centres in dense urban wards; promote reflective roofing where feasible."
        }
    ]

    for h in hazards:
        _, h["badge_class"] = get_risk_badge(80 if h["level"] == "Severe" else 60 if h["level"] == "High" else 40)

    return {
        "state": state,
        "heat_risk_score": risk_score,
        "heatwave_severity": severity_level,
        "severity_badge": severity_badge,
        "hazards": hazards
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)