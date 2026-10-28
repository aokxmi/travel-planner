import re
import textwrap
import requests
from flask import Flask, request, render_template_string

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e4b"


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


def to_number(s):
    return int(s.replace(",", ""))


def check_budget(text):
    """Return (python_sum, model_total) -- model_total is None if missing."""
    body, _, total_line = text.partition("Total:")
    items = re.findall(r"Rs\s*([\d,]+)", body)
    python_sum = sum(to_number(x) for x in items)
    claimed = re.findall(r"Rs\s*([\d,]+)", total_line)
    model_total = to_number(claimed[0]) if claimed else None
    return python_sum, model_total


app = Flask(__name__)

PAGE = """
<!doctype html>
<title>AI Travel Planner</title>
<h1>AI Travel Planner</h1>
<form method="post" onsubmit="document.getElementById('b').innerText='Planning... (about 20s)'">
  <input name="destination" placeholder="Destination" required><br>
  <input name="days" type="number" min="1" placeholder="Days" required><br>
  <input name="budget" type="number" min="1" placeholder="Budget (Rs)" required><br>
  <input name="interest" placeholder="Interests" required><br>
  <button id="b">Plan my trip</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if result %}
  <pre style="white-space: pre-wrap">{{ result }}</pre>
  <p><b>Budget check (Python):</b> items add up to Rs {{ py_sum }}
  {% if model_total %}| model said Rs {{ model_total }}{% endif %}
  | your budget: Rs {{ budget }}</p>
  <small>Prices are AI estimates. Verify before booking.</small>
{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():
    ctx = {}
    if request.method == "POST":
        try:
            budget = int(request.form["budget"])
            text = plan_trip(
                request.form["destination"],
                int(request.form["days"]),
                budget,
                request.form["interest"],
            )
            py_sum, model_total = check_budget(text)
            ctx = dict(result=text, py_sum=py_sum,
                       model_total=model_total, budget=budget)
        except requests.exceptions.ConnectionError:
            ctx = dict(error="Can't reach Ollama. Run: sudo systemctl start ollama")
        except Exception as e:
            ctx = dict(error=f"Something went wrong: {e}")
    return render_template_string(PAGE, **ctx)


if __name__ == "__main__":
    import sys
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
