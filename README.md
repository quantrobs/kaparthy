# SealedKeep

**Only real improvements survive.**

SealedKeep runs an experiment loop for code and research work.

An agent (or a simple script) changes something. A fixed command measures the result. If the number got better, the change stays. If it did not, the change is thrown away and the files go back to the last good version.

That is the whole product. Everything else exists to keep that rule honest.

## What matters

**The score has to come from a real run.**  
SealedKeep reads the number from the evaluation command’s output. An agent cannot type in a better score and keep the change. Printing a fake number in the middle of the output does not work either. The last real match wins.

**The test itself is off limits.**  
The agent can edit the experiment. It cannot edit the evaluation, the holdout data, or other protected files. If it tries, the trial is rejected before it is saved.

**A keep is not one lucky run.**  
A change that looks good on a single seed is not enough when the keep-gate is on. The keep has to hold up. That is what “sealed” means.

**History is not deleted.**  
Every try is a Git commit. The ones that failed stay in the record. You can see what was tried, what won, and what was reverted. The current best is always a commit you can check out.

**The working copy stays runnable.**  
A crash or a reject rolls back to the last kept version. You do not come back to a half-broken tree.

**The model does not get to set the rules.**  
The goal, the metric, the time and token limits, and the keep/revert policy live in a control file. Not in the prompt. Not in the agent’s memory.

**Knowledge is optional and off by default.**  
There is a graph for claims and sources if you want it. Agents cannot write to it unless you turn that on. Work history and “what we believe” are not the same pile.

If you remember one sentence: **progress is only real when the evaluation command says so, and that decision is recorded.**

## Try it

Python 3.11 or newer. No language model required for the demo.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
export AGENTIC_DATA=./data         # Windows: $env:AGENTIC_DATA = ".\data"

ah demo bootstrap
ah demo athlete --loop <loop_id> --max-trials 8
ah demo hostile --loop <loop_id>
ah demo show --loop <loop_id>
```

`bootstrap` sets up a tiny trainer: change `train.py`, never touch `prepare.py`, try to lower `val_loss`.

`athlete` is a simple searcher, not an LLM. It proposes hyperparameter changes and lives or dies by the metric.

`hostile` tries to fake a better score. That attempt must fail. The best result must not change.

Useful commands after that:

```bash
ah leaves                          # current frontier
ah board                           # notes on the trials
ah context --budget-tokens 2000    # what an agent is allowed to see
ah agent-run --loop <loop_id> --max-trials 8
```

API server: `export AGENTIC_DATA=./data` then `agentic-api`.  
Health: `GET /health`. Ready: `GET /ready`.

Local only: `X-Agent-Key: architect-dev-key`. Do not use that key on a shared machine.

## Run it for real

Turn on auth. Rotate the admin token. Keep secrets out of control files.

```bash
export AGENTIC_REQUIRE_AUTH=1
export AGENTIC_ADMIN_TOKEN='<long-random>'
export AGENTIC_REJECT_UNKNOWN_KEYS=1
agentic-api
```

If a run crashes or the tree is dirty: `POST /loops/{id}/recover` puts you back on the last kept commit and re-runs the metric.

Details: [docs/runbook.md](docs/runbook.md).

## This is not

- A model trainer. Weights are not updated here.
- An LLM. Bring your own if you want one. The loop does not need one.
- A promise the score will improve. Some trials lose. That is the point.
- A chat log. If it is not in Git and the ledger, it did not happen.

## More detail

| Doc | When you need it |
| --- | --- |
| [docs/demo.md](docs/demo.md) | Walk through the demo out loud |
| [docs/runbook.md](docs/runbook.md) | Auth, sandbox, recovery |
| [docs/release-gates.md](docs/release-gates.md) | Tests that must stay green |
| [MASTER-PLAN.md](MASTER-PLAN.md) | Full design, rules, and roadmap |
| `contracts/` | API and JSON schemas |
