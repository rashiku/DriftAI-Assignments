# Internal team notes

These notes are intentionally fictional and are used as the internal source for the research agent.

- Current RAG corpus: approximately 1,000,000 documents.
- Expected growth: approximately 20% per year.
- The application is already heavily invested in PostgreSQL for relational application data.
- Search results must support a hard per-tenant metadata filtering requirement.
- The team wants to avoid operating a separate database service unless the operational benefit is material.
- The service is expected to scale horizontally as usage grows.
- The team can operate PostgreSQL confidently; operating a new specialized database would add operational overhead.
- Performance matters, but the team has not specified a benchmark target. Do not invent a benchmark result.
