"""Everything that talks to the model.

The provider is not fixed. `client.py` speaks the OpenAI-compatible chat
protocol to whatever endpoint `.env` points at, so changing provider - Gemini,
Groq, OpenRouter, a local model, OpenAI - touches configuration only, never
this package."""
