# Breathe ESG — Carbon Data Ingestion Prototype

A Django REST + React prototype for ingesting, normalizing, and reviewing carbon emission data from three enterprise sources: SAP (fuel & procurement), utility portals (electricity), and corporate travel platforms (Concur).

## Demo credentials

```
URL: https://breathe-esg-prototype-six.vercel.app
Admin:   admin / demo1234
Analyst: analyst / demo1234
```

> Note: Backend is on Render free tier — first request may take ~50 seconds to wake up.

## Sample data files

Upload these from the `sample_data/` directory to try the ingestion flow:

| File | Source type | What it tests |
|---|---|---|
| `sap_fuel_mb51.csv` | SAP Fuel | Diesel, petrol, LPG, CNG across 4 plants; includes a statistical outlier row |
| `sap_procurement_me2n.csv` | SAP Procurement | Industrial goods across 5 categories; spend-based Scope 3 |
| `utility_greenbutton.csv` | Utility Electricity | Hourly interval data, 2 meters, TOD tariff codes |
| `concur_travel_export.csv` | Corporate Travel | Domestic + international flights, hotels, ground transport |

## Local development

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py create_demo_data
python manage.py runserver
```

API runs at http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173

## Architecture

- **Backend:** Django 5.1 + Django REST Framework, token authentication, PostgreSQL
- **Frontend:** React 18 + Vite + Tailwind CSS
- **Deployment:** Backend on Render (free tier), Frontend on Vercel

## Documentation

- [MODEL.md](docs/MODEL.md) — Data model and design rationale
- [DECISIONS.md](docs/DECISIONS.md) — Every ambiguity resolved and why
- [TRADEOFFS.md](docs/TRADEOFFS.md) — Three deliberate omissions
- [SOURCES.md](docs/SOURCES.md) — Research on each data source format
