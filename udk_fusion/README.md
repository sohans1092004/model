# Phase 5: multimodal fusion / decision engine (`udk_fusion/`)

This package is isolated. It is not imported by `api.py`, `udk_context` or `udk_signals`. The tests check this.

```
Phase 3  udk_context.decision.decide(UdkEvidence, ContextWindow, ...)  -> FinalDecision
             | inputs.from_phase3(UdkEvidence, FinalDecision)  (validated; ContractError on violation)
             v
Phase 5  engine.decide(FusionInput(linguistic, Phase 4 Evidence..., span), FusionPolicy) -> FusedDecision
             ^
Phase 4  udk_signals Evidence: acoustic_distress / overlap / speaker_attribution / target_speaker / condition
```

## Decision states

There are three states: `NO_ALERT`, `TRIGGER_VERIFY` and `TRIGGER_ALL`. `production_decision` maps them back to the live `NO_ACTION` / `TRIGGER_VERIFY` / `TRIGGER_ALL`.

There is **no DEFER tier**. Neither the live system nor Phases 3–4 has one, and TRIGGER_VERIFY already means "ask the user". Incomplete evidence is reported as `evidence_status: partial` plus the `ignored` list, so it is visible without a fourth tier that could absorb alerts.

Each result records:
- `basis`: none, linguistic, acoustic or fused
- `rules_fired`
- `contributing`: evidence that decided the result
- `considered`: informative evidence that had no effect, with the reason
- `ignored`: evidence that was uncertain, unavailable, outside the utterance span, or from a source the policy doesn't name, with the reason
- `annotations`
- `policy_sha256`

`record()` returns a JSON-serialisable version of all of this.

## Precedence (highest first)

| # | Evidence | Can raise | Can lower | Rule |
|---|---|---|---|---|
| 1 | Personal/custom UDK, KWS UDK | as the UDK path decided | never (Phase 3 H1; invariant I4) | R2 |
| 2 | Standard UDK | as the UDK path decided | only through the Phase 3 sentence veto (live) or context veto, and the context veto only with positive Phase 4 support (R3) | R2–R4 |
| 3 | Contextual intent (Phase 3) | VERIFY→ALL on a UDK (Phase 3 context escalation, off in production-equivalent) | through the Phase 3 context veto only, subject to R3 | R2, R3 |
| 4 | Danger without a UDK (classifier only) | TRIGGER_VERIFY at most (H6; I3) | – | R2 |
| 5 | Acoustic distress (S-4 boundary) | corroboration: UDK-path VERIFY→ALL (R5); acoustic alone: NO_ALERT→VERIFY (R6), never ALL (I1) | never | R5, R6 |
| 6 | Speaker attribution, target speaker | – | never. It can only let a context veto stand when POSITIVE (R3). "Not the enrolled user" never lowers anything. | R3, R7 |
| 7 | Overlap | – | never. Only a clean NEGATIVE lets a veto stand; POSITIVE or UNCERTAIN with no alert is annotated "UDK may be masked". | R3, R4, R7 |
| 8 | Degraded audio (condition POSITIVE) | – | – (other NEGATIVE evidence becomes UNCERTAIN, G5) | R1 |
| 9 | UNCERTAIN / UNAVAILABLE / missing | – | – (listed in `ignored`; never read as NEGATIVE) | R1 |

Rules R0–R8 and invariants I1–I4 are specified in `engine.py`.

## Policy

Policy is `configs/*.json` in the `udk_fusion.config/1` format, with no defaults.
- The loader rejects any `allow_*` override of the invariants.
- `s4_status` must stay `"open"`.
- `production_equivalent.json` mirrors live 96ea038, which is S-4 option C as deployed. This is not an endorsement.
- `s4_acoustic_policy(base, "A".."D")` builds each S-4 option so they can be evaluated side by side on real data later. It does not choose one.

## Tests

`python udk_fusion/test_fusion.py`: the input contract, the policy loader, named scenarios, and an exhaustive grid of 230,400 decisions checked for the invariants.
