# CXAS SCRAPI Guide

## What is CXAS SCRAPI?

**CXAS SCRAPI** (CX Agent Studio Scripting API) is a high-level Python library that extends the official Google Python Client for CX Agent Studio. It provides a more pythonic and developer-friendly interface for programmatically interacting with CX Agent Studio.

SCRAPI allows you to automate tasks that would otherwise require manual work in the CX Agent Studio console, making it ideal for:
- Automated testing and CI/CD pipelines
- Bulk operations across multiple agents
- Performance monitoring and analytics
- Programmatic agent configuration

## Installation

SCRAPI is currently in preview and not published to PyPI. You must download and install it directly from Google Cloud Storage.

### Prerequisites

- Python 3.9+
- Google Cloud authentication
- Access to CX Agent Studio

### Installation Steps

```python
# Step 1: Authenticate to Google Cloud
from google.colab import auth
auth.authenticate_user()

# Step 2: Download and install the base CES SDK
!wget https://storage.googleapis.com/gassets-api-ai/ces-client-libraries/v1beta/ces-v1beta-py.tar
!pip install ces-v1beta-py.tar --quiet

# Step 3: Download and install CXAS SCRAPI
!gsutil cp gs://gassets-api-ai/cxas-scrapi-external-preview/cxas_scrapi-0.1.2-py3-none-any.whl .
!pip install cxas_scrapi-0.1.2-py3-none-any.whl --quiet
```

### Dependencies

SCRAPI requires several dependencies that may need manual installation:

```bash
pip install pyyaml pandas pandas-gbq sentence-transformers jsonpath-ng
```

## Core Concepts

### App ID Format

All SCRAPI operations require an App ID in the following format:
```
projects/{PROJECT_ID}/locations/{LOCATION}/apps/{APP_UUID}
```

Example:
```
projects/my-gcp-project/locations/us/apps/7a5d79ec-16e8-4dbd-81a4-7ad0d16772ce
```

### Main Classes

| Class | Purpose |
|-------|---------|
| `Apps` | Manage CX Agent Studio applications |
| `Agents` | CRUD operations on agents within an app |
| `Tools` | Manage tools (OpenAPI, Python, DataStore, etc.) |
| `Sessions` | Run conversational tests |
| `Evaluations` | Manage and run evaluations |
| `EvalUtils` | Utilities for eval analysis and reporting |
| `ConversationHistory` | Access and analyze conversation logs |

## Usage Examples

### Basic Setup

```python
from cxas_scrapi import Apps, Agents, Tools

APP_ID = "projects/my-project/locations/us/apps/my-app-uuid"
PROJECT_ID = "my-project"
LOCATION = "us"
```

### Get App Information

```python
app_client = Apps(project_id=PROJECT_ID, location=LOCATION)
app = app_client.get_app(APP_ID)

print(f"App Name: {app.display_name}")
print(f"Model: {app.model_settings.model}")
print(f"Root Agent: {app.root_agent}")
print(f"Variables: {len(app.variable_declarations)}")
```

### List and Inspect Agents

```python
agent_client = Agents(APP_ID)

# List all agents
all_agents = agent_client.list_agents(APP_ID)
print(f"Total agents: {len(all_agents)}")

# Get root agent details
root_agent = agent_client.get_agent(app.root_agent)
print(f"Root Agent: {root_agent.display_name}")
print(f"Tools assigned: {len(root_agent.tools)}")
```

### Work with Tools

```python
tools_client = Tools(APP_ID)

# Get a map of tool names to IDs (useful for lookups)
tools_map = tools_client.get_tools_map(APP_ID, reverse=True)
print(f"Total tools: {len(tools_map)}")

# Get a specific tool
tool = tools_client.get_tool(tools_map["my_tool_name"])
print(f"Tool: {tool.display_name}")

# Execute a tool with arguments
args = {"query": "test input"}
result = tools_client.execute_tool(APP_ID, "my_tool_name", args=args, variables=None)
print(result)
```

### Conversational Testing with Sessions

```python
from cxas_scrapi import Sessions

session_client = Sessions(APP_ID)

# Create a new session
session_id = session_client.create_session_id()

# Send messages and get responses
inputs = ["Hello!", "I need help with my order"]

for user_input in inputs:
    response = session_client.run(session_id, user_input)
    session_client.parse_result(response)  # Pretty prints the response
```

### Running Evaluations

```python
from cxas_scrapi import Evaluations, EvalUtils

eval_client = Evaluations(APP_ID)
eval_utils = EvalUtils(APP_ID)

# Get evaluation thresholds
eval_client.get_evaluation_thresholds(print_console=True)

# Get map of evaluations
evals_map = eval_client.get_evaluations_map(reverse=True)
print(list(evals_map["goldens"].keys())[:5])  # First 5 golden evals

# Run specific evaluations
evals_to_run = ["My Test Eval"]
eval_op = eval_utils.run_evaluation(evaluations=evals_to_run, app_id=APP_ID)
eval_response = eval_op.result()

# Get results
results = eval_client.list_evaluation_results_by_run(eval_response.evaluation_run)
```

