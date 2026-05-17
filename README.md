# 💸 SplitWise — Smart Expense Splitter

A web app to split expenses fairly among friends — built with Python (Flask) and HTML/CSS/JS.  
BMCC Introduction to Computer Science — Final Project, Spring 2026.

---

## How to Run

```bash
pip install flask
python3 app.py
```
Then open **http://localhost:5000** in your browser.

---

## What it does

- Add people and reuse them across different events
- Create events (e.g. *Night Out*) with sub-activities (*Dinner*, *Bowling*, *Uber*)
- Exclude people from specific activities or expenses
- Multiple people can pay for one expense — each enters what they actually paid
- Automatically calculates who owes whom and the simplest way to settle up

---

## Project Structure

splitwise/
├── app.py              # Python backend — all logic
├── templates/
│   └── index.html      # HTML template
└── static/
├── style.css       # Styling
└── app.js          # UI interactions

---

## Built With

- Python 3 + Flask
- HTML, CSS, JavaScript
- No database — data saved to a JSON file