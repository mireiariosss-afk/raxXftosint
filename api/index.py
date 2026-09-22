"""raxXftosint - single-project multi-endpoint OSINT lookup API (Vercel-ready).

Working upstreams (verified 2026-09-22):
- mastersindia GSTIN / search / returns
- parkplus fastag + challan

Docs panel: GET /docs (Swagger UI)
"""
from __future__ import annotations

import random
import string

import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# ---- hardcoded config (no env, as requested) ----
TIMEOUT = 12

MI_BASE = "https://blog-backend.mastersindia.co/api/v1/custom/search"
MI_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://www.mastersindia.co",
    "referer": "https://www.mastersindia.co/gst-number-search-and-gstin-verification/",
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not=A?Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
}

PARKPLUS_AUTH = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6InYxIn0.eyJleHAiOjE3OTE3MDQ3MTYsInN1YiI6IjM2ODEwOTM0IiwidW5pcXVlX2lkIjoiRHRRcm1WcXF4dElQWWN5dElGTHJJVGt2VlJoTXJhSFdEWFNIY1RQeHFTZlRjUndGV2t4S2x2TEJqb0NVaUJqTiIsImh0dHBzOi8vcGFya3doZWVscy5jby5pbi8iOnsidXNlcl9pZCI6MzY4MTA5MzQsIm5hbWUiOiIgIiwiZW1haWwiOiIiLCJwaG9uZV9udW1iZXIiOiI5MDk4OTUzNjI2Iiwicm9sZSI6ImNsaWVudCIsImRldmljZV9pZCI6bnVsbCwidmVyc2lvbiI6NCwidGVzdF91c2VyIjpmYWxzZX19.fL_yntQnw4qchVHmG0Nt5VOTme2gXAY2DddVKKqwqrrvICAVkEEVlE5vg5vNrHK-e8_PpZdw7d0dIq2lXQksrg"
PARKPLUS_CLIENT_ID = "8186c1be-660f-428c-93a7-6480c2d8af66"
PARKPLUS_CLIENT_SECRET = "hjjh0uw8c3j7vw5jgba8"
PARKPLUS_DEVICE_ID = "b2f165731e4ecdd12ab8375b3861b3b5"

