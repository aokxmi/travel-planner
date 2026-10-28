import re
import sys
import textwrap
import requests
from flask import Flask, request, render_template_string

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e4b"


# ---------- Gemma call ----------
def plan_trip(destination, days, budget, interest):
    prompt = textwrap.dedent(f"""\
        You are my travel planner.
        Destination: {destination}
        Days: {days}
        Budget: Rs {budget} total
        Interests: {interest}

        Rules:
        - Plan 3 activities per day: morning, afternoon, evening.
        - Give an estimated cost for each activity, plus a stay and local transport for each day.
        - Write every cost as Rs and a plain number with no commas, like Rs 1300.
        - Keep the total under the budget.
        - End with one line: Total: Rs <number>

        Format:
        Day 1
        - Morning: <activity> (Rs <cost>)
        - Afternoon: <activity> (Rs <cost>)
        - Evening: <activity> (Rs <cost>)
        - Stay: <place, area> (Rs <cost>)
        - Transport: <how> (Rs <cost>)

        Total: Rs <number>

        Output only the itinerary.""")

    r = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False},
        timeout=300,
    )
    return r.json()["response"]


# Price check
def to_number(s):
    return int(s.replace(",", ""))


def check_budget(text):
    """Return (python_sum, model_total). model_total is None if missing."""
    body, _, total_line = text.partition("Total:")
    items = re.findall(r"Rs\s*([\d,]+)", body)
    python_sum = sum(to_number(x) for x in items)
    claimed = re.findall(r"Rs\s*([\d,]+)", total_line)
    model_total = to_number(claimed[0]) if claimed else None
    return python_sum, model_total


def parse_itinerary(text):
    """Turn the model's text into [{'n': '1', 'items': [...], 'total': 0}].
    Returns [] if the text doesn't look like an itinerary."""
    body = text.partition("Total:")[0]
    days = []
    for line in body.splitlines():
        line = line.strip().lstrip("*# ").strip()
        m = re.match(r"day\s*(\d+)", line, re.I)
        if m:
            days.append({"n": m.group(1), "items": [], "total": 0})
            continue
        m = re.match(r"[-*\u2022]\s*\**([A-Za-z ]+?)\**\s*:\s*\**\s*(.+)", line)
        if m and days:
            label, rest = m.groups()
            cost = re.findall(r"Rs\s*([\d,]+)", rest)
            amount = to_number(cost[-1]) if cost else 0
            desc = re.sub(r"\(?\s*Rs\s*[\d,]+\s*\)?", "", rest).strip(" -:*")
            days[-1]["items"].append(
                {"label": label.strip(), "desc": desc, "cost": amount}
            )
            days[-1]["total"] += amount
    return [d for d in days if d["items"]]