### Eval Results to DataFrames

```python
# Convert eval results to pandas DataFrames
dfs = eval_utils.evals_to_dataframe(results)

# Three DataFrames are returned:
# - summary: Overall pass/fail status
# - failures: Detailed failure information
# - trace: Full turn-by-turn conversation trace

print(dfs["summary"])
print(dfs["failures"])
print(dfs["trace"])
```

### Search and Filter Evaluations

```python
# Search evals by tool usage
evals_with_tool = eval_client.search_evaluations(APP_ID, tools=["my_tool"])

# Search by variable usage
evals_with_var = eval_client.search_evaluations(APP_ID, variables=["products"])

# Search by agent
evals_with_agent = eval_client.search_evaluations(APP_ID, agents=["Support Agent"])
```

### Latency Metrics

```python
# Get latency metrics from evaluations
df = eval_utils.get_latency_metrics_dfs(eval_names=["My Test Eval"])

print(df["eval_summary"])    # Overall latency stats
print(df["tool_summary"])    # Per-tool latency (p50, p90, p99)
print(df["callback_summary"]) # Callback latencies
print(df["guardrail_summary"]) # Guardrail latencies
```

```python
from cxas_scrapi import ConversationHistory

# Get latency from live conversation history
ch_client = ConversationHistory(APP_ID)
df = ch_client.get_latency_metrics_dfs(
    APP_ID,
    time_filter="7d",      # Last 7 days
    source_filter="LIVE",  # LIVE, SIMULATOR, or EVAL
    limit=300
)
```

### Tool Unit Testing

SCRAPI supports automated tool testing with YAML-defined test cases:

```python
from cxas_scrapi import EvalUtils

eval_utils = EvalUtils(APP_ID)

# Define test cases in YAML
yaml_tests = """
tests:
  - name: test_search_products
    tool: search_products
    args:
      query: "birthday cake"
    variables:
      - products
      - catalog
    expectations:
      response:
        - path: "$.result"
          operator: "is_not_null"
        - path: "$.result"
          operator: "length_greater_than"
          value: 0

  - name: test_with_mock_data
    tool: search_products
    args:
      query: "balloons"
    variables:
      products:
        - title: "Mock Product"
          price: 10
    expectations:
      response:
        - path: "$.result[0].title"
          operator: "equals"
          value: "Mock Product"
"""

# Load and run tests
test_cases = eval_utils.load_tool_test_cases_from_yaml(yaml_tests)
results = eval_utils.run_tool_tests(test_cases, debug=False)
```

**Supported operators:**
- `equals`, `contains`
- `greater_than`, `less_than`
- `length_equals`, `length_greater_than`, `length_less_than`
- `is_null`, `is_not_null`

### Export Evaluations

```python
# Export eval to YAML
yaml_content = eval_client.export_evaluation(
    evals_map["goldens"]["My Eval"],
    output_format="yaml"
)
print(yaml_content)

# Also supports JSON format
json_content = eval_client.export_evaluation(
    evals_map["goldens"]["My Eval"],
    output_format="json"
)
```

## Common Pitfalls and Solutions

### 1. Authentication Issues

**Problem:** `google.auth.exceptions.DefaultCredentialsError`

**Solution:** Ensure you're authenticated before using SCRAPI:
```python
# In Google Colab
from google.colab import auth
auth.authenticate_user()

# Or set application default credentials
# gcloud auth application-default login
```

### 2. Missing Dependencies

**Problem:** `ModuleNotFoundError: No module named 'yaml'` (or pandas, sentence_transformers, etc.)

**Solution:** Install all required dependencies:
```bash
pip install pyyaml pandas pandas-gbq sentence-transformers jsonpath-ng
```

### 3. Incorrect App ID Format

**Problem:** `InvalidArgument` or `NotFound` errors

**Solution:** Use the full resource path:
```python
# ❌ Wrong
APP_ID = "7a5d79ec-16e8-4dbd-81a4-7ad0d16772ce"

# ✅ Correct
APP_ID = "projects/my-project/locations/us/apps/7a5d79ec-16e8-4dbd-81a4-7ad0d16772ce"
```

### 4. Regional Endpoint Issues

**Problem:** `404 Not Found` when calling APIs

**Solution:** SCRAPI uses regional endpoints. Ensure your location matches your app:
```python
# App in 'us' region
APP_ID = "projects/my-project/locations/us/apps/..."

# App in 'eu' region
APP_ID = "projects/my-project/locations/eu/apps/..."
```

