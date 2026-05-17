"""
Run:  pip install flask
      python app.py
Open: http://localhost:5000
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
import json, os, uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = "splitwise-bmcc-2026"

# ── In-memory data store (saved to JSON file) ─────
DATA_FILE = "splitwise_data.json"

COLORS = [
    "#7c6dfa","#fa6d9a","#6dfabc","#fadb6d",
    "#6db8fa","#fa9a6d","#c86dfa","#6dfad4"
]

# ══════════════════════════════════════════════════
#  DATA HELPERS
# ══════════════════════════════════════════════════

def load_data():
    """Load data from JSON file, or return empty structure."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"people": [], "events": []}


def save_data(data):
    """Persist data to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def new_id():
    return uuid.uuid4().hex[:7]


def person_color(data, person_id):
    """Return a consistent color for a person based on their index."""
    ids = [p["id"] for p in data["people"]]
    idx = ids.index(person_id) if person_id in ids else 0
    return COLORS[idx % len(COLORS)]


def initials(name):
    parts = name.strip().split()
    return "".join(w[0] for w in parts).upper()[:2]


def get_person(data, pid):
    return next((p for p in data["people"] if p["id"] == pid), None)


def get_event(data, eid):
    return next((e for e in data["events"] if e["id"] == eid), None)


def get_sub(event, sid):
    return next((s for s in event["subs"] if s["id"] == sid), None)


# ══════════════════════════════════════════════════
#  ALGORITHM: BALANCE CALCULATION
#  (selection + iteration)
# ══════════════════════════════════════════════════

def calculate_event_balances(data, event):
    """
    For every expense in every sub-activity:
      - Determine included participants
        (event members minus sub excludes minus expense excludes).
      - Each payer GAINS the amount they paid.
      - Each included person LOSES their equal share of the total.
    Net balance = total gained − total lost.
    Uses both SELECTION (who is included/excluded) and
    ITERATION (over every expense, payer, and participant).
    """
    balances = {mid: 0.0 for mid in event["members"]}

    for sub in event["subs"]:
        sub_excluded = set(sub.get("excludes", []))

        for exp in sub["expenses"]:
            exp_excluded = set(exp.get("excludes", []))

            # Selection: determine who shares this expense
            included = [
                mid for mid in event["members"]
                if mid not in sub_excluded and mid not in exp_excluded
            ]
            if not included:
                continue

            total_paid = sum(p["amount"] for p in exp["payers"])
            share = total_paid / len(included)

            # Iteration: payers gain what they paid
            for payer in exp["payers"]:
                if payer["personId"] in balances:
                    balances[payer["personId"]] += payer["amount"]

            # Iteration: every included person loses their share
            for mid in included:
                balances[mid] -= share

    # Round to cents
    return {k: round(v, 2) for k, v in balances.items()}


# ══════════════════════════════════════════════════
#  ALGORITHM: SETTLEMENT (greedy two-pointer)
#  (selection + iteration)
# ══════════════════════════════════════════════════

def calculate_settlements(balances):
    """
    Greedy two-pointer algorithm:
      - Selection: separate members into debtors (owe money)
        and creditors (are owed money).
      - Sort both groups descending by magnitude.
      - Iteration: repeatedly match largest debtor with largest
        creditor, transfer min(debt, credit), advance whichever
        side is fully settled.
    Produces the MINIMUM number of transactions to settle all debts.
    """
    settlements = []

    debtors   = sorted(
        [(m, -b) for m, b in balances.items() if b < -0.01],
        key=lambda x: x[1], reverse=True
    )
    creditors = sorted(
        [(m,  b) for m, b in balances.items() if b >  0.01],
        key=lambda x: x[1], reverse=True
    )

    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor,   debt   = debtors[i]
        creditor, credit = creditors[j]

        transfer = min(debt, credit)
        settlements.append({
            "from":   debtor,
            "to":     creditor,
            "amount": round(transfer, 2)
        })

        debt   -= transfer
        credit -= transfer
        debtors[i]   = (debtor,   debt)
        creditors[j] = (creditor, credit)

        if debt   < 0.01: i += 1
        if credit < 0.01: j += 1

    return settlements


# ══════════════════════════════════════════════════
#  TEMPLATE CONTEXT HELPERS
# ══════════════════════════════════════════════════

def enrich(data):
    """
    Add display helpers (color, initials, totals) to every
    object so templates stay logic-free.
    """
    for p in data["people"]:
        p["color"]    = person_color(data, p["id"])
        p["initials"] = initials(p["name"])

    for ev in data["events"]:
        ev["total"] = round(sum(
            sum(p["amount"] for p in exp["payers"])
            for sub in ev["subs"]
            for exp in sub["expenses"]
        ), 2)
        ev["exp_count"] = sum(len(s["expenses"]) for s in ev["subs"])

        for mid in ev["members"]:
            person = get_person(data, mid)
            if person and "color" not in person:
                person["color"]    = person_color(data, mid)
                person["initials"] = initials(person["name"])

        for sub in ev["subs"]:
            sub["total"] = round(sum(
                sum(p["amount"] for p in exp["payers"])
                for exp in sub["expenses"]
            ), 2)
            sub_excluded = set(sub.get("excludes", []))
            sub["included_ids"] = [m for m in ev["members"] if m not in sub_excluded]

            for exp in sub["expenses"]:
                exp_excluded = set(exp.get("excludes", []))
                exp["included_ids"] = [
                    m for m in sub["included_ids"] if m not in exp_excluded
                ]
                exp["total"] = round(sum(p["amount"] for p in exp["payers"]), 2)
                exp["per_person"] = round(
                    exp["total"] / len(exp["included_ids"]), 2
                ) if exp["included_ids"] else 0

    return data


# ══════════════════════════════════════════════════
#  ROUTES — MAIN
# ══════════════════════════════════════════════════

@app.route("/")
def index():
    data = enrich(load_data())
    return render_template("index.html", data=data, active="people")


# ══════════════════════════════════════════════════
#  ROUTES — PEOPLE
# ══════════════════════════════════════════════════

@app.route("/people/add", methods=["POST"])
def add_person():
    data = load_data()
    name = request.form.get("name", "").strip().title()
    if not name:
        flash("Please enter a name.", "error")
    elif any(p["name"].lower() == name.lower() for p in data["people"]):
        flash(f'"{name}" already exists.', "error")
    else:
        data["people"].append({"id": new_id(), "name": name})
        save_data(data)
        flash(f"{name} added.", "success")
    return redirect(url_for("people_page"))


@app.route("/people/remove/<pid>", methods=["POST"])
def remove_person(pid):
    data = load_data()
    data["people"] = [p for p in data["people"] if p["id"] != pid]
    for ev in data["events"]:
        ev["members"] = [m for m in ev["members"] if m != pid]
        for sub in ev["subs"]:
            sub["excludes"] = [x for x in sub.get("excludes",[]) if x != pid]
            for exp in sub["expenses"]:
                exp["payers"]   = [p for p in exp["payers"]   if p["personId"] != pid]
                exp["excludes"] = [x for x in exp.get("excludes",[]) if x != pid]
    save_data(data)
    flash("Person removed.", "success")
    return redirect(url_for("people_page"))


@app.route("/people")
def people_page():
    data  = enrich(load_data())
    query = request.args.get("q", "").lower()
    people = [p for p in data["people"] if query in p["name"].lower()] if query else data["people"]
    return render_template("index.html", data=data, active="people",
                           people=people, query=query)


# ══════════════════════════════════════════════════
#  ROUTES — EVENTS
# ══════════════════════════════════════════════════

@app.route("/events")
def events_page():
    data = enrich(load_data())
    open_event = request.args.get("open")
    open_sub   = request.args.get("open_sub")
    return render_template("index.html", data=data, active="events",
                           open_event=open_event, open_sub=open_sub)


@app.route("/events/add", methods=["POST"])
def add_event():
    data    = load_data()
    name    = request.form.get("name", "").strip()
    icon    = request.form.get("icon", "🎉").strip() or "🎉"
    members = request.form.getlist("members")
    if not name:
        flash("Enter an event name.", "error")
    elif not members:
        flash("Select at least one member.", "error")
    else:
        data["events"].append({
            "id": new_id(), "name": name, "icon": icon,
            "members": members, "subs": []
        })
        save_data(data)
        flash(f'Event "{name}" created.', "success")
    return redirect(url_for("events_page"))


@app.route("/events/remove/<eid>", methods=["POST"])
def remove_event(eid):
    data = load_data()
    data["events"] = [e for e in data["events"] if e["id"] != eid]
    save_data(data)
    flash("Event deleted.", "success")
    return redirect(url_for("events_page"))


# ══════════════════════════════════════════════════
#  ROUTES — SUB-ACTIVITIES
# ══════════════════════════════════════════════════

@app.route("/events/<eid>/sub/add", methods=["POST"])
def add_sub(eid):
    data  = load_data()
    event = get_event(data, eid)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events_page"))
    name = request.form.get("name", "").strip()
    icon = request.form.get("icon", "🎯").strip() or "🎯"
    if not name:
        flash("Enter an activity name.", "error")
    else:
        event["subs"].append({
            "id": new_id(), "name": name, "icon": icon,
            "excludes": [], "expenses": []
        })
        save_data(data)
        flash(f'"{name}" added.', "success")
    return redirect(url_for("events_page", open=eid))


@app.route("/events/<eid>/sub/remove/<sid>", methods=["POST"])
def remove_sub(eid, sid):
    data  = load_data()
    event = get_event(data, eid)
    if event:
        event["subs"] = [s for s in event["subs"] if s["id"] != sid]
        save_data(data)
        flash("Activity removed.", "success")
    return redirect(url_for("events_page", open=eid))


@app.route("/events/<eid>/sub/<sid>/exclude/<pid>", methods=["POST"])
def toggle_sub_exclude(eid, sid, pid):
    data  = load_data()
    event = get_event(data, eid)
    sub   = get_sub(event, sid) if event else None
    if sub:
        excl = sub.setdefault("excludes", [])
        if pid in excl:
            excl.remove(pid)
        else:
            excl.append(pid)
        save_data(data)
    return redirect(url_for("events_page", open=eid, open_sub=sid))


# ══════════════════════════════════════════════════
#  ROUTES — EXPENSES
# ══════════════════════════════════════════════════

@app.route("/events/<eid>/sub/<sid>/expense/add", methods=["POST"])
def add_expense(eid, sid):
    data  = load_data()
    event = get_event(data, eid)
    sub   = get_sub(event, sid) if event else None
    if not sub:
        flash("Activity not found.", "error")
        return redirect(url_for("events_page", open=eid))

    desc     = request.form.get("desc", "").strip()
    excludes = request.form.getlist("excludes")

    # Collect payers: payer_id_<id> and payer_amt_<id>
    payers = []
    for key, val in request.form.items():
        if key.startswith("payer_id_"):
            suffix = key[len("payer_id_"):]
            amt_key = f"payer_amt_{suffix}"
            try:
                amt = float(request.form.get(amt_key, 0))
            except ValueError:
                amt = 0
            if amt > 0:
                payers.append({"personId": val, "amount": round(amt, 2)})

    if not desc:
        flash("Enter a description.", "error")
    elif not payers:
        flash("Add at least one payer with an amount.", "error")
    else:
        sub["expenses"].append({
            "id":       new_id(),
            "desc":     desc,
            "payers":   payers,
            "excludes": excludes,
            "date":     datetime.now().strftime("%b %d, %Y")
        })
        save_data(data)
        total = sum(p["amount"] for p in payers)
        flash(f'Expense "${total:.2f}" recorded.', "success")

    return redirect(url_for("events_page", open=eid, open_sub=sid))


@app.route("/events/<eid>/sub/<sid>/expense/remove/<idx>", methods=["POST"])
def remove_expense(eid, sid, idx):
    data  = load_data()
    event = get_event(data, eid)
    sub   = get_sub(event, sid) if event else None
    if sub:
        try:
            sub["expenses"].pop(int(idx))
            save_data(data)
            flash("Expense removed.", "success")
        except IndexError:
            pass
    return redirect(url_for("events_page", open=eid, open_sub=sid))


#  ROUTES — SUMMARY

@app.route("/summary")
@app.route("/summary/<eid>")
def summary_page(eid=None):
    data        = enrich(load_data())
    sel_event   = None
    balances    = {}
    settlements = []
    bal_display = []

    if eid:
        raw_data  = load_data()
        sel_event = get_event(raw_data, eid)
        if sel_event:
            balances    = calculate_event_balances(raw_data, sel_event)
            settlements = calculate_settlements(balances)
            # Enrich for display
            for mid, bal in balances.items():
                person = get_person(raw_data, mid)
                if not person:
                    continue
                bal_display.append({
                    "id":       mid,
                    "name":     person["name"],
                    "color":    person_color(raw_data, mid),
                    "initials": initials(person["name"]),
                    "balance":  bal,
                    "abs":      abs(bal),
                    "status":   "owed" if bal > 0.01 else ("owes" if bal < -0.01 else "settled")
                })
            for s in settlements:
                fp = get_person(raw_data, s["from"])
                tp = get_person(raw_data, s["to"])
                s["from_name"]     = fp["name"]     if fp else "?"
                s["from_color"]    = person_color(raw_data, s["from"])
                s["from_initials"] = initials(fp["name"]) if fp else "?"
                s["to_name"]       = tp["name"]     if tp else "?"
                s["to_color"]      = person_color(raw_data, s["to"])
                s["to_initials"]   = initials(tp["name"]) if tp else "?"
            sel_event = get_event(data, eid)  # enriched version

    total_spent  = sum(e["total"] for e in data["events"])
    total_people = len(data["people"])
    total_events = len(data["events"])

    return render_template("index.html",
        data=data, active="summary",
        sel_event=sel_event, eid=eid,
        bal_display=bal_display,
        settlements=settlements,
        total_spent=total_spent,
        total_people=total_people,
        total_events=total_events
    )


#  RESET

@app.route("/reset", methods=["POST"])
def reset():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    flash("All data reset.", "success")
    return redirect(url_for("index"))


#  RUN

if __name__ == "__main__":
    print("\n╔══════════════════════════════════════╗")
    print("║   SplitWise — Expense Splitter       ║")
    print("║   Open: http://localhost:5000         ║")
    print("╚══════════════════════════════════════╝\n")
    # app.run(debug=True, port=5000)
    if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
