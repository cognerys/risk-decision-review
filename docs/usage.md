# Using the review graph

## Command line

```bash
risk-desk run --card credit_missing --arm challenged
```

`--arm` is one of `single`, `specialists`, `challenged` (the default) or `self_review`. They make one, three, five and five model calls for each review. The command prints the final recommendation as JSON.

Runs use a scripted offline model unless `RISK_DESK_LIVE=1` (or `true`) is set, which turns on the configured live model and paid API calls.

The scripted model's reply deliberately fails the proposal checks, so an offline run falls back to the deterministic scorecard and prints a note saying so. A sensible-looking recommendation is therefore not evidence that a model produced it: look at the verification record. Each model stage and the verification are appended to `runs/mirror.jsonl`.

Other commands:

```bash
risk-desk scorecard ordinary_inside   # the deterministic reference for one card, no model
risk-desk show-config                 # model id and live flag; never prints a key
risk-desk view                        # local page at http://127.0.0.1:8765
risk-desk probe                       # one live call to check the credential
```

## Graph viewer

`risk-desk view` serves a local page that draws each configuration and lights its steps as a card runs through it. The model stays off unless you tick the box.

## LangGraph Studio

```bash
pip install -e ".[studio]"
langgraph dev
```

`langgraph.json` exposes the `challenged` configuration as `review`. Studio supplies checkpointing and loads `.env`, so check `RISK_DESK_LIVE` before running. Example input:

```json
{"card_id": "credit_missing"}
```

Use a fresh thread for each independent review.

## Running the study

The command line and Studio run the sixteen standard cards, whose evidence includes each action's utility. The study is different: it uses four composed cases and withholds the utility figures, so a model has to calculate them from the supplied components. Use the runner for that.

```bash
python experiments/run_study.py                      # offline, scripted model, no cost
python experiments/run_study.py --live --experiment MY-RUN --output-dir experiments/results/my-run
python experiments/analyse_study.py experiments/results/my-run --output-dir experiments/results/my-run/analysis
```

A live run needs `OPENAI_API_KEY` in the environment and makes at most 56 calls (it stops at 60). The runner refuses to write into an existing directory, copies the source and protocol into the run, and keeps every request, response, intermediate proposal and check. Read `experiments/protocol.md` first. Model output is not deterministic, so a repeat will not reproduce another run call for call.
