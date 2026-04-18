"""
BleedX — AI-Powered Money Leak Detection Engine
FastAPI Backend
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
import io
import re
from datetime import datetime
import sys
import subprocess

# --- Auto-install pdfplumber if missing to revive the broken server ---
try:
    import pdfplumber
except ImportError:
    print("pdfplumber not found! Auto-installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

from pydantic import BaseModel
import uuid

app = FastAPI(title="BleedX API", version="1.0.0")

import os
import json

VERCEL_ENV = os.environ.get("VERCEL", "0") == "1"
CLIENT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "client")
DB_PATH = "/tmp/database.json" if VERCEL_ENV else os.path.join(os.path.dirname(__file__), "database.json")

def load_db():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"transactions": [], "analysis": {}, "budget": 50000.0}

def save_db(db_state):
    try:
        with open(DB_PATH, "w") as f:
            json.dump(db_state, f)
    except Exception:
        pass

memory_db = load_db()
if "budget" not in memory_db:
    memory_db["budget"] = 50000.0
if "phone" not in memory_db:
    memory_db["phone"] = None

class TransactionMark(BaseModel):
    id: str
    status: str # "necessary" or "unnecessary"

# --- MOCK SMS GATEWAY ---
def dispatch_sms(phone: str, message: str):
    """
    Simulated SMS Dispatcher simulating a Twilio/AWS SNS node constraint.
    In real production deployments, this binds to the Twilio REST module.
    """
    print(f"\n\033[96m{'='*60}\033[0m")
    print(f"\033[1;92m📱 ⚡ SMS OUTBOUND GATEWAY OVERRIDE INITIATED\033[0m")
    print(f"\033[93mTarget Device: {phone}\033[0m")
    print(f"\033[95mPayload Transmission:\n{message}\033[0m")
    print(f"\033[96m{'='*60}\033[0m\n")
    return True

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Serve frontend ---
import os
CLIENT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "client")

app.mount("/static", StaticFiles(directory=CLIENT_DIR), name="static")


@app.get("/")
async def serve_login():
    return FileResponse(os.path.join(CLIENT_DIR, "login.html"))

@app.get("/app")
async def serve_app():
    return FileResponse(os.path.join(CLIENT_DIR, "index.html"))


# ---------------------------------------------------------------------------
# Category keywords mapping
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "Food": [
        "zomato", "swiggy", "dominos", "pizza", "burger", "food", "restaurant",
        "cafe", "starbucks", "mcd", "kfc", "uber eats", "dining", "eat",
        "biryani", "chicken", "hotel", "dhaba", "bakery", "snack", "juice",
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "ajio", "meesho", "snapdeal",
        "shopping", "mall", "store", "retail", "nykaa", "purplle",
        "croma", "reliance", "brand", "fashion",
    ],
    "Subscriptions": [
        "netflix", "spotify", "hotstar", "prime", "youtube", "premium",
        "subscription", "membership", "plan", "renewal", "auto-debit",
        "apple music", "jio", "airtel", "vi ", "bsnl", "zee5", "sonyliv",
        "disney", "hbo",
    ],
    "Bills": [
        "electricity", "water", "gas", "bill", "recharge", "broadband",
        "wifi", "internet", "insurance", "emi", "loan", "rent", "tax",
        "maintenance", "society",
    ],
    "Travel": [
        "uber", "ola", "rapido", "metro", "petrol", "diesel", "fuel",
        "parking", "toll", "cab", "auto", "train", "irctc", "bus",
        "flight", "makemytrip", "travel", "indigo", "air", "hotel"
    ],
}


def classify_category(description: str) -> str:
    """Classify a transaction into a category based on keywords."""
    desc = str(description).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc:
                return category
    return "Others"


def detect_leaks(df: pd.DataFrame) -> dict:
    """
    Core leak detection logic.
    Returns structured analysis results.
    """
    # ------------------------------------------------------------------
    # 1. Basic Stats
    # ------------------------------------------------------------------
    total_spend = float(df["amount"].sum())
    total_transactions = len(df)

    # ------------------------------------------------------------------
    # 2. Category breakdown
    # ------------------------------------------------------------------
    category_spend = df.groupby("category")["amount"].sum().to_dict()
    category_counts = df.groupby("category")["amount"].count().to_dict()

    # ------------------------------------------------------------------
    # 3. Monthly trend
    # ------------------------------------------------------------------
    monthly = {}
    if "date" in df.columns:
        df["_month"] = df["date"].dt.to_period("M").astype(str)
        monthly = df.groupby("_month")["amount"].sum().to_dict()

    # ------------------------------------------------------------------
    # 4. Leak Detection
    # ------------------------------------------------------------------
    leaks = []
    leak_amount = 0.0

    # --- A. Micro-spending (< ₹500, high frequency) ---
    micro = df[df["amount"] < 500]
    if len(micro) > 5:  # at least 5 small transactions
        micro_total = float(micro["amount"].sum())
        leak_amount += micro_total
        leaks.append({
            "type": "Micro Spending",
            "icon": "🔬",
            "message": f"You have {len(micro)} tiny transactions (< ₹500) totaling ₹{micro_total:,.0f}. These silent bleeds add up fast.",
            "amount": micro_total,
            "count": int(len(micro)),
        })

    # --- B. Subscription detection (same amount repeated 2+) ---
    amount_freq = df.groupby("amount").size()
    recurring = amount_freq[amount_freq >= 2]
    if not recurring.empty:
        sub_amounts = recurring.index.tolist()
        sub_df = df[df["amount"].isin(sub_amounts)]
        sub_total = float(sub_df["amount"].sum())
        leak_amount += sub_total
        top_subs = []
        for amt in sub_amounts[:5]:
            rows = df[df["amount"] == amt]
            desc = rows["description"].iloc[0] if "description" in rows.columns else "Unknown"
            top_subs.append({"description": str(desc), "amount": float(amt), "count": int(len(rows))})
        leaks.append({
            "type": "Recurring / Subscriptions",
            "icon": "🔁",
            "message": f"Detected {len(sub_amounts)} recurring charges totaling ₹{sub_total:,.0f}. Could be subscriptions you forgot about.",
            "amount": sub_total,
            "count": int(len(sub_df)),
            "details": top_subs,
        })

    # --- C. Impulse spending (11 PM – 3 AM) ---
    if "date" in df.columns:
        night = df[df["date"].dt.hour.between(23, 23) | df["date"].dt.hour.between(0, 3)]
        if len(night) > 0:
            night_total = float(night["amount"].sum())
            leak_amount += night_total
            leaks.append({
                "type": "Late-Night Impulse",
                "icon": "🌙",
                "message": f"{len(night)} transactions between 11 PM–3 AM totaling ₹{night_total:,.0f}. Night-time spending = impulse spending.",
                "amount": night_total,
                "count": int(len(night)),
            })

    # ------------------------------------------------------------------
    # 5. Leak Score
    # ------------------------------------------------------------------
    if total_spend > 0:
        leak_score = min(100, max(0, (leak_amount / total_spend) * 100))
    else:
        leak_score = 0

    # ------------------------------------------------------------------
    # 6. Top leak categories (for the "Where Money Bleeds" section)
    # ------------------------------------------------------------------
    sorted_cats = sorted(category_spend.items(), key=lambda x: x[1], reverse=True)
    top_categories = []
    for cat, amount in sorted_cats[:5]:
        pct = (amount / total_spend * 100) if total_spend > 0 else 0
        top_categories.append({
            "category": cat,
            "amount": float(amount),
            "percentage": round(pct, 1),
            "count": int(category_counts.get(cat, 0)),
        })

    # ------------------------------------------------------------------
    # 7. Insights (Deep AI Structural Diagnostics)
    # ------------------------------------------------------------------
    insights = []
    
    # 7.1 Capital Concentration Warning
    if len(top_categories) > 0:
        primary_cat = top_categories[0]
        if primary_cat["percentage"] >= 30:
            insights.append({
                "icon": "⚠️",
                "text": f"DANGER: Severe capital concentration. {primary_cat['percentage']:.1f}% (₹{primary_cat['amount']:,.0f}) of all measured outbound liquidity went to [{primary_cat['category']}]. You lack expenditure diversification.",
            })

    # 7.2 Food Delivery Metric 
    if "Food" in category_spend and category_spend["Food"] > 0:
        food_yearly_proj = category_spend["Food"] * 12
        insights.append({
            "icon": "🍔",
            "text": f"Your measured food/dining bleed rate is ₹{category_spend['Food']:,.0f}/mo. At constant velocity, this burns ₹{food_yearly_proj:,.0f} annually. Hard-cutting external dining by 40% recoups ₹{food_yearly_proj * 0.40:,.0f}/yr.",
        })

    # 7.3 Subscription Velocity Check
    if "Subscriptions" in category_spend and category_spend["Subscriptions"] > 0:
        subs_pct = (category_spend["Subscriptions"] / total_spend * 100) if total_spend > 0 else 0
        insights.append({
            "icon": "📺",
            "text": f"Phantom Subscriptions account for {subs_pct:.1f}% of continuous capital drain (₹{category_spend['Subscriptions']:,.0f}). Statistically, the average consumer ignores 60% of active recurring SaaS profiles.",
        })

    # 7.4 Micro-transaction Frequency (Data matched natively from leaks loop)
    micro_leak = next((l for l in leaks if l["type"] == "Micro Spending"), None)
    if micro_leak:
        avg_micro = micro_leak["amount"] / micro_leak["count"]
        insights.append({
            "icon": "📉",
            "text": f"Micro-Bleeding Protocol Alert: System flagged {micro_leak['count']} distinct transactions under ₹500 at a median of ₹{avg_micro:.0f}/swipe. These 'harmless' invisible charges aggregated to a massive ₹{micro_leak['amount']:,.0f} hole.",
        })
        
    # 7.5 Late-Night Impulse
    night_leak = next((l for l in leaks if l["type"] == "Late-Night Impulse"), None)
    if night_leak:
        insights.append({
            "icon": "🌃",
            "text": f"Circadian Alert: You authorized {night_leak['count']} payments between 23:00 and 03:00 (Total: ₹{night_leak['amount']:,.0f}). Late-night neural fatigue explicitly correlates with 85% of impulse buyer's remorse.",
        })

    # 7.6 Core Health Baseline
    if leak_score >= 50:
        insights.append({
            "icon": "🚨",
            "text": f"SYSTEM CRITICAL: Terminal leak score indicates {leak_score:.0f}% of your capital (₹{leak_amount:,.0f}) is mathematically classified as pure tactical waste. Immediate intervention protocol is required.",
        })
    elif leak_score < 15 and total_transactions > 0:
        insights.append({
            "icon": "🛡️",
            "text": f"FORTIFIED: Capital structure is strictly optimized. Current systemic leak rate is stabilized at just {leak_score:.1f}%. Current velocity leaves high excess liquidity for manual investment routing.",
        })

    # ------------------------------------------------------------------
    # 8. Action suggestions (Dynamic Mitigation Protocols)
    # ------------------------------------------------------------------
    actions = []
    
    if "Food" in category_spend and (category_spend["Food"] / total_spend) > 0.15:
        actions.append({"filter": "Food", "icon": "🍳", "title": "Execute Protocol: Prep", "description": "Cut aggressive food delivery bleeding. Click to isolate all Food & Dining charges."})
        
    if any(l["type"] == "Recurring / Subscriptions" for l in leaks):
        actions.append({"filter": "Subscriptions", "icon": "🗑️", "title": "Execute Protocol: Purge", "description": "Terminate unused recurring ghost subscriptions. Click to isolate flagged charges."})
        
    if "Shopping" in category_spend and (category_spend["Shopping"] / total_spend) > 0.20:
        actions.append({"filter": "Shopping", "icon": "📵", "title": "Execute Protocol: Detox", "description": "Initiate a 30-day shopping fast. Click to isolate all retail triggers."})
        
    if any(l["type"] == "Late-Night Impulse" for l in leaks):
        actions.append({"filter": "Curfew", "icon": "⏰", "title": "Execute Protocol: Curfew", "description": "Restrict 11 PM to 3 AM spending gates. Click to isolate nocturnal impulses."})
        
    if len(actions) == 0:
        actions.append({"filter": "All", "icon": "💹", "title": "Execute Protocol: Sustain", "description": "No critical bleeding thresholds met. Monitor general spending allocations."})


    # ------------------------------------------------------------------
    # Build response
    # ------------------------------------------------------------------
    return {
        "success": True,
        "leak_score": round(leak_score, 1),
        "total_spend": round(total_spend, 2),
        "total_transactions": total_transactions,
        "category_spend": category_spend,
        "monthly_trend": monthly,
        "top_categories": top_categories,
        "leaks": leaks,
        "insights": insights,
        "actions": actions,
        "leak_amount": round(leak_amount, 2),
        "budget": memory_db.get("budget", 50000.0)
    }


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Upload a CSV/Excel file and get back a full leak analysis.
    """
    try:
        contents = await file.read()
        filename = file.filename.lower()

        # Read the file
        if filename.endswith(".csv"):
            try:
                csv_str = contents.decode("utf-8")
            except UnicodeDecodeError:
                csv_str = contents.decode("latin-1", errors="ignore")
                
            lines = csv_str.splitlines()
            skip_idx = 0
            for i, line in enumerate(lines[:20]):
                line_lower = line.lower()
                if "amount" in line_lower or "debit" in line_lower or "date" in line_lower or "particular" in line_lower:
                    skip_idx = i
                    break
            
            df = pd.read_csv(io.StringIO(csv_str), skiprows=skip_idx, on_bad_lines="skip")
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents))
        elif filename.endswith((".pdf", ".txt", ".log", ".md")):
            
            text = ""
            if filename.endswith(".pdf"):
                import pdfplumber
                with pdfplumber.open(io.BytesIO(contents)) as pdf:
                    for page in pdf.pages:
                        text += (page.extract_text(x_tolerance=2, y_tolerance=3) or "") + "\n"
            else:
                # Handle raw text encodings natively
                text = contents.decode("utf-8", errors="ignore")
            
            
            records = []
            
            # Very aggressive Regex to find typical Indian/Global Bank Statement formats
            # Matches Date (e.g. 12/03/2024, 12-Mar-2024, 12 Mar 24)
            date_pattern = r"(?P<date>\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{1,2}\s*[A-Za-z]{3}\s*\d{2,4}|\d{1,2}[-][A-Za-z]{3}[-]\d{2,4})"
            # Matches an Amount (e.g. 1,000.50, 45.00, 1000)
            amount_pattern = r"(?P<amount>\d{1,3}(?:,\d{2,3})*\.\d{2})"
            
            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line starts with a date
                date_match = re.search(r"^" + date_pattern, line)
                if not date_match:
                    # Sometimes date is slightly offset
                    date_match = re.search(date_pattern, line)
                
                if date_match:
                    date_str = date_match.group("date")
                    
                    # Find all amounts in the line (withdrawals/deposits/balances)
                    amounts = re.findall(amount_pattern, line)
                    
                    if amounts:
                        # Extract the text between the date and the first amount as description
                        # Or just remove date and amounts from the line
                        desc_str = line.replace(date_str, "")
                        for amt in amounts:
                            desc_str = desc_str.replace(amt, "")
                        
                        desc_str = re.sub(r'[^A-Za-z0-9\s]', '', desc_str).strip()
                        if len(desc_str) < 3:
                            desc_str = "Transaction Data"
                            
                        # Usually the first amount is the transaction amount, or second. 
                        # We will just pick the first valid amount we find
                        txn_amount_str = amounts[0].replace(",", "")
                        
                        records.append({
                            "Date": date_str,
                            "Description": desc_str,
                            "Amount": txn_amount_str
                        })

            if not records:
                return {"success": False, "error": "Could not extract structured transactions from the document. The format must contain dates and amounts."}
            df = pd.DataFrame(records)
        else:
            return {"success": False, "error": "Unsupported file type. Please upload a PDF, CSV, Excel, or purely Text (.txt) Bank Statement."}

        # --- Clean & normalize columns ---
        df.columns = df.columns.str.strip().str.lower()

        # Try to detect the amount column
        amount_col = None
        for col in df.columns:
            if "amount" in col or "debit" in col or "withdrawal" in col:
                amount_col = col
                break
        if amount_col is None:
            # === EXTREME FALLBACK: Pure Regex Extraction ===
            # If the CSV/Excel structures are corrupt or lacking headers, literally rip it as a string
            fallback_records = []
            try:
                text_raw = contents.decode("utf-8", errors="ignore")
                d_patt = r"(?P<date>\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{1,2}\s*[A-Za-z]{3}\s*\d{2,4}|\d{1,2}[-][A-Za-z]{3}[-]\d{2,4})"
                a_patt = r"(?P<amount>\d{1,3}(?:,\d{2,3})*\.\d{2})"
                for lne in text_raw.splitlines():
                    if re.search(d_patt, lne):
                        f_amts = re.findall(a_patt, lne)
                        if f_amts:
                            dstr = re.search(d_patt, lne).group("date")
                            dsc = lne.replace(dstr, "")
                            for a in f_amts: dsc = dsc.replace(a, "")
                            dsc = re.sub(r'[^A-Za-z0-9\s]', '', dsc).strip()
                            if len(dsc) < 3: dsc = "Extracted Ledger Entry"
                            fallback_records.append({"date": dstr, "desc": dsc, "amount": f_amts[0].replace(",", "")})
            except Exception:
                pass
            
            if fallback_records:
                df = pd.DataFrame(fallback_records)
                amount_col = "amount"
                date_col = "date"
                desc_col = "desc"
            else:
                return {"success": False, "error": "Could not identify standard banking arrays. Try manually deleting garbage rows at the top."}

        df["amount"] = pd.to_numeric(df[amount_col], errors="coerce").abs()

        # Try to detect the date column
        date_col = None
        for col in df.columns:
            if "date" in col or "time" in col:
                date_col = col
                break
        if date_col:
            df["date"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
        else:
            df["date"] = pd.NaT

        # Try to detect description column
        desc_col = None
        for col in df.columns:
            if any(k in col for k in ["desc", "narr", "particular", "remark", "detail", "merchant", "name"]):
                desc_col = col
                break
        if desc_col:
            df["description"] = df[desc_col].astype(str)
        else:
            df["description"] = "Unknown"

        # Drop rows with NaN amounts
        df = df.dropna(subset=["amount"])
        df = df[df["amount"] > 0]

        if df.empty:
            return {"success": False, "error": "No valid transactions found in the file."}

        # Classify categories
        df["category"] = df["description"].apply(classify_category)

        # Ensure we have type debit/credit (fallback assumption all positive are debits in our parsed df)
        df["type"] = "debit"

        # Give every transaction an ID and user_mark status
        if "id" not in df.columns:
            df["id"] = [str(uuid.uuid4()) for _ in range(len(df))]
        if "user_mark" not in df.columns:
            df["user_mark"] = "unknown" # can be 'necessary' or 'unnecessary'

        # Store in memory DB
        # Safe JSON serialization (convert NaT/NaN to None)
        df_safe = df.astype(object).where(pd.notnull(df), None)
        memory_db["transactions"] = df_safe.to_dict(orient="records")

        # Run analysis
        result = detect_leaks(df)
        result["transactions"] = memory_db["transactions"]

        # Calculate necessary / unnecessary spending from marked
        necessary_spend = sum(t["amount"] for t in memory_db["transactions"] if t.get("user_mark") == "necessary")
        unnecessary_spend = sum(t["amount"] for t in memory_db["transactions"] if t.get("user_mark") == "unnecessary")
        result["necessary_spend"] = float(necessary_spend)
        result["unnecessary_spend"] = float(unnecessary_spend)

        memory_db["analysis"] = result
        return result

    except Exception as e:
        return {"success": False, "error": f"Analysis failed: {str(e)}"}

@app.get("/demo-analysis")
async def demo_analysis():
    import os
    file_path = r"c:\Users\Ishant katyayan\OneDrive\Desktop\Bleed_X\sample_transactions.csv"
    if not os.path.exists(file_path):
        return {"success": False, "error": "Sample file not found on disk."}
    with open(file_path, "rb") as f:
        contents = f.read()
    
    # Send contents through the exact same logic block as /analyze (mocking CSV parsing)
    df = pd.read_csv(io.BytesIO(contents))
    df.columns = df.columns.str.strip().str.lower()
    
    amount_col = None
    for col in df.columns:
        if "amount" in col or "debit" in col: amount_col = col; break
    if not amount_col:
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]): amount_col = col; break
    
    df["amount"] = pd.to_numeric(df[amount_col], errors="coerce").abs()
    
    date_col = None
    for col in df.columns:
        if "date" in col or "time" in col: date_col = col; break
    if date_col: df["date"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    else: df["date"] = pd.NaT
        
    desc_col = None
    for col in df.columns:
        if any(k in col for k in ["desc", "narr", "particular", "merchant"]): desc_col = col; break
    if desc_col: df["description"] = df[desc_col].astype(str)
    else: df["description"] = "Unknown"
        
    df = df.dropna(subset=["amount"])
    df = df[df["amount"] > 0]
    df["category"] = df["description"].apply(classify_category)
    df["type"] = "debit"
    if "id" not in df.columns: df["id"] = [str(uuid.uuid4()) for _ in range(len(df))]
    if "user_mark" not in df.columns: df["user_mark"] = "unknown"
        
    df_safe = df.astype(object).where(pd.notnull(df), None)
    memory_db["transactions"] = df_safe.to_dict(orient="records")
    
    result = detect_leaks(df)
    result["transactions"] = memory_db["transactions"]
    result["necessary_spend"] = 0.0
    result["unnecessary_spend"] = 0.0
    result["budget"] = memory_db.get("budget", 50000.0)
    memory_db["analysis"] = result
    save_db(memory_db)
    
    # Dispatch Automated SMS if system is linked
    if memory_db.get("phone"):
        msg = f"BLEEDX UPLOAD: Analysis Complete.\nLeak Score: {result['leak_score']}%.\nWaste: ₹{result['leak_amount']:,.0f}.\nSystemic budget threshold tested. Review terminal for override protocols."
        dispatch_sms(memory_db["phone"], msg)
    
    return result

@app.get("/analysis")
async def get_analysis():
    if not memory_db["transactions"]:
        return {"success": False, "error": "No data analyzed yet."}
    
    df = pd.DataFrame(memory_db["transactions"])
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
    result = detect_leaks(df)
    result["transactions"] = memory_db["transactions"]

    # Calculate necessary / unnecessary
    necessary_spend = sum(t["amount"] for t in memory_db["transactions"] if t.get("user_mark") == "necessary")
    unnecessary_spend = sum(t["amount"] for t in memory_db["transactions"] if t.get("user_mark") == "unnecessary")
    result["necessary_spend"] = float(necessary_spend)
    result["unnecessary_spend"] = float(unnecessary_spend)
    result["budget"] = memory_db.get("budget", 50000.0)
    
    return result

@app.post("/set-budget")
async def set_budget(data: dict):
    try:
        budget_val = float(data.get("budget", 50000.0))
        memory_db["budget"] = budget_val
        save_db(memory_db)
        return {"success": True, "budget": budget_val}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/register-sms")
async def register_sms(data: dict):
    phone = data.get("phone")
    if not phone:
        return {"success": False, "error": "No phone provided"}
    
    memory_db["phone"] = phone
    save_db(memory_db)
    
    dispatch_sms(phone, "BLEEDX AUTH: Terminal linked successfully. You will now receive secure financial leak thresholds via SMS override.")
    return {"success": True}

@app.post("/send-sms-report")
async def send_sms_report():
    phone = memory_db.get("phone")
    if not phone: 
        return {"success": False, "error": "No phone registered"}
    
    analysis = memory_db.get("analysis", {})
    if not analysis:
        return {"success": False, "error": "No data analyzed yet."}
        
    leak_score = analysis.get("leak_score", 0)
    leak_amt = analysis.get("leak_amount", 0)
    burn_pct = round((analysis.get("total_spend", 0) / analysis.get("budget", 50000.0)) * 100, 1)
    
    msg = f"BLEEDX STATUS 🚨\nTerminal Leak: {leak_score}%\nBleed: ₹{leak_amt:,.0f}\nBurn Velocity: {burn_pct}%\nLog in immediately to execute detox constraints."
    
    dispatch_sms(phone, msg)
    return {"success": True, "message": "SMS Dispatched"}

@app.post("/mark-transaction")
async def mark_transaction(mark: TransactionMark):
    updated = False
    for tx in memory_db.get("transactions", []):
        if tx["id"] == mark.id:
            tx["status"] = mark.status
            updated = True
            break
    if updated:
        save_db(memory_db)
    return {"success": updated}

@app.post("/terminate-sub")
async def terminate_sub(data: dict):
    desc = data.get("description")
    analysis = memory_db.get("analysis")
    if not analysis: return {"success": False}
    
    amount_reclaimed = 0
    # Clean up leaks array
    for leak in analysis.get("leaks", []):
        if leak.get("type") == "Recurring / Subscriptions":
            new_details = []
            for d in leak.get("details", []):
                if d["description"] == desc:
                    amount_reclaimed += (d["amount"] * d["count"])
                else:
                    new_details.append(d)
            leak["details"] = new_details
            
            leak["amount"] = sum(d["amount"] * d["count"] for d in leak["details"])
            leak["count"] = sum(d["count"] for d in leak["details"])

    if amount_reclaimed > 0:
        analysis["leak_amount"] -= amount_reclaimed
        if analysis["leak_amount"] < 0: analysis["leak_amount"] = 0
        
        if analysis["total_spend"] > 0:
            analysis["leak_score"] = min(100, max(0, (analysis["leak_amount"] / analysis["total_spend"]) * 100))
            
    if "Subscriptions" in analysis.get("category_spend", {}):
        analysis["category_spend"]["Subscriptions"] -= amount_reclaimed
        if analysis["category_spend"]["Subscriptions"] < 0: 
            analysis["category_spend"]["Subscriptions"] = 0
            
    sorted_cats = sorted(analysis.get("category_spend", {}).items(), key=lambda x: x[1], reverse=True)
    new_top = []
    for cat, amount in sorted_cats[:5]:
        pct = (amount / analysis["total_spend"] * 100) if analysis["total_spend"] > 0 else 0
        new_top.append({"category": cat, "amount": float(amount), "percentage": round(pct, 1), "count": 1})
    analysis["top_categories"] = new_top

    memory_db["analysis"] = analysis
    save_db(memory_db)
    
    if memory_db.get("phone"):
        msg = f"BLEEDX TERMINATION: Simulated closed bounds against {desc}. Reclaimed rs.{amount_reclaimed:,.0f}. Structural Leak score dropped to {analysis['leak_score']:,.1f}%."
        dispatch_sms(memory_db["phone"], msg)

    return {"success": True, "analysis": analysis, "reclaimed": amount_reclaimed}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
