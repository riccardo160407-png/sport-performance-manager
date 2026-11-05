# SPORT PERFORMANCE MANAGER

Prototype for managing athletes and reviewing training files (FIT, TCX, GPX, CSV).

## Status
This repository is the starting prototype, not a production-ready hosted service. The current prototype uses a local SQLite database (`sport_performance.db`). On a cloud host with ephemeral storage, data may be lost; do not enter real athlete or health-related data until persistent cloud storage, access controls, backups, and privacy protections have been implemented and tested.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On first launch, create the coach account. Use strong unique passwords. The app is intended for private coaching use; do not expose it publicly in its current form.

## Next steps before online use
- Replace local SQLite with managed persistent storage (for example, Supabase/Postgres).
- Enforce server-side row-level access so each athlete can access only their own records.
- Store uploaded files securely and validate file contents and size.
- Configure secrets outside the repository; never commit credentials or athlete data.
- Test backup, restore, authentication, and authorization before inviting athletes.
