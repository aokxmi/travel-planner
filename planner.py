import requests, time, re

destination = "goa"
days = 3
budget = 15000
interest = "beaches,sea food,party"

prompt = f"""You are my travel planner.
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

Output only the itinerary."""

r = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "gemma4:e4b",
            "prompt": prompt,
            "stream": False
            }
        )

text = r.json()["response"]
print(text)

costs = re.findall(r"Rs\s*(/d+)", text)
print(costs)

numbers = [int(c) for c in costs]
print(sum(numbers))

