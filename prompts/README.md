# Prompt assets

`agent/system.md` contains the active fictional airline assistant instructions.
`scripts/configure_elevenlabs.py` publishes this prompt, the greeting, six policy
documents, and booking webhook tools to the configured private ElevenLabs agent.

Simulation, evaluation, and refinement prompts remain future work. The setup CLI
does not run the autonomous refinement loop.
