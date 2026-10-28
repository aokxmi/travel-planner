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


# ---------- Python-side checks (the model never does the math) ----------
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


# ---------- Web UI ----------
app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trip planner</title>
<style>
  :root {
    --bg: #eceff7; --surface: #f4f6fb; --ink: #2b3042; --muted: #7a8196;
    --hi: rgba(255,255,255,.95); --lo: rgba(158,168,200,.55);
    --coral: #f7a48b; --coral-ink: #3d2620; --mint: #9bd9c0; --over: #ec8b86;
    --c-morning: #fbd9c8; --c-afternoon: #cdeede; --c-evening: #d9d6f5; --c-other: #dde3ee;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #1e2332; --surface: #252b3d; --ink: #e8ebf5; --muted: #9aa2ba;
      --hi: rgba(70,80,110,.55); --lo: rgba(8,10,20,.75);
      --coral: #f1967c; --coral-ink: #2a1712; --mint: #6fc4a6; --over: #ee847f;
      --c-morning: #5a3c33; --c-afternoon: #2d4f44; --c-evening: #3d3a63; --c-other: #353d52;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 16px/1.6 ui-rounded, "SF Pro Rounded", "Nunito", "Avenir Next", system-ui, sans-serif;
  }
  main { max-width: 600px; margin: 0 auto; padding: 64px 22px 90px; }
  h1 { font-size: clamp(1.8rem, 6vw, 2.4rem); line-height: 1.15; margin: 0 0 8px; font-weight: 700; }
  .sub { color: var(--muted); margin: 0 0 36px; }

  .clay {
    background: var(--surface); border-radius: 32px; padding: 28px;
    box-shadow:
      14px 14px 30px var(--lo),
      -12px -12px 26px var(--hi),
      inset 3px 3px 6px var(--hi),
      inset -4px -4px 8px var(--lo);
  }
  form { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  label { display: grid; gap: 8px; color: var(--muted); font-size: .9rem; padding-left: 6px; }
  .full { grid-column: 1 / -1; }
  input {
    font: inherit; font-size: 1rem; color: var(--ink); width: 100%;
    background: var(--bg); border: 0; border-radius: 20px; padding: 14px 18px;
    box-shadow: inset 5px 5px 10px var(--lo), inset -5px -5px 10px var(--hi);
  }
  input::placeholder { color: var(--muted); opacity: .6; }
  input:focus-visible { outline: 3px solid var(--coral); outline-offset: 2px; }
  button {
    grid-column: 1 / -1; margin-top: 6px;
    font: inherit; font-weight: 700; font-size: 1.05rem; cursor: pointer;
    color: var(--coral-ink); background: var(--coral); border: 0;
    border-radius: 24px; padding: 16px;
    box-shadow:
      8px 8px 18px var(--lo), -6px -6px 14px var(--hi),
      inset 3px 3px 6px rgba(255,255,255,.45), inset -4px -4px 8px rgba(160,80,50,.25);
    transition: box-shadow .15s ease, transform .15s ease;
  }
  button:active:not([disabled]) {
    transform: translateY(1px);
    box-shadow: inset 4px 4px 10px rgba(160,80,50,.35), inset -3px -3px 8px rgba(255,255,255,.3);
  }
  button:focus-visible { outline: 3px solid var(--ink); outline-offset: 3px; }
  button[disabled] { opacity: .7; cursor: progress; }
  .error { margin-top: 26px; color: var(--over); text-align: center; }

  .plan { margin-top: 60px; }
  .plan h2 { font-size: 1.5rem; margin: 0 0 18px; font-weight: 700; }
  .spend { margin: 0 0 14px; }
  .track {
    height: 18px; border-radius: 12px; background: var(--bg); padding: 3px;
    box-shadow: inset 3px 3px 6px var(--lo), inset -3px -3px 6px var(--hi);
  }
  .track span {
    display: block; height: 100%; border-radius: 10px; background: var(--mint);
    box-shadow: inset 2px 2px 3px rgba(255,255,255,.5);
  }
  .track.over span { background: var(--over); }
  .warn { color: var(--over); margin: 12px 0 0; }
  .aside { color: var(--muted); font-size: .9rem; margin: 10px 0 0; }

  .day { margin-top: 28px; padding: 22px 24px; }
  .day h3 { display: flex; justify-content: space-between; margin: 0 0 12px; font-size: 1.1rem; }
  .day h3 span { color: var(--muted); font-weight: 500; }
  .stops { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
  .stops li { display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; }
  .chip {
    min-width: 6.2rem; text-align: center; padding: 6px 12px; border-radius: 14px;
    font-size: .85rem; font-weight: 600; background: var(--c-other); color: var(--ink);
    box-shadow: 3px 3px 6px var(--lo), -2px -2px 5px var(--hi);
  }
  .chip.morning { background: var(--c-morning); }
  .chip.afternoon { background: var(--c-afternoon); }
  .chip.evening { background: var(--c-evening); }
  .cost { color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
  pre { white-space: pre-wrap; font: inherit; margin: 28px 0 0; padding: 22px 24px; }
  .note { color: var(--muted); font-size: .88rem; margin-top: 36px; text-align: center; }
  @media (max-width: 520px) {
    form { grid-template-columns: 1fr; }
    .clay { padding: 22px; border-radius: 28px; }
    .stops li { grid-template-columns: 1fr auto; }
    .chip { grid-column: 1 / -1; justify-self: start; }
  }
</style>
</head>
<body>
<main>
  <h1>Where to next?</h1>
  <p class="sub">Tell us a few things and get a day-by-day plan.</p>

  <form method="post" id="f" class="clay">
    <label class="full">Destination
      <input name="destination" value="{{ v.destination }}" placeholder="Goa" required>
    </label>
    <label>Days
      <input name="days" type="number" min="1" max="14" value="{{ v.days }}" required>
    </label>
    <label>Budget in rupees
      <input name="budget" type="number" min="1" value="{{ v.budget }}" required>
    </label>
    <label class="full">What you enjoy
      <input name="interest" value="{{ v.interest }}" placeholder="beaches, street food" required>
    </label>
    <button id="b">Plan my trip</button>
  </form>

  {% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}

  {% if result %}
  <section class="plan">
    <h2>Your {{ v.days }} days in {{ v.destination }}</h2>
    <p class="spend">About <strong>Rs {{ py_sum }}</strong> of your Rs {{ budget }}.</p>
    <div class="track {{ 'over' if over else '' }}"><span style="width: {{ pct }}%"></span></div>
    {% if over %}
      <p class="warn">That's Rs {{ py_sum - budget }} over your budget. Try again, or raise it a little.</p>
    {% endif %}
    {% if model_total is not none and model_total != py_sum %}
      <p class="aside">The AI wrote its own total as Rs {{ model_total }}, but the items add up to Rs {{ py_sum }}. We went with the items.</p>
    {% endif %}

    {% if days_data %}
      {% for d in days_data %}
        <section class="day clay">
          <h3>Day {{ d.n }} <span>Rs {{ d.total }}</span></h3>
          <ul class="stops">
            {% for it in d['items'] %}
              <li>
                <span class="chip {{ it.label|lower|replace(' ', '-') }}">{{ it.label }}</span>
                <span>{{ it.desc }}</span>
                <span class="cost">Rs {{ it.cost }}</span>
              </li>
            {% endfor %}
          </ul>
        </section>
      {% endfor %}
    {% else %}
      <pre class="clay">{{ result }}</pre>
    {% endif %}
    <p class="note">Prices are rough guesses. Check them before you book.</p>
  </section>
  {% endif %}
</main>
<script>
  document.getElementById('f').addEventListener('submit', function () {
    var b = document.getElementById('b');
    b.textContent = 'Putting your days together...';
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
            ctx = dict(error="We can't reach the AI on this computer. Start it with: sudo systemctl start ollama")
        except Exception as e:
            ctx = dict(error=f"Something went wrong: {e}. Try again.")
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