# UI
app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trip Planner</title>
<style>
  :root {
    --ink: #14233b; --muted: #5d6b82; --paper: #f2f6f9; --card: #ffffff;
    --line: #d5dde6; --sea: #0e7c86; --sea-soft: #dff1f2;
    --sun: #e8a33d; --over: #c2412d;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ink: #e8eef6; --muted: #9aa8bd; --paper: #0f1a2b; --card: #17263c;
      --line: #2a3b55; --sea: #4fc1cb; --sea-soft: #173a46;
      --sun: #f0b45a; --over: #ef7a66;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--paper); color: var(--ink);
    font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  main { max-width: 880px; margin: 0 auto; padding: 40px 20px 64px; }
  h1 {
    font: 600 clamp(2rem, 5vw, 3rem)/1.1 Georgia, "Iowan Old Style", serif;
    margin: 0 0 8px; letter-spacing: -0.01em;
  }
  .lede { color: var(--muted); margin: 0 0 28px; max-width: 52ch; }
  form {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 14px; background: var(--card); border: 1px solid var(--line);
    border-radius: 14px; padding: 20px;
  }
  label { display: grid; gap: 6px; font-size: .9rem; color: var(--muted); }
  input {
    font: inherit; color: var(--ink); background: var(--paper);
    border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px;
  }
  input:focus-visible, button:focus-visible {
    outline: 3px solid var(--sea); outline-offset: 2px;
  }
  .wide { grid-column: 1 / -1; }
  button {
    grid-column: 1 / -1; font: inherit; font-weight: 600; cursor: pointer;
    background: var(--sea); color: #fff; border: 0; border-radius: 10px;
    padding: 12px 18px;
  }
  button[disabled] { opacity: .7; cursor: progress; }
  html[data-theme="x"] button { color: #000; }
  .error {
    margin-top: 20px; padding: 14px 16px; border-radius: 10px;
    border: 1px solid var(--over); color: var(--over);
  }
  .meter { margin: 32px 0 8px; }
  .meter h2 { font: 600 1.1rem/1.3 Georgia, serif; margin: 0 0 12px; }
  .bar {
    height: 14px; border-radius: 7px; background: var(--sea-soft);
    overflow: hidden; border: 1px solid var(--line);
  }
  .bar span { display: block; height: 100%; background: var(--sea); }
  .bar.over span { background: var(--over); }
  .nums { display: flex; flex-wrap: wrap; gap: 8px 28px; margin-top: 10px; }
  .nums div { color: var(--muted); font-size: .9rem; }
  .nums b { display: block; color: var(--ink); font-size: 1.25rem; }
  .mismatch { color: var(--sun); font-size: .9rem; margin-top: 6px; }
  .day {
    margin-top: 22px; background: var(--card); border: 1px solid var(--line);
    border-radius: 14px; overflow: hidden;
  }
  .day header {
    display: flex; justify-content: space-between; align-items: baseline;
    padding: 14px 20px; border-bottom: 1px solid var(--line);
    background: var(--sea-soft);
  }
  .day h3 { margin: 0; font: 600 1.25rem/1.2 Georgia, serif; }
  .day header span { color: var(--muted); font-size: .9rem; }
  .row {
    display: grid; grid-template-columns: 110px 1fr auto; gap: 14px;
    padding: 12px 20px; border-top: 1px solid var(--line);
  }
  .row:first-of-type { border-top: 0; }
  .row .l { color: var(--sea); font-weight: 600; }
  .row .c { font-variant-numeric: tabular-nums; white-space: nowrap; }
  @media (max-width: 560px) {
    .row { grid-template-columns: 1fr auto; }
    .row .l { grid-column: 1 / -1; }
  }
  pre {
    white-space: pre-wrap; background: var(--card); border: 1px solid var(--line);
    border-radius: 14px; padding: 18px; margin-top: 22px; font: inherit;
  }
  .note { color: var(--muted); font-size: .85rem; margin-top: 24px; }
</style>
</head>
<body>
<main>
  <h1>Plan a trip in one go</h1>
  <p class="lede">Tell us where, how long and what you like. A local Gemma model writes
  the plan, and Python checks that the costs fit your budget.</p>

  <form method="post" id="f">
    <label>Destination
      <input name="destination" value="{{ v.destination }}" placeholder="Goa" required>
    </label>
    <label>Days
      <input name="days" type="number" min="1" max="14" value="{{ v.days }}" required>
    </label>
    <label>Budget (Rs)
      <input name="budget" type="number" min="1" value="{{ v.budget }}" required>
    </label>
    <label class="wide">Interests
      <input name="interest" value="{{ v.interest }}" placeholder="beaches, seafood, nightlife" required>
    </label>
    <button id="b">Plan my trip</button>
  </form>

  {% if error %}<div class="error" role="alert">{{ error }}</div>{% endif %}

  {% if result %}
    <section class="meter" aria-label="Budget check">
      <h2>Budget check</h2>
      <div class="bar {{ 'over' if over else '' }}">
        <span style="width: {{ pct }}%"></span>
      </div>
      <div class="nums">
        <div><b>Rs {{ py_sum }}</b>planned spend (added up by Python)</div>
        <div><b>Rs {{ budget }}</b>your budget</div>
        {% if model_total is not none %}<div><b>Rs {{ model_total }}</b>total the model claimed</div>{% endif %}
      </div>
      {% if over %}<div class="mismatch">This plan goes over your budget. Try again or raise the budget.</div>{% endif %}
      {% if model_total is not none and model_total != py_sum %}
        <div class="mismatch">The model's own total doesn't match the items, so trust the Python figure.</div>
      {% endif %}
    </section>

    {% if days_data %}
      {% for d in days_data %}
        <article class="day">
          <header><h3>Day {{ d.n }}</h3><span>Rs {{ d.total }}</span></header>
          {% for it in d['items'] %}
            <div class="row">
              <div class="l">{{ it.label }}</div>
              <div>{{ it.desc }}</div>
              <div class="c">Rs {{ it.cost }}</div>
            </div>
          {% endfor %}
        </article>
      {% endfor %}
    {% else %}
      <pre>{{ result }}</pre>
    {% endif %}
    <p class="note">Prices are AI estimates. Check them before you book anything.</p>
  {% endif %}
</main>
<script>
  document.getElementById('f').addEventListener('submit', function () {
    var b = document.getElementById('b');
    b.textContent = 'Planning your trip... this takes about 20 seconds';
    setTimeout(function () { b.disabled = true; }, 0);
  });
</script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    v = {"destination": "", "days": 3, "budget": 15000, "interest": ""}
    ctx = {}
    if request.method == "POST":
        try:
            v = {
                "destination": request.form["destination"],
                "days": int(request.form["days"]),
                "budget": int(request.form["budget"]),
                "interest": request.form["interest"],
            }
            text = plan_trip(v["destination"], v["days"], v["budget"], v["interest"])
            py_sum, model_total = check_budget(text)
            pct = min(100, round(py_sum / v["budget"] * 100)) if v["budget"] else 0
            ctx = dict(
                result=text,
                days_data=parse_itinerary(text),
                py_sum=py_sum,
                model_total=model_total,
                budget=v["budget"],
                pct=pct,
                over=py_sum > v["budget"],
            )
        except requests.exceptions.ConnectionError:
            ctx = dict(error="Can't reach Ollama. Start it with: sudo systemctl start ollama")
        except Exception as e:
            ctx = dict(error=f"Something went wrong: {e}")
    return render_template_string(PAGE, v=v, **ctx)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        d = input("Where to? ")
        n = int(input("How many days? "))
        b = int(input("Budget in Rs? "))
        i = input("Interests? ")
        out = plan_trip(d, n, b, i)
        print(out)
        print("Python sum / model total:", check_budget(out))
    else:
        app.run(debug=True)
