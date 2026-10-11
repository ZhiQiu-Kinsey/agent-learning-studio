# Model access and execution evidence

**English** · [简体中文](multi-provider-review.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

The platform keeps the raw HTTP teaching path and uses the LiteLLM SDK to adapt other providers. Each lesson still owns its messages, tools and loop, while the backend manages model connections in one place.

## Where it lives

- `server/providers.py`: provider bindings, connection configuration validation, and the backend's temporary in-memory configuration.
- `course/providers.py`: the model connection types and the LiteLLM call adapter.
- `course/api_client.py`: the Bailian raw HTTP transport.
- `course/execution.py`: the call budget, cancellation and event snapshots shared by lessons.

The Bailian raw entry point reads `local_config.py` and `DASHSCOPE_API_KEY`. Other services use their own environment variables or the temporary backend configuration submitted from the web page. The variable list and the steps are in the [README](../../README.md#connecting-a-model). Keys are never echoed and never stored in browser storage. Switching providers never borrows another provider's credentials automatically.

## How evidence is represented

| Call path | Representation in the inspector | Boundary |
| --- | --- | --- |
| Bailian raw HTTP | Full request and response bodies | Authentication headers don't enter events |
| LiteLLM SDK | SDK-standardized request and response | It has gone through the SDK adapter, so it can't pass as a raw on-the-wire HTTP message |

One SDK request event stands for one SDK call, and isn't guaranteed to equal one underlying network attempt. Unknown token usage is not counted as zero. The model's tool proposal and Python's actual execution are recorded separately. A custom lesson uses the shared RunContext and doesn't build its own key reading or transport.

## Connection and run boundaries

An API Base URL may be HTTPS, or HTTP on local localhost. Addresses that contain credentials, query parameters, fragments or an invalid path are rejected. The user fills in the model ID for the actual provider, and the platform doesn't infer capabilities from the display name. Ollama needs a local service that already exists; the platform doesn't download models automatically.

Stopping a run blocks later calls. An upstream request that has already been sent may continue until the response arrives or the transport times out. Configuration lives only in backend memory, and after a restart the environment variables and local files take over again. The platform is for single-user local learning and binds to 127.0.0.1 by default.

Provider tests use deterministic responses. A real connection check must be configured and run by hand, and it produces usage. A passing test doesn't mean every vendor or model has been verified.
