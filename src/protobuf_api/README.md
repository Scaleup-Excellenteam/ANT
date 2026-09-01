# Shared Protobuf interface

`autocomplete.proto` is the language-neutral contract for an autocomplete client and
this project. It defines:

- `SearchRequest`: query, corpus/AI mode, optional AI context, and result limit;
- `SearchResponse`: the echoed request, suggestions, elapsed time, and a stable error;
- `Suggestion.origin`: a `oneof` carrying either corpus source/offset/score metadata
  or the AI model name.

`autocomplete_pb2.py` is generated code. Do not edit it manually. Regenerate it from
the project root after changing the schema:

```powershell
python -m grpc_tools.protoc -I src/protobuf_api --python_out=src/protobuf_api src/protobuf_api/autocomplete.proto
```

## Actual binary round trip

Run a corpus request without any API key:

```powershell
python -m src.protobuf_api.demo --query "to pe" --mode corpus --max-results 2
```

Or run an AI request after setting `GEMINI_API_KEY`:

```powershell
python -m src.protobuf_api.demo --query "Thank you for" --mode ai --context "concise professional email" --max-results 3
```

The demo serializes a generated `SearchRequest` with `SerializeToString()`, displays
the byte length and hexadecimal payload, passes the bytes into the existing search
components, serializes a `SearchResponse`, and parses it back for display.

Protobuf supplies the schema, generated bindings, and binary serialization. It does
not send the bytes. Another component can use this contract over HTTP, gRPC, a message
queue, a socket, or a file without changing the message structure.
