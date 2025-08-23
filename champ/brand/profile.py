# champ/brand/profile.py

PRODUCT_NAME = "PhysioChamp"
ASSISTANT_NAME = "Champ"

ABOUT_ONE_LINER = (
    "PhysioChamp is a mobile-based data intelligence platform that turns smart insole "
    "pressure data into clear insights on gait, posture, and balance, with explainable AI tips, "
    "personalized exercise routines, and progress tracking for home and clinic use."
)

ELEVATOR_PITCH = (
    "PhysioChamp analyzes foot-pressure sensor data to detect gait, posture, and balance issues, "
    "then delivers explainable insights, tailored physiotherapy routines, and progress dashboards. "
    "It supports real-time feedback, remote monitoring, and shareable reports for individuals, athletes, "
    "seniors, and physiotherapy clinics."
)

KEY_CAPABILITIES = [
    "Real-time smart insole data capture and visualization",
    "AI/GenAI insights for gait, posture, and balance",
    "Personalized exercise plans and adherence tips",
    "Progress tracking with trends and shareable reports",
    "Clinic and home workflows; remote monitoring ready",
    "Diabetes-focused insights from pressure patterns (optional module)"
]

TARGET_USERS = [
    "Physiotherapists & rehab clinics",
    "Senior citizens (fall-risk and balance monitoring)",
    "Athletes & coaches (efficiency and injury prevention)",
    "Health-conscious individuals (posture correction and fitness)",
    "Chronic condition patients (e.g., Parkinson’s, stroke recovery, arthritis, diabetic neuropathy)"
]

TECH_STACK = [
    "Frontend: Flutter (Dart), Bluetooth (FlutterBlue)",
    "Backend: Python (Flask API), RAG (future)",
    "Database: MySQL",
    "ML/AI: Python, LLM (Gemini/OpenAI), LangChain/LangGraph",
]

BUSINESS_MODEL = (
    "Freemium-to-subscription: Free basic metrics; Premium (₹499/mo) with full history, detailed insights, "
    "personalized plans, reports, and chatbot; Pro (₹999/mo) for multi-user management and clinical exports. "
    "Optional revenue from ads and hardware (insoles)."
)

CONTACT = "Team PhysioChamp — +91 9322770715, priteshpurkar.17@gmail.com (Team T-1712, MIT AoE Pune)"

ROADMAP_SHORT = [
    "0–1 year: Launch core app, AI gait anomaly detection, secure cloud records",
    "1–3 years: Personalized rehab plans, GenAI chatbot Q&A, wearable integrations, B2B plans",
    "3+ years: Predictive fall risk, AR/VR guided sessions, multilingual assistant, global expansion"
]

# Canned answers (plain text, concise)
def answer_about():
    return (
        f"{ABOUT_ONE_LINER}\n\n"
        f"Key capabilities:\n- " + "\n- ".join(KEY_CAPABILITIES) +
        f"\n\nWho benefits:\n- " + "\n- ".join(TARGET_USERS)
    )

def answer_who_is_champ():
    return (
        f"{ASSISTANT_NAME} is the AI assistant inside {PRODUCT_NAME}. "
        "It summarizes gait/posture/balance trends, explains insights in plain language, "
        "and suggests practical, non-medical tips and exercise routines based on your data."
    )

def answer_how_to_use():
    return (
        "How to use PhysioChamp:\n"
        "1) Wear the smart insoles and perform a walking or standing session.\n"
        "2) The app syncs pressure data and computes gait, posture, and balance metrics.\n"
        "3) Open the dashboard to view trends, sessions, and alerts.\n"
        "4) Ask Champ for a health overview or personalized tips.\n"
        "5) Follow your suggested routine; track progress over time."
    )

def answer_features():
    return "Core features:\n- " + "\n- ".join(KEY_CAPABILITIES)

def answer_tech():
    return "Tech stack:\n- " + "\n- ".join(TECH_STACK)

def answer_business():
    return "Business model:\n" + BUSINESS_MODEL

def answer_contact():
    return f"Contact: {CONTACT}"

def answer_pitch():
    return ELEVATOR_PITCH

def answer_roadmap():
    return "Roadmap:\n- " + "\n- ".join(ROADMAP_SHORT)

# Simple matcher
def detect_brand_intent(q: str) -> str | None:
    t = (q or "").strip().lower()
    if not t:
        return None
    if any(k in t for k in ["what is physiochamp", "about physiochamp", "what is physio champ", "who are you", "who is champ", "assistant name", "your name"]):
        return "about"
    if any(k in t for k in ["how to use physiochamp", "how do i use", "getting started", "how to use"]):
        return "howto"
    if any(k in t for k in ["features", "capabilities", "what can you do"]):
        return "features"
    if any(k in t for k in ["tech stack", "technology", "stack"]):
        return "tech"
    if any(k in t for k in ["business model", "pricing", "plans", "subscription"]):
        return "business"
    if any(k in t for k in ["contact", "email", "phone"]):
        return "contact"
    if any(k in t for k in ["pitch", "elevator", "why physiochamp"]):
        return "pitch"
    if any(k in t for k in ["roadmap", "future", "plan"]):
        return "roadmap"
    return None

def reply_for_intent(intent: str) -> str:
    if intent == "about":
        return f"{answer_about()}\n\nAssistant: {ASSISTANT_NAME}"
    if intent == "howto":
        return answer_how_to_use()
    if intent == "features":
        return answer_features()
    if intent == "tech":
        return answer_tech()
    if intent == "business":
        return answer_business()
    if intent == "contact":
        return answer_contact()
    if intent == "pitch":
        return answer_pitch()
    if intent == "roadmap":
        return answer_roadmap()
    return ""
