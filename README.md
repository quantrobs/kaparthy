Only real improvements survive. We test every change against live markets, and we throw out the rest. You must measure each update closely, because models that look good on paper often fail under pressure. We don't keep theoretical gains; instead, we use our local LLM infrastructure to filter the noise and retain only the code that actually makes money.

SealedKeep operates a continuous experiment loop that integrates both code and research workflows. You can use this system to test hypotheses rapidly, refine your models, and apply empirical data directly to your projects. By automating the cycle, we ensure that technology development and research information don't diverge, allowing your team to iterate with confidence.

An agent or a simple script modifies the code, and a fixed command evaluates the result against a baseline. If the metric improves, the system permanently keeps the modification; otherwise, it discards the attempt and reverts the files to the last working version.

That constitutes the entire product. Every other component exists solely to enforce this rule.

**Acknowledgement**

I drew inspiration for this work from Karpathy's writings. You can find the bibliography at docs/bibliography.md.

What matters
The score has to come from a real run.
SealedKeep reads the number from the evaluation command’s output. An agent cannot type in a better score and keep the change. Printing a fake number in the middle of the output does not work either. The last real match wins.

The test itself remains off-limits. The agent can edit the experiment, but it cannot modify the evaluation, the holdout data, or other protected files. If the agent attempts to alter these files, the system rejects the trial before saving it.

A successful keep does not rely on a single lucky run, nor does a change that looks good on one seed suffice when you enable the keep-gate. The keep has to hold up. That's what we mean by a "sealed" state.

History is not deleted, since every attempt is a Git commit and the iterations that failed stay in the record. You can see exactly what was tried, what won, and what was reverted. The current best version is always a commit you can check out.

The working copy remains runnable. If the system crashes or rejects an update, it rolls back to the last kept version, so you do not return to a half-broken tree.

The model does not get to set the rules. You define the goal, the metric, the time and token limits, and the keep/revert policy in a control file, rather than in the prompt or the agent's memory.

Knowledge remains optional and is disabled by default. If you require a graph for claims and sources, you can enable this feature, but agents cannot write to the graph unless you explicitly activate the setting. You must separate work history from what we believe, as these elements represent distinct data structures rather than a single repository.

If you remember only one sentence, make it this: progress is only real when the evaluation command confirms it, and you record that decision. You can't rely on intuition when you train local models; you must run the evaluation scripts, assess the metrics, and log the outcomes. Only when you save these results to your version control system does the work become a verifiable milestone.


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
