This repo is modified from [RDI-Foundation/agentbeats-tutorial] (https://github.com/RDI-Foundation/agentbeats-tutorial.git).
It extends [tau2-bench](https://github.com/sierra-research/tau2-bench) benchmark evaluation to include assessment if all the (white) agent violates any specified rules.
- Reward point is 1.0 if the agent interaction is successful as defined in the original tau-bench with no rule violation.
- Reward point is 0.0 if the agent interaction is not successful
- Reward point is 0.5 if the agent interaction is successful but there are violation

## Quickstart
1. Clone the repo
```
git clone git@github.com:rdi-foundation/agentbeats-tutorial.git
cd agentbeats-tutorial
```
2. Install dependencies
```
uv sync
```
3. Set environment variables
```
cp sample.env .env
```
Add your Google API key to the .env file

4. Clone the tau-bench2 repository
```
cd ./scenarios/tau2
git clone --depth 1 https://github.com/sierra-research/tau2-bench.git
```
For more information, see ./scenarios/tau2/README.md
```

5. Run the [tau2 example](#example)
```
uv run agentbeats-run scenarios/tau2/scenario.toml
```
This command will:
- Start the agent servers using the commands specified in scenario.toml
- Construct an `assessment_request` message containing the participant's role-endpoint mapping and the assessment config
- Send the `assessment_request` to the green agent and print streamed responses

**Note:** Use `--show-logs` to see agent outputs during the assessment, and `--serve-only` to start agents without running the assessment.

To run this example manually, start the agent servers in separate terminals, and then in another terminal run the A2A client on the scenario.toml file to initiate the assessment.

After running, you should see an output similar to this.

![Sample output](assets/sample_output.png)

## Project Structure
```
src/
└─ agentbeats/
   ├─ green_executor.py        # base A2A green agent executor
   ├─ models.py                # pydantic models for green agent IO
   ├─ client.py                # A2A messaging helpers
   ├─ client_cli.py            # CLI client to start assessment
   └─ run_scenario.py          # run agents and start assessment

scenarios/
└─ tau2/                       # implementation of the tau2 example
   ├─ tau2_evaluator.py        # green agent impl using the official A2A SDK
   ├─ tau2_check_rules.py      # check agent communication conforming to rules
   ├─ tau2_agent.py            # white agent (Google ADK)
   └─ scenario.toml            # config for the tau2 example
   └─ tau2-bench               # git clone --depth 1 https://github.com/sierra-research/tau2-bench.git
      └─ ...
```
