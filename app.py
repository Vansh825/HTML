import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
DB_NAME = "ewaste.db"

# 1. Price Dataset (Fair Market Baseline Rates per Kg)
PRICE_RATES = {
    "PCBs / मदरबोर्ड": 280,      # High value: Copper, Gold, Tantalum
    "Batteries / बैटरी": 95,     # Lithium, Cobalt, Lead
    "Cables / तार": 140,         # Copper
    "CRT / पुराना टीवी": 25,     # Glass, Lead handling
    "Motors / मोटर": 45,         # Copper, Magnets
    "Mixed Plastics / प्लास्टिक": 18
}

# 2. Authorized Recycler Dataset (JNARDDC / CPCB Registered)
RECYCLERS = [
    {
        "name": "Eco-Logic Authorized Recyclers",
        "contact": "+91 98765 43210",
        "auth_id": "REG-CPCB-2024-091",
        "accepts": ["PCBs / मदरबोर्ड", "Batteries / बैटरी", "Cables / तार"]
    },
    {
        "name": "Green Earth Safe Dismantlers",
        "contact": "+91 91234 56789",
        "auth_id": "REG-CPCB-2023-412",
        "accepts": ["CRT / पुराना टीवी", "Motors / मोटर", "Mixed Plastics / प्लास्टिक"]
    }
]

def init_db():
    """Initializes the Material & Transaction Dataset in SQLite"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id TEXT,
            collector_id TEXT,
            category TEXT,
            weight REAL,
            estimated_value REAL,
            recycler_name TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/", methods=["GET", "POST"])
def index():
    lots = []
    
    if request.method == "POST":
        category = request.form.get("category")
        weight = float(request.form.get("weight", 0))
        
        # Fair valuation logic
        rate_per_kg = PRICE_RATES.get(category, 0)
        estimated_val = round(weight * rate_per_kg, 2)
        
        # Match with an authorized recycler
        matched_recycler = "Local Approved Aggregator"
        for r in RECYCLERS:
            if category in r["accepts"]:
                matched_recycler = f"{r['name']} ({r['auth_id']})"
                break
        
        lot_id = f"LOT-{sqlite3.connect(DB_NAME).total_changes + 101}"
        
        # Save to database (Transaction Dataset)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (lot_id, collector_id, category, weight, estimated_value, recycler_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (lot_id, "COLL-01", category, weight, estimated_val, matched_recycler, "Ready for Handover"))
        conn.commit()
        conn.close()
        
        return redirect(url_for("index"))

    # Fetch transaction ledger
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT lot_id, category, weight, estimated_value, recycler_name, status FROM transactions ORDER BY id DESC")
    lots = cursor.fetchall()
    conn.close()

    return render_template("index.html", rates=PRICE_RATES, recyclers=RECYCLERS, lots=lots)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
