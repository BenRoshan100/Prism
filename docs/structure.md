# Project Structure — Prism

```
prism/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
├── config.yaml                      # All tunable params (chunk sizes, weights, eval flags)
├── Dockerfile
├── render.yaml
├── .gitignore
│
├── .claude/
│   ├── settings.json
│   ├── hooks/
│   │   └── session-reflect.sh
│   └── rules/
│       ├── memory-profile.md        # Facts about Ben
│       ├── memory-preferences.md    # How Ben likes things done
│       ├── memory-decisions.md      # Technical decisions log
│       ├── memory-sessions.md       # Session log
│       └── coding-standards.md     # Code style rules
│
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   ├── api-spec.md
│   └── structure.md                 # This file
│
├── server/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app, lifespan startup
│   ├── ingest.py                    # Load → ParentDocumentRetriever → embed → store
│   ├── retriever.py                 # Hybrid: dense + BM25 + RRF + reranker
│   ├── bm25_index.py               # BM25 index singleton
│   ├── reranker.py                  # Cross-encoder reranker singleton
│   ├── memory.py                    # ConversationBufferWindowMemory
│   ├── chain.py                     # ConversationalRetrievalChain
│   ├── utils.py                     # Config loader, logger, token counter
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py                  # POST /api/chat, DELETE /api/chat/memory
│   │   ├── upload.py               # POST /api/upload
│   │   └── eval.py                  # GET /api/eval/session, POST /api/eval/precision|ragas
│   └── eval/
│       ├── __init__.py
│       ├── precision.py             # Precision@K
│       ├── faithfulness.py          # LLM-as-Judge (1–5 score)
│       └── ragas_eval.py           # RAGAS (4 metrics)
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                  # Tab nav: Chat | Eval | Upload
│       ├── api.js                   # Axios client
│       └── components/
│           ├── ChatTab.jsx
│           ├── EvalDashboard.jsx    # RAGAS scorecard + Precision@K + LangSmith link
│           ├── UploadTab.jsx        # Drag-and-drop upload
│           ├── MessageBubble.jsx
│           └── SourceExpander.jsx
│
├── scripts/
│   ├── run_ingest.py               # CLI ingestion
│   ├── run_eval.py                  # CLI Precision@K eval
│   ├── run_ragas_eval.py           # CLI RAGAS eval
│   └── benchmark_chunks.py         # Sweep chunk sizes, plot Precision@K
│
├── tests/
│   ├── test_ingest.py
│   ├── test_retriever.py
│   ├── test_reranker.py
│   ├── test_chain.py
│   ├── test_eval.py
│   └── test_ragas.py
│
├── data/
│   ├── raw/                         # Drop PDFs here (gitignored)
│   └── ground_truth/
│       └── eval_pairs.json          # 20 query/chunk pairs + ground_truth field
│
├── sample_data/                     # Seeded sample PDFs for demo
└── chroma_db/                       # Auto-created, gitignored
```
