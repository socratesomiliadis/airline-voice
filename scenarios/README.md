# Simulation scenarios

`airline.json` is the executable fictional customer suite for the autonomous
refiner. Each scenario supplies a unique ID, goal, customer facts, expected
outcome, required tool names, and optional fresh prerequisite booking.

Run from the repository root:

```sh
uv run --package airline-refiner airline-refiner run
```

See [the refinement guide](../docs/refinement.md) for configuration, fixtures,
scoring, repairs and saved run evidence. Do not add real customer data.
