import sqlite3
import os
import io
import base64
import qrcode
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)
DB_NAME = "ewaste.db"

# Master Material & Fair Price Dataset (per Kg)
PRICE_RATES = {
    "PCBs / मदरबोर्ड": {"rate": 280, "icon": "🖥️", "hazard": "डू नॉट बर्न (Do not burn). Contains copper, gold & lead."},
    "Batteries / लिथियम बैटरी": {"rate": 110, "icon": "🔋", "hazard": "आग का खतरा (Fire hazard). Do not puncture or crush."},
    "Cables / तांबे के तार": {"rate": 145, "icon": "🔌", "hazard": "तार न जलाएं (No open burning). Extract mechanically."},
    "CRT / पुराना टीवी": {"rate": 30, "icon": "📺", "hazard": "सीसा और कांच का खतरा (Toxic leaded glass). Do not smash."},
    "Motors / मोटर और चुंबक": {"rate": 55, "icon": "⚙️", "hazard": "Heavy metals. Wear gloves while sorting."},
    "Mixed Plastics / प्लास्टिक": {"rate": 20, "icon": "🛢️", "hazard": "Keep away from heat sources."}
}

# Master Registered Recyclers (CPCB/JNARDDC aligned)
RECYCLERS = [
    {
        "id": "REC-101",
        "name": "Eco-Logic Safe Recyclers",
        "reg_id": "REG-CPCB-2024-091",
        "distance": "2.4 km दूर",
        "accepts": ["PCBs / मदरबोर्ड", "Batteries / लिथियम बैटरी", "Cables / तांबे के तार"]
    },
    {
        "id": "REC-102",
        "name": "Green Earth Safe Dismantlers",
        "reg_id": "REG-CPCB-2023-412",
        "distance": "4.1 km दूर",
        "accepts": ["CRT / पुराना टीवी", "Motors / मोटर और चुंबक", "Mixed Plastics / प्लास्टिक"]
    }
]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id TEXT UNIQUE,
            collector_id TEXT,
            category TEXT,
            weight REAL,
            estimated_value REAL,
            recycler_name TEXT,
            qr_base64 TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def generate_qr(text_data):
    """Generates a verifiable Base64 QR code for digital handover records"""
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(text_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1b5e20", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        category = request.form.get("category")
        try:
            weight = float(request.form.get("weight", 0))
        except ValueError:
            weight = 0.0

        item_info = PRICE_RATES.get(category, {"rate": 0})
        rate = item_info["rate"]
        estimated_value = round(weight * rate, 2)

        # Match nearest certified recycler
        matched_rec = "Approved Local Aggregator"
        for rec in RECYCLERS:
            if category in rec["accepts"]:
                matched_rec = f"{rec['name']} ({rec['distance']})"
                break

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM lots")
        count = cursor.fetchone()[0]
        lot_id = f"EPR-{count + 1001}"

        # Digital verifiable manifest embedded in QR
        qr_manifest = f"LOT:{lot_id}|CAT:{category}|WT:{weight}kg|VAL:INR {estimated_value}|RECYCLER:{matched_rec}"
        qr_img = generate_qr(qr_manifest)

        cursor.execute("""
            INSERT INTO lots (lot_id, collector_id, category, weight, estimated_value, recycler_name, qr_base64, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (lot_id, "COLL-DELHI-07", category, weight, estimated_value, matched_rec, qr_img, "Ready for Handover"))
        conn.commit()
        conn.close()

        return redirect(url_for("index"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT lot_id, category, weight, estimated_value, recycler_name, qr_base64, status FROM lots ORDER BY id DESC")
    lots = cursor.fetchall()
    conn.close()

    total_earnings = sum([row[3] for row in lots if row[6] == "Verified & Paid"])
    pending_earnings = sum([row[3] for row in lots if row[6] != "Verified & Paid"])

    return render_template("index.html", 
                           rates=PRICE_RATES, 
                           recyclers=RECYCLERS, 
                           lots=lots,
                           total_earnings=total_earnings,
                           pending_earnings=pending_earnings)

# Endpoint for the Recycler to verify material handover
@app.route("/verify/<lot_id>", methods=["POST"])
def verify_lot(lot_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE lots SET status = 'Verified & Paid' WHERE lot_id = ?", (lot_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
