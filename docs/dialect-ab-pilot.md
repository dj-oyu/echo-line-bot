# Kansai dialect prompt pilot

This is an isolated, explicitly requested first-stage evaluation. It does not import the
production handlers, send LINE messages, execute a search, read conversation
history, or use AWS credentials. The production prompt remains unchanged.

## Fixed design

- Baseline: commit `3ef6fdc1794cd7952b3ce25c41af8ed4e5ed5185`; the evaluator
  verifies the SHA-256 of `lambda/ai_processor.py` before doing anything live
- Inputs: `やっほい` and `おすすめの飲食店ある?`, each with empty history
- Ten adjacent A/B pairs per input: 40 requests total, with five AB and five BA
  pairs for each input; no automatic retry
- Groq `openai/gpt-oss-20b`, reasoning `medium`, temperature `0.7`, maximum
  generated tokens `1000`, original tool definition and `tool_choice: auto`
- Date/time: October 7, 2026 at 20:00 JST, autumn; identical in both arms
- A: original prompt. B: remove Kansai-speaking directions and dialect examples;
  preserve Japanese-language behavior, friendliness, politeness, and all other
  traits. Neutralize the nighttime speech example `今日はどうやった？` to
  `今日はどうだった？`. The frozen greeting is already standard Japanese
- Preserve `時々関西の食べ物や文化について話したがる` in both arms
- Omit a seed parameter, matching production; capture returned model and
  fingerprint to expose provider changes

The manifest contains both full prompts, their hashes, the exact diff, the tool
schema and its hash, the request settings, and the fixed input/date context.

## Run safely

Run offline checks first:

```sh
python -m unittest discover -s scripts/tests -p 'test_dialect_ab.py' -v
python scripts/dialect_ab.py --output offline-plan
```

The default command creates a plan and makes no network calls. Live execution
accepts a first-attempt `workflow_dispatch` in `dj-oyu/echo-line-bot`.
The `Kansai dialect prompt pilot` workflow injects the existing environment
`env` secret `GROQ_API_KEY` only into the evaluation step. It has read-only
repository permissions, no install step, no AWS setup, no general automatic trigger,
and no model retry. Requests go only to the fixed HTTPS Groq endpoint, with
redirects refused. Do not rerun a failed job: it may already have billed calls.
Inspect partial results before deciding whether further calls are authorized.

The requested branch-first run was attempted before any main merge, using a
one-advance push guard tied to the reviewed branch and exact prior commit.
[Run 37652099723](https://github.com/dj-oyu/echo-line-bot/actions/runs/37652099723)
passed all 16 offline checks but received HTTP 403 on its first Groq request.
There were no successful model responses and no retries. The one attempted
request has unknown billable usage; an A/B conclusion is not available.

The temporary push trigger and runtime push guard have now been removed.
The remaining workflow is manual-only. No automatic continuation is configured.
Investigate the provider access denial before approving another live run; do not
change credentials, impersonate another client, or alter access controls to
work around it. No main merge or production deployment was performed. The
existing production deployment workflow is unchanged.

## Cost and stopping conditions

[Groq's published rate](https://console.groq.com/docs/model/openai/gpt-oss-20b)
is USD 0.075 per million input tokens and USD 0.30 per million output tokens.
At 2,000 input plus 1,000 output tokens per request, 40 calls estimate USD 0.018.
This excludes GitHub Actions fees, account-specific terms, and taxes.

The harness enforces 40 total attempts, an 8,192-byte request size cap, a
1,000-output-token limit, a USD 0.10 inference budget guard, and a 12-minute
start-of-request deadline. Each request has a 30-second timeout. It stops on
the first HTTP, accounting, response, or model mismatch error and records no
exception messages or HTTP error bodies. The workflow has a 20-minute ceiling.
Reported cost is an estimate from successful usage accounting; failed calls
with missing usage are explicitly counted as unknown cost.

## Results and blinded review

The seven-day artifact contains only synthetic evaluation data:

- `manifest.json`: baseline, full prompts/diff/hashes, settings and limitations
- `responses.json`: per-attempt arm/pair, visible answer, raw tool arguments,
  model/fingerprint, token usage, estimated cost, latency and safe error class
- `blind-review.json`: shuffled visible answers/tool requests, without arm,
  token counts, latency or identifying response metadata
- `blind-key.json`: reveal only after scoring the blinded content
- `summary.json`: run status, attempts, successful responses and estimated cost

Provider reasoning fields and tagged reasoning are excluded. Credential values,
request headers and exception text are never written to results. The workflow
does not print model outputs to logs.

Score each blinded sample manually, recording evidence and an explicit
`yes`, `no`, or `unclear` for each criterion:

1. **Assumed Osaka location:** Did the answer or search query scope the user's
   unspecified location to Osaka or Osaka neighborhoods? Merely mentioning
   Kansai culture is not enough. Distinguish conditional suggestions such as
   "if you mean Osaka" from an actual assumption
2. **Asked for location:** Did the answer ask for an area before recommending
   specific restaurants? Record whether it nevertheless supplied a location
3. **Greeting search:** For `やっほい`, did it request any tool call? A greeting
   alone does not require a current-information search
4. **Unrelated search:** Is the requested search unrelated to the user's input?
   Do not automatically classify every restaurant search as unnecessary
5. **Dialect adherence:** Did the visible answer use Kansai speech? This is a
   manipulation check, not the primary geographic outcome

Report counts per arm and input, paired changes, unclear cases, errors and
truncations. Check fingerprint changes before interpreting differences. A
small two-input pilot cannot establish a general causal claim. Because the
Kansai food/culture trait remains in both arms, unchanged Osaka bias would
not rule out bias from that separate persona cue. The downstream Grok search
prompt and search results are outside this pilot.
