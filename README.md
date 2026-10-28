# Trip Planner

Tell it where you're going, for how many days, how much you can spend and what you enjoy. It gives you a day-by-day plan with a rough cost for everything.

It runs on your own computer. No account, no API key, nothing sent to the internet.

## How it works

1. You fill in the form (or answer the questions in the terminal).
2. The app sends your answers to **Gemma 4**, an open-weight model from Google, running locally through [Ollama](https://ollama.com).
3. Gemma writes the itinerary: morning, afternoon and evening for each day, plus a place to stay and local transport.
4. **Python adds up the costs itself**, because small language models are not reliable at maths. If the plan goes over your budget, the page tells you by how much. If the model's own total doesn't match the items, the page uses the items.

## What you need

- Python 3.10 or newer
- [Ollama](https://ollama.com), with the Gemma 4 model pulled
- A computer that can run a small model. It was built on a laptop with 23 GB of RAM and a 6 GB GPU, and a plan takes about 20 seconds.

## Setup

```bash
# 1. Get the code
git clone <your-repo-url>
cd <your-repo-folder>

# 2. Python environment
python -m venv .venv
source .venv/bin/activate
pip install flask requests

# 3. Start Ollama and download the model (one time, a few GB)
sudo systemctl start ollama      # on Arch; on other systems, just open Ollama
ollama pull gemma4:e4b
```

On Arch Linux, install Ollama with `sudo pacman -S ollama ollama-cuda` (the second package is for NVIDIA GPUs).

## Run it

Web page:

```bash
python app.py
```

Then open http://127.0.0.1:5000

Terminal only:

```bash
python app.py --cli
```

The first plan after starting Ollama is slower, because the model has to load into memory.

## Good to know

- **Prices are estimates.** A small model makes educated guesses and sometimes invents place names. Check anything important before you book.
- It only works while Ollama is running on the same computer.
- If your computer struggles, try the smaller model: change `MODEL` at the top of `app.py` to `gemma4:e2b`.

## Built with

- [Gemma 4](https://ai.google.dev/gemma), run locally with Ollama
- [Flask](https://flask.palletsprojects.com) for the web page

## License

MIT. See the `LICENSE` file.
