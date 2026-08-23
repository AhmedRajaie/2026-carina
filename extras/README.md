# extras/

Optional, self-contained deep-dives. Nothing here is required. Each is one big
notebook you can run top to bottom.

**The gate:** an AI extra earns its place only if it makes your **dashboard**
better. These two do — news sentiment and a market Q&A chat both become panels.
Both keep the LLM on *explanation and context*, never on the trade itself.

- `llm-news-sentiment.ipynb` — score headlines per stock with Gemini, show a
  sentiment panel.
- `rag-market-chat.ipynb` — a small RAG chat over market notes, using a local
  Chroma vector DB + Gemini.

## API keys (free tiers)
- **Gemini:** free key at https://aistudio.google.com/apikey. Set it as an
  environment variable `GEMINI_API_KEY` before running.
- **Chroma:** runs locally, no account, no cost.

Both notebooks have a **MOCK mode** that runs without any key, so you can see the
flow first and add a key only when ready.
