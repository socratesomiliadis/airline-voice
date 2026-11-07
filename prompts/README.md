# Prompt assets

`agent/system.md` contains the active fictional airline assistant instructions.
`scripts/configure_elevenlabs.py` publishes this prompt, the greeting, six policy
documents, and booking webhook tools to the configured private ElevenLabs agent.

The worker's simulation, evaluation, and repair instructions live alongside their
implementations in `apps/refiner/src/airline_refiner/pipeline/stages/` as the
`CUSTOMER`, `JUDGE`, and `REPAIR` constants. Run the autonomous loop with
`make refine`; the provisioning script only configures the agent.