### 5. Search Index Build Time

**Problem:** First search operation is slow

**Solution:** This is expected. SCRAPI builds a search index on the first query:
```python
# First search takes 5-10 seconds (building index)
results = eval_client.search_evaluations(APP_ID, tools=["my_tool"])

# Subsequent searches are instant (cached index)
results = eval_client.search_evaluations(APP_ID, tools=["other_tool"])
```

### 6. Tool Execution with Variables

**Problem:** Tool execution fails or returns unexpected results

**Solution:** Understand the three variable modes:
```python
# Mode 1: Use all app variables (default)
result = tools_client.execute_tool(APP_ID, "tool_name", args=args, variables=None)

# Mode 2: Use specific app variables (looked up automatically)
result = tools_client.execute_tool(APP_ID, "tool_name", args=args, variables=["var1", "var2"])

# Mode 3: Override with custom values
result = tools_client.execute_tool(APP_ID, "tool_name", args=args, variables={
    "var1": "custom_value",
    "var2": 123
})
```

### 7. Session State Not Persisting

**Problem:** Conversation context is lost between turns

**Solution:** Reuse the same session ID:
```python
# ❌ Wrong - creates new session each time
response1 = session_client.run(session_client.create_session_id(), "Hello")
response2 = session_client.run(session_client.create_session_id(), "What's my name?")

# ✅ Correct - maintains conversation context
session_id = session_client.create_session_id()
response1 = session_client.run(session_id, "My name is John")
response2 = session_client.run(session_id, "What's my name?")  # Agent remembers "John"
```

### 8. Evaluation Results Empty

**Problem:** `list_evaluation_results` returns empty

**Solution:** Ensure you're querying the correct evaluation and it has been run:
```python
# Check if eval exists
evals_map = eval_client.get_evaluations_map(reverse=True)
if "My Eval" not in evals_map["goldens"]:
    print("Evaluation not found!")

# Run the eval first
eval_op = eval_utils.run_evaluation(evaluations=["My Eval"], app_id=APP_ID)
eval_op.result()  # Wait for completion

# Then get results
results = eval_client.list_evaluation_results("My Eval")
```

### 9. Rate Limiting

**Problem:** `ResourceExhausted` errors

**Solution:** Add delays between bulk operations:
```python
import time

for eval_name in eval_names:
    results = eval_client.list_evaluation_results(eval_name)
    time.sleep(0.5)  # Brief delay to avoid rate limits
```

### 10. Large Response Handling

**Problem:** Memory issues with large conversation histories

**Solution:** Use pagination and limits:
```python
# Limit the number of conversations fetched
df = ch_client.get_latency_metrics_dfs(
    APP_ID,
    time_filter="1d",  # Shorter time window
    limit=50           # Fewer conversations
)
```

## Best Practices

1. **Use Maps for Lookups**: The `get_*_map()` methods provide O(1) lookups by display name:
   ```python
   tools_map = tools_client.get_tools_map(APP_ID, reverse=True)
   tool_id = tools_map["my_tool"]  # Instant lookup
   ```

2. **Parse Results for Debugging**: Use `parse_result()` for readable output:
   ```python
   response = session_client.run(session_id, "Hello")
   session_client.parse_result(response)  # Pretty printed HTML/text
   ```

3. **Export Before Modifying**: Always export evaluations before making changes:
   ```python
   backup = eval_client.export_evaluation(eval_id, output_format="yaml")
   ```

4. **Use DataFrames for Analysis**: Convert results to pandas for easier analysis:
   ```python
   dfs = eval_utils.evals_to_dataframe(results)
   failures = dfs["failures"]
   failures[failures["failure_type"] == "Tool Call"]
   ```

5. **Environment Separation**: Use different App IDs for dev/staging/prod:
   ```python
   import os
   APP_ID = os.environ.get("CX_APP_ID", "projects/.../apps/dev-app-id")
   ```

## Supported Tool Types

SCRAPI supports executing and testing the following tool types:

| Tool Type | Execute | Unit Test |
|-----------|---------|-----------|
| OpenAPI Toolset | ✅ | ✅ |
| Python Functions | ✅ | ✅ |
| DataStore Tools | ✅ | ✅ |
| Google Search | ✅ | ✅ |
| Connector Tools | ✅ | ❌ |
| MCP Tools | ❌ | ❌ |

## Additional Resources

- [CX Agent Studio Documentation](https://cloud.google.com/agent-studio/docs)
- [CX Agent Studio Best Practices](https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps/best-practices)
- [Google Cloud CES API Reference](https://cloud.google.com/agent-studio/docs/reference)

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 0.1.2 | 2026-02 | Current preview release |

---

*Note: CXAS SCRAPI is currently in preview. APIs and features may change.*
