# resume-ATS-matcher
Resume ATS matcher and editor (v0.1).

## Quick start
1) Install deps
```
uv sync
```

2) Install spaCy model
```
uv run python -m spacy download en_core_web_sm
```

3) Run the app
```
uv run streamlit run app.py
```

## What v0.1 includes
- Upload .docx resume, parse sections/roles/bullets
- Paste JD text or provide URL
- Extract skill terms, rank with MMR, embed, and classify skill matches
- Extract requirement sentences and match against resume bullets
- Coverage report split into skill and requirement sections with evidence
- Separate strong/weak thresholds for skills and requirements
- Selectable ranking and matching strategies (MMR, TF-IDF, hybrid)
- Human-in-the-loop edits with explicit accept
- Export tailored .docx
