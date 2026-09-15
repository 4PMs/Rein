# Tempera Console

Live Run console using the existing `runs/`, `scenarios/`, and `tempera.runner` artifacts.

```powershell
# backend
uvicorn console.backend.main:app --reload --port 8000

# frontend
cd console/frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The old Flask panel remains available as a fallback while this console is verified.
