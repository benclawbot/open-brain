# Five-minute memory store and retrieval example

This is a **local demonstration**; use non-sensitive test text.

1. Start the local stack from a checkout:

   ```bash
   bash scripts/quickstart.sh
   ```

2. Store a deliberately fictional decision, then search it:

   ```bash
   openbrain store "Example project Atlas stores test fixture data locally" --source cli --tag atlas-example
   openbrain search "Where does project Atlas keep its test fixtures?"
   openbrain stats
   ```

3. Inspect the authenticated API contract at http://127.0.0.1:8765/docs. The local stack uses the `API_PORT` value from your `.env`. API key authentication is still required for protected endpoints.
4. Connect an MCP-capable agent to `python -m src.main` if you need interactive `memory_store`, `memory_search` and `memory_get_related` tools.

## Expected behavior

The search result should retrieve the fictional decision (assuming embeddings are ready). The indexed memory retains source attribution to `cli`. Relevance scores and exact ordering may vary with model/version.

Delete the example record using the supported CLI/API maintenance workflow if this is a shared real memory store. For persistent tests, prefer an isolated disposable database.

Open Brain does **not** automatically promote every imported claim to a user-confirmed fact. See [Security and authority](../README.md#security-and-authority).