app = FastAPI(title="raxXftosint", description="GSTIN + Fastag + Challan - single project, multi endpoint", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


def _random_uid(length: int = 29) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def _mi_get(endpoint: str, params: dict[str, str], need_uid: bool = True) -> dict[str, object]:
    url = f"{MI_BASE}/{endpoint}/"
    try:
        p = dict(params)
        if need_uid:
            p["unique_id"] = _random_uid()
        r = requests.get(url, params=p, headers=MI_HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        return {"success": False, "error": f"Upstream request failed: {e}"}
    if r.status_code in (403, 206):
        try:
            p2 = dict(params)
            if not need_uid:
                p2["unique_id"] = _random_uid()
            r2 = requests.get(url, params=p2, headers=MI_HEADERS, timeout=TIMEOUT)
            r = r2
        except requests.RequestException:
            pass
    if r.status_code == 403:
        return {"success": False, "error": "Upstream rate limit (403). Try again later."}
    try:
        body = r.json()
    except ValueError:
        return {"success": False, "error": f"Upstream non-JSON (HTTP {r.status_code})"}
    if isinstance(body, dict):
        return body
    return {"success": False, "error": "Unexpected upstream shape"}


def _clean(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v if v and v.lower() not in ("na", "n/a", "null", "-") else None
    return value


def _fmt_addr(addr: object) -> object:
    if not isinstance(addr, dict):
        return addr
    parts = [_clean(addr.get(k)) for k in ("flno", "bno", "bnm", "st", "loc", "dst", "stcd", "pncd")]
    return ", ".join(p for p in parts if isinstance(p, str) and p)


def _clean_record(rec: object) -> object:
    if not isinstance(rec, dict):
        return rec
    out: dict[str, object] = {}
    for k, v in rec.items():
        if k in ("pradr", "adadr"):
            continue
        cv = _clean(v)
        if cv is not None and not (isinstance(cv, list) and not cv):
            out[k] = cv
    pradr = rec.get("pradr") or {}
    paddr = pradr.get("addr") if isinstance(pradr, dict) else {}
    out["pradr"] = {"address": _fmt_addr(paddr), "ntr": _clean(pradr.get("ntr")) if isinstance(pradr, dict) else None}
    adadr: list[dict[str, object]] = []
    raw_ad = rec.get("adadr") if isinstance(rec, dict) else None
    if isinstance(raw_ad, list):
        for a in raw_ad:
            if not isinstance(a, dict):
                continue
            line = _fmt_addr(a.get("addr"))
            ntr = _clean(a.get("ntr"))
            if line or ntr:
                adadr.append({"address": line, "ntr": ntr})
    out["adadr"] = adadr
    return out


def _park_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {
        "accept": "application/json, text/plain, */*",
        "app-name": "Park+ PWA",
        "authorization": PARKPLUS_AUTH,
        "client-id": PARKPLUS_CLIENT_ID,
        "client-secret": PARKPLUS_CLIENT_SECRET,
        "device-id": PARKPLUS_DEVICE_ID,
        "new-device-id": PARKPLUS_DEVICE_ID,
        "origin": "https://parkplus.io",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    }
    if extra:
        h.update(extra)
    return h


@app.get("/api/index", include_in_schema=False)
def _diag_probe() -> dict[str, str]:
    return {"diag": "rewrite-shadow-probe", "build": "cb4a999+probe"}


@app.get("/", include_in_schema=False)
def root() -> dict[str, object]:
    return {
        "service": "raxXftosint",
        "docs": "/docs",
        "endpoints": {
            "gstin": "/api/gstin?gstinNum=21AABCF8078M2ZC",
            "search": "/api/search?keyword=flipkart",
            "returns": "/api/returns?gstinNum=21AABCF8078M2ZC&financial_year=2026-27",
            "gstin_to_pan": "/api/gstin-to-pan?gstin=29AAAAA0000A1Z5",
            "fastag": "/api/fastag?vehicle_number=KA01AB1234",
            "challan": "/api/challan?vehicle_number=KA01AB1234&status=PENDING",
            "health": "/health",
        },
    }


@app.get("/home", include_in_schema=False)
def home_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/gstin", tags=["gstin"])
def get_gstin(gstinNum: str = Query(..., min_length=15, max_length=15)) -> dict[str, object]:
    """Full GSTIN verification."""
    gstin = gstinNum.strip().upper()
    data = _mi_get("gstin", {"keyword": gstin})
    if not data.get("success"):
        return {"status": "error", "message": data.get("error", "Not found")}
    return {"status": "success", "data": _clean_record(data.get("data"))}


@app.get("/api/search", tags=["gstin"])
def search_by_name(keyword: str = Query(..., min_length=3)) -> dict[str, object]:
    """Search GST numbers by business name or PAN."""
    data = _mi_get("name_and_pan", {"keyword": keyword.strip()}, need_uid=False)
    if not data.get("success"):
        return {"status": "error", "message": data.get("error", "Not found")}
    records = data.get("data") or []
    recs = records if isinstance(records, list) else []
    return {"status": "success", "count": len(recs), "data": [_clean_record(r) for r in recs]}


STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "32": "Kerala", "33": "Tamil Nadu",
    "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}


@app.get("/api/gstin-to-pan", tags=["gstin"])
def gstin_to_pan(gstin: str = Query(..., min_length=15, max_length=15)) -> dict[str, object]:
    """Extract PAN from GSTIN (chars 3-12)."""
    g = gstin.strip().upper()
    if len(g) != 15 or not g.isalnum():
        return {"status": "error", "message": "Invalid GSTIN. Must be 15 alphanumeric characters."}
    return {"status": "success", "pan": g[2:12], "state": STATE_CODES.get(g[:2], f"Unknown ({g[:2]})")}


@app.get("/api/returns", tags=["gstin"])
def gst_returns(
    gstinNum: str = Query(..., min_length=15, max_length=15),
    financial_year: str = Query("2026-27"),
) -> dict[str, object]:
    """GST return filing status (GSTR-1, GSTR-3B)."""
    gstin = gstinNum.strip().upper()
    data = _mi_get("gst_return_status", {"keyword": gstin, "financial_year": financial_year.strip()})
    if not data.get("success"):
        return {"status": "error", "message": data.get("error", "Not found")}
    return {"status": "success", "data": data.get("data")}


@app.get("/api/fastag", tags=["vehicle"])
def fastag_lookup(vehicle_number: str = Query(..., min_length=4)) -> dict[str, object]:
    """Fastag owner/bank info by vehicle number."""
    vrn = vehicle_number.strip().upper().replace(" ", "")
    try:
        r = requests.post(
            "https://fastag-issuance.parkplus.io/fastag-recharge/tag/v2/vrn-detail",
            json={"vehicle_number": vrn, "source": "recharge"},
            headers=_park_headers({"content-type": "application/json;charset=UTF-8", "platform": "web", "package-name": "web.pwa"}),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return {"status": "error", "message": f"Upstream request failed: {e}"}
    try:
        body = r.json()
    except ValueError:
        return {"status": "error", "message": f"Upstream non-JSON (HTTP {r.status_code})"}
    if not isinstance(body, dict) or body.get("status") != 0:
        msg = body.get("message") if isinstance(body, dict) else "lookup failed"
        return {"status": "error", "message": msg or "lookup failed"}
    return {"status": "success", "vehicle_number": vrn, "data": body.get("data")}


@app.get("/api/challan", tags=["vehicle"])
def challan_lookup(
    vehicle_number: str = Query(..., min_length=4),
    status: str = Query("PENDING"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, object]:
    """Challan list by vehicle number."""
    vrn = vehicle_number.strip().upper().replace(" ", "")
    try:
        r = requests.get(
            "https://challan.parkplus.io/api/v1/challan/challan-list",
            params={"vehicle_number": vrn, "status": status.strip().upper(), "page": page, "limit": limit},
            headers=_park_headers({"platform": "mweb"}),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return {"status": "error", "message": f"Upstream request failed: {e}"}
    try:
        body = r.json()
    except ValueError:
        return {"status": "error", "message": f"Upstream non-JSON (HTTP {r.status_code})"}
    if not isinstance(body, dict) or body.get("status") != 0:
        msg = body.get("message") if isinstance(body, dict) else "lookup failed"
        return {"status": "error", "message": msg or "lookup failed"}
    return {"status": "success", "vehicle_number": vrn, "data": body.get("data")}
