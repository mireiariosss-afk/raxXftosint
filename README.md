# raxXftosint

Single-project multi-endpoint OSINT API (Vercel-ready, hardcoded, no env needed).

Docs panel: `/api/docs` (Vercel mounts the app at `/api`, no rewrites)

| Endpoint | Example |
|---|---|
| `GET /api/gstin?gstinNum=21AABCF8078M2ZC` | GSTIN verification |
| `GET /api/search?keyword=flipkart` | Search by name/PAN |
| `GET /api/returns?gstinNum=21AABCF8078M2ZC&financial_year=2026-27` | Return filing status |
| `GET /api/gstin-to-pan?gstin=29AAAAA0000A1Z5` | PAN extract |
| `GET /api/fastag?vehicle_number=KA01AB1234` | Fastag info |
| `GET /api/challan?vehicle_number=KA01AB1234&status=PENDING` | Challan list |
| `GET /api/pan?pan=AXDPR2606K` | PAN info (name, dob, status) |
| `GET /api/pk?number=03359736848` | PK SIM/CNIC info (name, cnic, network) |
| `POST /api/pk` `{"number":"03359736848"}` | PK SIM/CNIC info (JSON body) |
| `GET /api/phone-to-upi?phone=8449171549` | Phone to VPA + full UPI/bank details |
| `GET /api/num-to-upi?phone=8449171549` | Alias for phone-to-upi |
| `GET /api/dl?dlno=DL1234567890&dob=YYYY-MM-DD` | Read-only driving-licence lookup |
| `GET /api/health` | Health |

Deploy: Import this repo in Vercel -> Deploy (no env setup).
