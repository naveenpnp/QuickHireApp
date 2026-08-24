# QuickHire — Hyperlocal Same-Day Work & Hiring Platform

QuickHire is a local full-stack web application designed for on-demand, same-day job matching and execution. It features a unique **single-account dual-role model** (one account can both post jobs and work on jobs), an automated **demo escrow wallet system**, **smart payment calculation** (prorating for late arrivals and overtime), and a **reputation/reliability score engine**.

---

## 🏗️ Project Architecture

Strict three-tier folder layout:

```
quickhire/
├── frontend/
│   ├── templates/          # Jinja2 HTML templates
│   │   ├── base.html       # Master layout with navbar & alerts
│   │   ├── index.html      # Landing hero & urgent jobs feed
│   │   ├── login.html      # Login with 1-click demo switcher
│   │   ├── register.html   # User registration
│   │   ├── dashboard.html  # Action center & balance cards
│   │   ├── jobs.html       # Search & category filter
│   │   ├── job_details.html# Interactive job & applicant management
│   │   ├── post_job.html   # Post job with escrow calculator
│   │   ├── profile.html    # Reliability score & review showcase
│   │   ├── applications.html# My applications tracker
│   │   ├── my_jobs.html    # 4-tab activity center
│   │   ├── wallet.html     # Wallet, Escrow, and transaction ledger
│   │   └── reviews.html    # Rating & feedback center
│   └── static/
│       ├── css/style.css   # Custom modern design system
│       ├── js/script.js    # Interactive simulation helpers & calculators
│       └── images/logo.svg # QuickHire branding
├── backend/
│   ├── app.py              # Flask app factory, config & routes registration
│   ├── models.py           # SQLite data access layer
│   ├── requirements.txt    # Flask & Werkzeug dependencies
│   ├── routes/             # Feature blueprints
│   │   ├── auth_routes.py
│   │   ├── main_routes.py
│   │   ├── job_routes.py
│   │   ├── application_routes.py
│   │   ├── assignment_routes.py
│   │   ├── wallet_routes.py
│   │   ├── profile_routes.py
│   │   └── review_routes.py
│   └── services/           # Business logic & math
│       ├── payment_service.py     # Smart payment calculation (Cases 1, 2, 3)
│       ├── reliability_service.py # Scoring, penalties & ratings
│       └── auth_service.py        # Authentication & session guards
├── database/
│   ├── schema.sql          # 7 SQLite tables (users, categories, jobs, applications, assignments, reviews, transactions)
│   ├── seed.py             # Demo users & starter jobs
│   ├── init_db.py          # Idempotent database initialization
│   └── quickhire.db        # SQLite database file
├── run.sh                  # macOS/Linux one-command runner
├── run.bat                 # Windows one-command runner
└── README.md
```

---

## ⚡ Quick Start Instructions

### 1. Automated Run (Recommended)

**Windows:**
Double click `run.bat` or in PowerShell / Command Prompt:
```cmd
run.bat
```

**macOS / Linux:**
```bash
chmod +x run.sh
./run.sh
```

### 2. Manual Step-by-Step Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Initialize database & seed demo data (Idempotent)
python database/init_db.py

# 4. Start the Flask application
python backend/app.py
```

Open your browser at **`http://127.0.0.1:5000`**.

> **Same Wi-Fi Network Access:**
> To test from a phone or other device on the same local network, access `http://<your-laptop-ip>:5000`.

---

## 🔑 Demo Login Credentials

The database is pre-seeded with two demo accounts with ₹5,000 initial balance:

| Name | Email | Password | City | Initial Balance |
|---|---|---|---|---|
| **Arun Kumar** | `arun@gmail.com` | `123456` | Trichy | ₹5,000.00 |
| **Rahul Sharma** | `rahul@gmail.com` | `123456` | Chennai | ₹5,000.00 |

*(You can also use the 1-click login buttons on the login page for instant sign-in).*

---

## 💡 Complete Step-by-Step Demo Flow Script

Follow this sequence to showcase the full end-to-end workflow:

### Step 1: Post a Job with Escrow Security
1. Log in as **Arun Kumar** (`arun@gmail.com`).
2. Click **Post a Job** in the navbar.
3. Enter title: *"Event Assistant for College Fest"*, Category: *Event Work*, Payment: *₹900*, Workers: *1*, Location: *Trichy*, check **Mark as URGENT**.
4. Notice that **₹900** is deducted from Arun's *Available Balance* and placed into *Secured Escrow*.
5. Log out.

### Step 2: Apply for the Job as a Worker
1. Log in as **Rahul Sharma** (`rahul@gmail.com`).
2. Click **Browse Jobs**, find Arun's job, and click **View & Apply**.
3. Click **Apply for this Job**.
4. Log out.

### Step 3: Select Worker
1. Log back in as **Arun**.
2. Go to **Dashboard** or **My Jobs** &rarr; open the job details.
3. In the **Applicants** section, review Rahul's reliability score and click **Select Worker**.
4. Log out.

### Step 4: Clock In & Complete Job with Smart Payment
1. Log in as **Rahul**.
2. Go to **Dashboard** or **My Jobs &rarr; Active Gigs** &rarr; open the job details.
3. In the **Worker Action Panel**:
   - Click **Start Job (Clock In)** (or pick preset *30m Late Start* to simulate late arrival).
   - Click **Complete Job & Calculate Pay** (choose between *Case 1: Full hours*, *Case 2: Late with makeup hours*, or *Case 3: Late without makeup hours*).
4. View the **Smart Payment Calculation** summary.
5. Log out.

### Step 5: Poster Confirms & Escrow Releases
1. Log back in as **Arun**.
2. On your **Dashboard**, see the *"Work Completed — Action Required"* banner.
3. Click **Review & Confirm**.
4. In the confirmation modal, confirm payment release.
5. Notice that ₹900 (or prorated pay) moves into Rahul's wallet balance!
6. Leave a 5-star review for Rahul.

### Step 6: Verify Wallets & Reviews
- Check Rahul's **Wallet** at `/wallet` to see the +₹900 Credit transaction.
- Check Rahul's **Profile** at `/profile` to see the updated completed job count (+1), reliability score (+1), and the new star rating.

---

## 🧮 Smart Payment Calculation Rules (§7)

- **Case 1 (On-Time):** `actual_start <= scheduled_start` and `actual_hours >= scheduled_hours` &rarr; 100% pay, `late=False`.
- **Case 2 (Late with Makeup Duration):** Worker arrived late but stayed late to complete the full scheduled hours &rarr; 100% pay, `late=True` (-2 reliability penalty).
- **Case 3 (Late without Makeup Duration):** Worker arrived late and left at scheduled end &rarr; `payment = scheduled_payment * (actual_hours / scheduled_hours)`, `late=True`.

---

## 🛡️ Business Rules Enforced (§6)

1. A user cannot apply to their own job.
2. A user cannot apply twice to the same job.
3. A job cannot have more selected workers than `required_workers`.
4. Only a selected worker can start a job.
5. A worker must start before they can complete.
6. A completed job's payment cannot be paid twice.
7. Payment moves from escrow to worker wallet **only** on poster confirmation.
8. No-show workers receive ₹0; funds remain secured for the poster.
9. No-show penalizes worker reliability by -10 points and reopens the job slot.
10. Confirmed completion increases `completed_jobs` by 1 and reliability by +1.
11. Late arrival decreases reliability by -2 points and is flagged in review logs.
