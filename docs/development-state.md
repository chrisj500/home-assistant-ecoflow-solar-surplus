# Development state — 0.1.12

## Problem and evidence
Installed 0.1.11 recorded command mask 0 while panel grid minus home power measured 1,102 W at night with zero solar. All 50 retained grid decisions held the command. No actual switch states or original failed shutdown were retained. The initiating device/service failure is unknown.

## Change
Central safety enforcement precedes every control-mode trigger when solar conditions are unsafe, including sunset and reassert. Off requests are verified against live force-charge switches and fresh physical panel power (200 W tolerance). Maximum three requests at least 30 seconds apart per shutdown episode. Pending/unconfirmed state is independent of saved desired command. A later confirmed shutdown followed by recurrence gets a new retry budget. Safe grid decisions requesting charging reset the prior episode. Observe mode performs no writes. No reserve, charge limit or AC channel policy changes.

Diagnostics include actual switch states and shutdown status/attempt count. Observability retains 50 shutdown-state transitions separately from the 50 grid decisions and persists them through reloads. Retry counters are session scoped, so reload starts a new bounded budget.

## Validation and next steps
Run `python -m unittest discover -s tests -v` and required GitHub validations. Controller regression tests execute extracted actual methods with fake HA telemetry/services; they do not simulate the EcoFlow transport. After merge/release and installation, confirm off switches plus physical charging below tolerance. An unconfirmed error requires inspecting actual EcoFlow state and transport logs; never treat service completion as hardware acknowledgement.

## Release pipeline
Main pushes publish the manifest version with an installable integration ZIP after regression, Hassfest and HACS checks pass. Existing releases are skipped. The release tag targets the validated main commit.
