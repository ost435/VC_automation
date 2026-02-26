## VC Automation FastAPI UI

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BASIC_AUTH_USER=admin
export BASIC_AUTH_PASS=changeme
uvicorn main:app --reload
```

Open http://127.0.0.1:8000 and authenticate with the env credentials.
