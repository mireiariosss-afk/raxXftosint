"""raxXftosint - single-project multi-endpoint OSINT lookup API (Vercel-ready).

Working upstreams (verified 2026-09-22):
- mastersindia GSTIN / search / returns
- parkplus fastag + challan

Docs panel: GET /docs (Swagger UI)
"""
from __future__ import annotations

import random
import json
import re
import string
import threading
import time

import json
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

# --- turtlemint (pan) - hardcoded, verified working 2026-09-22 ---
TURTLE_BASE = "https://turtlemintloans.com/api/minterprise/v1/products/personal-loan/leads/existing-lead-by-pan"
TURTLE_BEARER = "9164b80a95d58333dcca54bf7d109edfe0c295848217a45315536b1a47a2aa6c4fe9fb1da604604b5466723215760078"
TURTLE_TOKEN_ID = "ODEzMDQ5NzgxNDo2MDZL"
TURTLE_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "authorization": f"Bearer {TURTLE_BEARER}",
    "content-type": "application/json",
    "priority": "u=1, i",
    "referer": "https://turtlemintloans.com/products/personal-loan/customer/MULTI/apply",
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not=A?Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "x-broker": "turtlemint",
    "x-partner-id": "undefined",
    "x-provider": "signzy",
    "x-tenant": "turtlemint",
}
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

IMSIDATA_URL = "https://imsidata.com/wp-admin/admin-ajax.php"
IMSIDATA_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "origin": "https://imsidata.com",
    "referer": "https://imsidata.com/search/",
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not=A?Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "x-requested-with": "XMLHttpRequest",
}
PK_PHONE_RE = re.compile(r"^[0-9+\- ]{10,15}$")
AMAZON_COOKIE = 'session-id=524-3333471-4402345; i18n-prefs=INR; ubid-acbin=523-4707979-0161653; csd-key=eyJ3YXNtVGVzdGVkIjp0cnVlLCJ3YXNtQ29tcGF0aWJsZSI6dHJ1ZSwid2ViQ3J5cHRvVGVzdGVkIjpmYWxzZSwidiI6MSwia2lkIjoiMzc0YWM2Iiwia2V5IjoiSVpZb2RER2JqTU4yMmpqL1cvc2ZaRmZCeUtBRy9hY250bGRzYkVEVEVrY3RWVTEvcENiNkUxc1RQbWVSR09GcWxFbFozaERVbEZRbDJuS0pWOFhSUTlGQ2FiYUxBVXh2eHBsVXRrYUJJM0o0OUNhQ054NXRkdFpGbWVSdU5jUVcwMVlYdlVRUTRHTGJ0SEVZa042WTREK2kyTk5kejltcWRHcTBUSG1WQ1FBbVUwRTBNYWdIK1R1anliSGtEeVhad3B0MnZUVTdqM2pEamRQaStENElMSlA2bXJBNy8yS2N1Y2ZMTXJSVmJtRE5JMzJPTGZNcEhpVGZhRUJCQ2tPMDBnSXVUWFFvd2Z5WlNYNVloSTBhNzBVeVBrNDZOM1g2N2lXciszbWZTd0tYb0l0dC9jODBEZDNFd3J0c1pjS05oNXdIUzEzaHc1STNQaklabFF4SVV3PT0ifQ==; lc-acbin=en_IN; sso-state-acbin=Xdsso|ZQHijZ6vzY7FlQCHcSd4oHpqE-e_piS6VH0yxcp2jOgS5DYe_QBSM_YbkP_rHpbU4-12WJhVadsSrHR8r08dmm_bKIumlcqQ9vWKZxv8l8h3tPD7; at-acbin=Atza|gQCmXgdvAwEBAkQHbxvxbZ3WK1Gx0CFjBis3KjY4TTeySRFIu3f_IEzx0XOUAn_GeeQqlMupQgSBSFGP667Ru2vEevt3ResY7dhyQjZizafcd15_mZZylGQmw3Y0yjnxE3mRSb0OBbKzRdRPomTAUuDS5_Zyr0qHGbRv-RwcnmDGRu0r8DltJuY-XJ-TjMplhsohKTx10ipR5sCeT1B8jYASfi9IYmUOOFfNgWh8vijFCNElYdYI1NtTZaET_-9WhWhGqfPp-JQ9HLupTQd5jAMmFRRB_lIjXKJ7Ih2f2DO8hV9SHq4QXiq08JETXDSIK3Kr00I3JZoDmKFFj7Dd0UG6QKEMiZmfClT0jf_slJ-OOroHaEfRhZHnZ5TspWY8MZ6dDhu_cHNcYZ8CWAGs0Mk1_Le2d2fV9gJIAM-zpmq71No; sess-at-acbin=60K42HpUyti0bPQ2Ne8bD0dE/bK4zc7ztkTRog168co=; sst-acbin=Sst1|PQJxS1omQzGbXvq7AZ8R3Gz0DT4vct4LEDlvDqwpvZPLMX-HWHQ1divyu_0qq3JZJkAJ0c9BMGEMsyuDhVVzT2gbyjEmakLcbcFehw3BkqIW60KObs6mty1K1KqKORg2isyPSdYFlZlVrs6wZpo43KLovPbkaz9Gh7rQZq5q4LA0ZxeP07z3sGd5oUMbPAsAB5HcECCnp2-6fIbG6i1HMyUajd5UBjs2_Ka3sSif6NUIcPnQy-krvbNgxwLVm6euVLzvJYN22OkLRzdiYzSa1M3n1SfoAvkW4-l3aB2BHxqmFrobq2zaNJ7SNV3-h12_909_JfF9IUgmjB1kVTq1nqSgZDonYJwQl9II9yiZxnsvKXHV33SlimGN9vpkslrTeloI; session-id-time=2082787201l; csm-hit=tb:s-JMMN3CY6JTFYJJ70R0K5|1790090662184&t:1790090662941&adb:adblk_no; session-token=fGAkYvhwlSCygZtM6CCJmwQHOmi3CcfbTS0UxVKXtMViC77smxg08miiD094/soOjQ+LRlv45sx1VRyX3GOi2TDZkPiweyq5JzXptbUnZXzPRChRRqBLc/nITNa5nC7okhSHVZSLRQ/hZru2H/zAnifuXxsQNtf0W+J4HB2D190WlNkJHez52q+kOPfwwUSDx9R1ZVy0QUFmOK5fPuCCxJV9wIks3jMazf8rmsxxV+uQSrIfRq3X6ky7iZyhNTnv; x-acbin="RRkQ@TTJGUuQIM9jgNS6WkZxeIYoAxRrNaujyZ@HuemU@tpGHTXFrNslCxLh89m7"; rxc=APnSMUR6RxzeZ4GerHs'
AMAZON_URL = "https://www.amazon.in/apay/money-transfer/verify-vpa/v2"
AMAZON_DEVICE = 'mobile-device-info=dpi:300.0|w:720|h:1600; amzn-app-ctxt=1.8%20%7B%22an%22%3A%22Amazon.com%22%2C%22av%22%3A%2230.22.0.300%22%2C%22xv%22%3A%221.16.0%22%2C%22os%22%3A%22Android%22%2C%22ov%22%3A%2215%22%2C%22cp%22%3A788760%2C%22uiv%22%3A4%2C%22ast%22%3A3%2C%22nal%22%3A%221%22%2C%22di%22%3A%7B%22pr%22%3A%22V2446iC%22%2C%22md%22%3A%22V2509%22%2C%22v%22%3A%22V2446%22%2C%22mf%22%3A%22vivo%22%2C%22dsn%22%3A%222df8901a9ca34ef48e1fc70480e942d4%22%2C%22dti%22%3A%22A1MPSLFC7L5AFK%22%2C%22ca%22%3A%22%22%2C%22ct%22%3A%22MOBILE%22%2C%22mct%22%3A13%7D%2C%22dm%22%3A%7B%22w%22%3A720%2C%22h%22%3A1600%2C%22ld%22%3A1.875%2C%22dx%22%3A265.7669982910156%2C%22dy%22%3A259.02099609375%2C%22pt%22%3A0%2C%22pb%22%3A78%7D%2C%22is%22%3A%22com.google.android.packageinstaller%22%2C%22msd%22%3A%22.amazon.in%22%7D; '

DIGI_MOBILE = "7989335216"
DIGI_PASS = "Pass@031212"
DIGI_AMOUNT = "200"
CASHFREE_UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Mobile Safari/537.36"
_cash_lock = threading.Lock()
_cash_cache: dict[str, object] = {"session_id": None, "created_at": 0.0, "ttl": 240}
AMAZON_HEADERS = {
    'User-Agent': "Amazon.com/30.22.0.300 (Android/15/V2509)",
    'Accept': "application/json; charset=utf-8",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'sec-ch-ua-full-version-list': "",
    'sec-ch-ua-platform': '"Android"',
    'viewport-width': "384", 'device-memory': "8",
    'sec-ch-ua': '"Not:A-Brand";v="99", "Android WebView";v="145", "Chromium";v="145"',
    'sec-ch-dpr': "1.875", 'sec-ch-ua-mobile': "?1",
    'content-type': "application/json; charset=utf-8",
    'sec-ch-viewport-width': "384", 'downlink': "10", 'ect': "4g",
    'sec-ch-device-memory': "8", 'dpr': "1.875", 'rtt': "0",
    'sec-ch-ua-platform-version': '""',
    'origin': "https://www.amazon.in",
    'x-requested-with': "in.amazon.mShop.android.shopping",
    'sec-fetch-site': "same-origin", 'sec-fetch-mode': "cors",
    'sec-fetch-dest': "empty",
    'referer': "https://www.amazon.in/apay/money-transfer/assets/ap4-eap/index.html",
    'accept-language': "en-IN,en-US;q=0.9,en;q=0.8",
    'priority': "u=1, i",
}

PSP = {
    "oksbi":       {"app": "Google Pay", "bank": "State Bank of India"},
    "okhdfcbank":  {"app": "Google Pay", "bank": "HDFC Bank"},
    "okaxis":      {"app": "Google Pay", "bank": "Axis Bank"},
    "okicici":     {"app": "Google Pay", "bank": "ICICI Bank"},
    "okpnb":       {"app": "Google Pay", "bank": "Punjab National Bank"},
    "okboi":       {"app": "Google Pay", "bank": "Bank of India"},
    "okbob":       {"app": "Google Pay", "bank": "Bank of Baroda"},
    "okcanara":    {"app": "Google Pay", "bank": "Canara Bank"},
    "okdhan":      {"app": "Google Pay", "bank": "Indian Bank"},
    "okidbi":      {"app": "Google Pay", "bank": "IDBI Bank"},
    "okindus":     {"app": "Google Pay", "bank": "IndusInd Bank"},
    "okkotak":     {"app": "Google Pay", "bank": "Kotak Mahindra Bank"},
    "oksbm":       {"app": "Google Pay", "bank": "SBM Bank India"},
    "okyes":       {"app": "Google Pay", "bank": "Yes Bank"},
    "okfbl":       {"app": "Google Pay", "bank": "Federal Bank"},
    "oksib":       {"app": "Google Pay", "bank": "South Indian Bank"},
    "okcbi":       {"app": "Google Pay", "bank": "Central Bank of India"},
    "okpost":      {"app": "Google Pay", "bank": "India Post Payments Bank"},
    "okfino":      {"app": "Google Pay", "bank": "Fino Payments Bank"},
    "okjio":       {"app": "Google Pay", "bank": "Jio Payments Bank"},
    "okuboi":      {"app": "Google Pay", "bank": "Union Bank of India"},
    "okmah":       {"app": "Google Pay", "bank": "Bank of Maharashtra"},
    "okuco":       {"app": "Google Pay", "bank": "UCO Bank"},
    "okiob":       {"app": "Google Pay", "bank": "Indian Overseas Bank"},
    "okcsb":       {"app": "Google Pay", "bank": "CSB Bank"},
    "okrbl":       {"app": "Google Pay", "bank": "RBL Bank"},
    "okdlb":       {"app": "Google Pay", "bank": "Dhanlaxmi Bank"},
    "okkvb":       {"app": "Google Pay", "bank": "Karur Vysya Bank"},
    "okesaf":      {"app": "Google Pay", "bank": "ESAF Small Finance Bank"},
    "okutkarsh":   {"app": "Google Pay", "bank": "Utkarsh Small Finance Bank"},
    "okshivalik":  {"app": "Google Pay", "bank": "Shivalik Small Finance Bank"},
    "okaubank":    {"app": "Google Pay", "bank": "AU Small Finance Bank"},
    "oknsdl":      {"app": "Google Pay", "bank": "NSDL Payments Bank"},
    "okairtel":    {"app": "Google Pay", "bank": "Airtel Payments Bank"},
    "okaditya":    {"app": "Google Pay", "bank": "Aditya Birla Payments Bank"},
    "oksaraswat":  {"app": "Google Pay", "bank": "Saraswat Cooperative Bank"},
    "okapna":      {"app": "Google Pay", "bank": "Apna Sahakari Bank"},
    "okcosmos":    {"app": "Google Pay", "bank": "Cosmos Cooperative Bank"},
    "oknkl":       {"app": "Google Pay", "bank": "NKGSB Cooperative Bank"},
    "ybl":         {"app": "PhonePe", "bank": "Yes Bank"},
    "axl":         {"app": "PhonePe", "bank": "Axis Bank"},
    "ibl":         {"app": "PhonePe", "bank": "ICICI Bank"},
    "payphone":    {"app": "PhonePe", "bank": "Yes Bank"},
    "yblpay":      {"app": "PhonePe", "bank": "Yes Bank"},
    "yblpe":       {"app": "PhonePe", "bank": "Yes Bank"},
    "axlpay":      {"app": "PhonePe", "bank": "Axis Bank"},
    "axlpe":       {"app": "PhonePe", "bank": "Axis Bank"},
    "paytm":       {"app": "Paytm", "bank": "Paytm Payments Bank"},
    "ptaxis":      {"app": "Paytm", "bank": "Axis Bank"},
    "pthdfc":      {"app": "Paytm", "bank": "HDFC Bank"},
    "ptsbi":       {"app": "Paytm", "bank": "State Bank of India"},
    "ptyes":       {"app": "Paytm", "bank": "Yes Bank"},
    "pticici":     {"app": "Paytm", "bank": "ICICI Bank"},
    "ptkotak":     {"app": "Paytm", "bank": "Kotak Mahindra Bank"},
    "ptindus":     {"app": "Paytm", "bank": "IndusInd Bank"},
    "ptrbl":       {"app": "Paytm", "bank": "RBL Bank"},
    "ptfederal":   {"app": "Paytm", "bank": "Federal Bank"},
    "ptboi":       {"app": "Paytm", "bank": "Bank of India"},
    "ptbob":       {"app": "Paytm", "bank": "Bank of Baroda"},
    "ptcanara":    {"app": "Paytm", "bank": "Canara Bank"},
    "ptunion":     {"app": "Paytm", "bank": "Union Bank of India"},
    "ptiob":       {"app": "Paytm", "bank": "Indian Overseas Bank"},
    "ptuco":       {"app": "Paytm", "bank": "UCO Bank"},
    "ptpnb":       {"app": "Paytm", "bank": "Punjab National Bank"},
    "ptmah":       {"app": "Paytm", "bank": "Bank of Maharashtra"},
    "ptcbi":       {"app": "Paytm", "bank": "Central Bank of India"},
    "ptsib":       {"app": "Paytm", "bank": "South Indian Bank"},
    "ptcsb":       {"app": "Paytm", "bank": "CSB Bank"},
    "ptdhan":      {"app": "Paytm", "bank": "Dhanlaxmi Bank"},
    "ptidbi":      {"app": "Paytm", "bank": "IDBI Bank"},
    "ptkvb":       {"app": "Paytm", "bank": "Karur Vysya Bank"},
    "ptdcb":       {"app": "Paytm", "bank": "DCB Bank"},
    "ptpsb":       {"app": "Paytm", "bank": "Punjab & Sind Bank"},
    "ptdlb":       {"app": "Paytm", "bank": "Dhanlaxmi Bank"},
    "ptaubank":    {"app": "Paytm", "bank": "AU Small Finance Bank"},
    "ptesaf":      {"app": "Paytm", "bank": "ESAF Small Finance Bank"},
    "ptutkarsh":   {"app": "Paytm", "bank": "Utkarsh Small Finance Bank"},
    "upi":         {"app": "BHIM"},
    "bhim":        {"app": "BHIM"},
    "npci":        {"app": "BHIM"},
    "apl":         {"app": "Amazon Pay", "bank": "Axis Bank"},
    "yapl":        {"app": "Amazon Pay", "bank": "Yes Bank"},
    "rapl":        {"app": "Amazon Pay", "bank": "RBL Bank"},
    "amazon":      {"app": "Amazon Pay", "bank": "Amazon Pay"},
    "amazonpay":   {"app": "Amazon Pay", "bank": "Amazon Pay"},
    "waicici":     {"app": "WhatsApp Pay", "bank": "ICICI Bank"},
    "waaxis":      {"app": "WhatsApp Pay", "bank": "Axis Bank"},
    "wahdfcbank":  {"app": "WhatsApp Pay", "bank": "HDFC Bank"},
    "wasbi":       {"app": "WhatsApp Pay", "bank": "State Bank of India"},
    "naviaxis":    {"app": "Navi", "bank": "Axis Bank"},
    "superyes":    {"app": "Super Money", "bank": "Yes Bank"},
    "ikwik":       {"app": "MobiKwik", "bank": "MobiKwik"},
    "mobikwik":    {"app": "MobiKwik", "bank": "MobiKwik"},
    "mbk":         {"app": "MobiKwik", "bank": "One MobiKwik"},
    "cred":        {"app": "CRED", "bank": "CRED"},
    "credapp":     {"app": "CRED", "bank": "CRED"},
    "credpay":     {"app": "CRED", "bank": "CRED"},
    "yescred":     {"app": "CRED", "bank": "Yes Bank"},
    "axisb":       {"app": "CRED", "bank": "Axis Bank"},
    "slice":       {"app": "Slice", "bank": "Garagepreneur Internet"},
    "sliceaxis":   {"app": "Slice", "bank": "Axis Bank"},
    "slicepay":    {"app": "Slice", "bank": "Slice"},
    "nslice":      {"app": "Slice", "bank": "Slice"},
    "bharatpe":    {"app": "BharatPe", "bank": "BharatPe"},
    "postpe":      {"app": "BharatPe", "bank": "BharatPe"},
    "bharat":      {"app": "BharatPe", "bank": "BharatPe"},
    "postpeat":    {"app": "BharatPe", "bank": "BharatPe"},
    "bpunity":     {"app": "BharatPe", "bank": "Unity Small Finance Bank"},
    "freecharge":  {"app": "Freecharge", "bank": "Axis Bank"},
    "nfreecharge": {"app": "Freecharge", "bank": "Axis Bank"},
    "fam":         {"app": "Fampay", "bank": "Tri O Tech"},
    "fampay":      {"app": "Fampay", "bank": "Tri O Tech"},
    "yesfam":      {"app": "Fampay", "bank": "Yes Bank"},
    "payzapp":     {"app": "PayZapp", "bank": "HDFC Bank"},
    "zoicici":     {"app": "Zomato UPI", "bank": "ICICI Bank"},
    "fkaxis":      {"app": "Flipkart UPI", "bank": "Axis Bank"},
    "tapicici":    {"app": "Tata Neu", "bank": "ICICI Bank"},
    "jupiteraxis": {"app": "Jupiter", "bank": "Axis Bank"},
    "goaxb":       {"app": "Kiwi", "bank": "Axis Bank"},
    "freoicici":   {"app": "Freo", "bank": "ICICI Bank"},
    "niyoicici":   {"app": "Niyo", "bank": "ICICI Bank"},
    "abfspay":     {"app": "Bajaj Finserv", "bank": "Axis Bank"},
    "pingpay":     {"app": "Samsung Pay", "bank": "Axis Bank"},
    "oneyes":      {"app": "OneCard", "bank": "Yes Bank"},
    "shriramhdfcbank": {"app": "Shriram One", "bank": "HDFC Bank"},
    "kphdfc":      {"app": "KreditPe", "bank": "HDFC Bank"},
    "groww":       {"app": "Groww", "bank": "Groww"},
    "yesg":        {"app": "Groww", "bank": "Yes Bank"},
    "axb":         {"app": "OkCredit", "bank": "Axis Bank"},
    "yespop":      {"app": "Popclub", "bank": "Yes Bank"},
    "seyes":       {"app": "Salaryse", "bank": "Yes Bank"},
    "spicepay":    {"app": "Spicepay", "bank": "Spice Money"},
    "timecosmos":  {"app": "Timepay", "bank": "Cosmos Co-op Bank"},
    "paymoni":     {"app": "Unimoni", "bank": "Unimoni Financial"},
    "idfcbank":    {"app": "Fave", "bank": "IDFC FIRST Bank"},
    "pinelabs":    {"app": "Fave", "bank": "Pine Labs"},
    "idfcpay":     {"app": "Firstrupi", "bank": "IDFC FIRST Bank"},
    "trans":       {"app": "Cheq", "bank": "Transcorp International"},
    "payu":        {"app": "Citrus Wallet", "bank": "PayU Payments"},
    "dhani":       {"app": "Dhani", "bank": "Transerv Limited"},
    "digikhata":   {"app": "Digikhata", "bank": "Pay Point India"},
    "ebixcash":    {"app": "Ebixcash", "bank": "Ebix Payments"},
    "nye":         {"app": "Nye", "bank": "Rapipay Fintech"},
    "omni":        {"app": "Omnicard", "bank": "Eroute Technologies"},
    "oxymoney":    {"app": "Oxymoney", "bank": "Appnit Technologies"},
    "pockets":     {"app": "Pockets", "bank": "ICICI Bank"},
    "liv":         {"app": "Quikwallet", "bank": "Livquik Technology"},
    "fbl":         {"app": "Cointab", "bank": "Federal Bank"},
    "sbi":         {"app": "SBI YONO", "bank": "State Bank of India"},
    "yono":        {"app": "SBI YONO", "bank": "State Bank of India"},
    "hdfcbank":    {"app": "HDFC Bank", "bank": "HDFC Bank"},
    "hdfc":        {"app": "HDFC Bank", "bank": "HDFC Bank"},
    "icici":       {"app": "ICICI Bank", "bank": "ICICI Bank"},
    "icicibank":   {"app": "ICICI Bank", "bank": "ICICI Bank"},
    "axis":        {"app": "Axis Bank", "bank": "Axis Bank"},
    "axisbank":    {"app": "Axis Bank", "bank": "Axis Bank"},
    "kotak":       {"app": "Kotak Mahindra Bank", "bank": "Kotak Mahindra Bank"},
    "kotakb":      {"app": "Kotak Mahindra Bank", "bank": "Kotak Mahindra Bank"},
    "kmbl":        {"app": "Kotak Mahindra Bank", "bank": "Kotak Mahindra Bank"},
    "yesbank":     {"app": "Yes Bank", "bank": "Yes Bank"},
    "yesb":        {"app": "Yes Bank", "bank": "Yes Bank"},
    "idbi":        {"app": "IDBI Bank", "bank": "IDBI Bank"},
    "indus":       {"app": "IndusInd Bank", "bank": "IndusInd Bank"},
    "indusb":      {"app": "IndusInd Bank", "bank": "IndusInd Bank"},
    "rbl":         {"app": "RBL Bank", "bank": "RBL Bank"},
    "federal":     {"app": "Federal Bank", "bank": "Federal Bank"},
    "union":       {"app": "Union Bank of India", "bank": "Union Bank of India"},
    "unionb":      {"app": "Union Bank of India", "bank": "Union Bank of India"},
    "canara":      {"app": "Canara Bank", "bank": "Canara Bank"},
    "canarab":     {"app": "Canara Bank", "bank": "Canara Bank"},
    "baroda":      {"app": "Bank of Baroda", "bank": "Bank of Baroda"},
    "barodab":     {"app": "Bank of Baroda", "bank": "Bank of Baroda"},
    "bob":         {"app": "Bank of Baroda", "bank": "Bank of Baroda"},
    "boi":         {"app": "Bank of India", "bank": "Bank of India"},
    "bankofindia": {"app": "Bank of India", "bank": "Bank of India"},
    "pnb":         {"app": "Punjab National Bank", "bank": "Punjab National Bank"},
    "pnbb":        {"app": "Punjab National Bank", "bank": "Punjab National Bank"},
    "uco":         {"app": "UCO Bank", "bank": "UCO Bank"},
    "iob":         {"app": "Indian Overseas Bank", "bank": "Indian Overseas Bank"},
    "cbi":         {"app": "Central Bank of India", "bank": "Central Bank of India"},
    "centralbank": {"app": "Central Bank of India", "bank": "Central Bank of India"},
    "mah":         {"app": "Bank of Maharashtra", "bank": "Bank of Maharashtra"},
    "aubank":      {"app": "AU Small Finance Bank", "bank": "AU Small Finance Bank"},
    "csb":         {"app": "CSB Bank", "bank": "CSB Bank"},
    "dlb":         {"app": "Dhanlaxmi Bank", "bank": "Dhanlaxmi Bank"},
    "sib":         {"app": "South Indian Bank", "bank": "South Indian Bank"},
    "kvb":         {"app": "Karur Vysya Bank", "bank": "Karur Vysya Bank"},
    "dcb":         {"app": "DCB Bank", "bank": "DCB Bank"},
    "psb":         {"app": "Punjab & Sind Bank", "bank": "Punjab & Sind Bank"},
    "esaf":        {"app": "ESAF Small Finance Bank", "bank": "ESAF Small Finance Bank"},
    "utkarsh":     {"app": "Utkarsh Small Finance Bank", "bank": "Utkarsh Small Finance Bank"},
    "shivalik":    {"app": "Shivalik Small Finance Bank", "bank": "Shivalik Small Finance Bank"},
    "sbm":         {"app": "SBM Bank India", "bank": "SBM Bank India"},
    "nsdl":        {"app": "NSDL Payments Bank", "bank": "NSDL Payments Bank"},
    "fino":        {"app": "Fino Payments Bank", "bank": "Fino Payments Bank"},
    "jio":         {"app": "Jio Payments Bank", "bank": "Jio Payments Bank"},
    "airtel":      {"app": "Airtel Payments Bank", "bank": "Airtel Payments Bank"},
    "airtelpay":   {"app": "Airtel Payments Bank", "bank": "Airtel Payments Bank"},
    "post":        {"app": "India Post Payments Bank", "bank": "India Post Payments Bank"},
    "ippb":        {"app": "India Post Payments Bank", "bank": "India Post Payments Bank"},
    "aditya":      {"app": "Aditya Birla Payments Bank", "bank": "Aditya Birla Payments Bank"},
    "indian":      {"app": "Indian Bank", "bank": "Indian Bank"},
    "indianb":     {"app": "Indian Bank", "bank": "Indian Bank"},
    "syndicate":   {"app": "Canara Bank", "bank": "Canara Bank"},
    "corporation": {"app": "Union Bank of India", "bank": "Union Bank of India"},
    "andhra":      {"app": "Union Bank of India", "bank": "Union Bank of India"},
    "allahabad":   {"app": "Indian Bank", "bank": "Indian Bank"},
    "dena":        {"app": "Bank of Baroda", "bank": "Bank of Baroda"},
    "vijaya":      {"app": "Bank of Baroda", "bank": "Bank of Baroda"},
    "orient":      {"app": "Indian Bank", "bank": "Indian Bank"},
    "united":      {"app": "Punjab National Bank", "bank": "Punjab National Bank"},
    "cosmos":      {"app": "Cosmos Cooperative Bank", "bank": "Cosmos Cooperative Bank"},
    "nklgsb":      {"app": "NKGSB Cooperative Bank", "bank": "NKGSB Cooperative Bank"},
    "saraswat":    {"app": "Saraswat Cooperative Bank", "bank": "Saraswat Cooperative Bank"},
    "apna":        {"app": "Apna Sahakari Bank", "bank": "Apna Sahakari Bank"},
    "shamrao":     {"app": "Shamrao Vithal Cooperative Bank", "bank": "Shamrao Vithal Cooperative Bank"},
    "tjsb":        {"app": "TJSB Sahakari Bank", "bank": "TJSB Sahakari Bank"},
    "jmb":         {"app": "Janata Sahakari Bank", "bank": "Janata Sahakari Bank"},
    "janata":      {"app": "Janata Sahakari Bank", "bank": "Janata Sahakari Bank"},
    "raj":         {"app": "Rajasthan Marudhara Gramin Bank", "bank": "Rajasthan Marudhara Gramin Bank"},
    "zerodha":     {"app": "Zerodha", "bank": "Zerodha"},
    "coin":        {"app": "Coin by Zerodha", "bank": "Coin by Zerodha"},
    "kuver":       {"app": "Kuver", "bank": "Kuver"},
    "jar":         {"app": "Jar", "bank": "Jar"},
    "chq":         {"app": "CHQ", "bank": "CHQ"},
    "superpay":    {"app": "Super Pay", "bank": "Kotak Mahindra Bank"},
    "tvam":        {"app": "TVAM", "bank": "Yes Bank"},
    "yuvapay":     {"app": "Yuva Pay", "bank": "Yes Bank"},
}

BANK_INFO = {
    "upi_bank_IPPB": {"name": "India Post Payments Bank", "type": "Payments Bank", "ifsc": "IPOS0000001"},
    "upi_bank_SBI": {"name": "State Bank of India", "type": "Public Sector Bank", "ifsc": "SBIN0000001"},
    "upi_bank_HDFC": {"name": "HDFC Bank", "type": "Private Sector Bank", "ifsc": "HDFC0000001"},
    "upi_bank_ICICI": {"name": "ICICI Bank", "type": "Private Sector Bank", "ifsc": "ICIC0000001"},
    "upi_bank_AXIS": {"name": "Axis Bank", "type": "Private Sector Bank", "ifsc": "UTIB0000001"},
    "upi_bank_KOTAK": {"name": "Kotak Mahindra Bank", "type": "Private Sector Bank", "ifsc": "KKBK0000001"},
    "upi_bank_YES": {"name": "Yes Bank", "type": "Private Sector Bank", "ifsc": "YESB0000001"},
    "upi_bank_PNB": {"name": "Punjab National Bank", "type": "Public Sector Bank", "ifsc": "PUNB0000001"},
    "upi_bank_BOB": {"name": "Bank of Baroda", "type": "Public Sector Bank", "ifsc": "BARB0000001"},
    "upi_bank_CANARA": {"name": "Canara Bank", "type": "Public Sector Bank", "ifsc": "CNRB0000001"},
    "upi_bank_INDUS": {"name": "IndusInd Bank", "type": "Private Sector Bank", "ifsc": "INDB0000001"},
    "upi_bank_RBL": {"name": "RBL Bank", "type": "Private Sector Bank", "ifsc": "RATN0000001"},
    "upi_bank_FEDERAL": {"name": "Federal Bank", "type": "Private Sector Bank", "ifsc": "FDRL0000001"},
    "upi_bank_IDFC": {"name": "IDFC First Bank", "type": "Private Sector Bank", "ifsc": "IDFB0000001"},
    "upi_bank_AIRTEL": {"name": "Airtel Payments Bank", "type": "Payments Bank", "ifsc": "AIRP0000001"},
    "upi_bank_JIO": {"name": "Jio Payments Bank", "type": "Payments Bank", "ifsc": "JIOB0000001"},
    "upi_bank_PAYTM": {"name": "Paytm Payments Bank", "type": "Payments Bank", "ifsc": "PYTM0000001"},
    "payapp_GOOGLE": {"name": "Google Pay", "type": "Payment App", "ifsc": None},
    "payapp_PHONEPE": {"name": "PhonePe", "type": "Payment App", "ifsc": None},
    "payapp_PAYTM": {"name": "Paytm", "type": "Payment App", "ifsc": None},
    "payapp_AMAZON": {"name": "Amazon Pay", "type": "Payment App", "ifsc": None},
    "payapp_CRED": {"name": "CRED", "type": "Payment App", "ifsc": None},
}

BID = {
    "SBI":     {"name": "State Bank of India", "ifsc_prefix": "SBIN"},
    "PNB":     {"name": "Punjab National Bank", "ifsc_prefix": "PUNB"},
    "UBI":     {"name": "Union Bank of India", "ifsc_prefix": "UBIN"},
    "HDF":     {"name": "HDFC Bank", "ifsc_prefix": "HDFC"},
    "ICICI":   {"name": "ICICI Bank", "ifsc_prefix": "ICIC"},
    "AXIS":    {"name": "Axis Bank", "ifsc_prefix": "UTIB"},
    "BOB":     {"name": "Bank of Baroda", "ifsc_prefix": "BARB"},
    "BOI":     {"name": "Bank of India", "ifsc_prefix": "BKID"},
    "CAN":     {"name": "Canara Bank", "ifsc_prefix": "CNRB"},
    "KOTAK":   {"name": "Kotak Mahindra Bank", "ifsc_prefix": "KKBK"},
    "IDBI":    {"name": "IDBI Bank", "ifsc_prefix": "IBKL"},
    "YES":     {"name": "Yes Bank", "ifsc_prefix": "YESB"},
    "INDUS":   {"name": "IndusInd Bank", "ifsc_prefix": "INDB"},
    "FED":     {"name": "Federal Bank", "ifsc_prefix": "FDRL"},
    "RBL":     {"name": "RBL Bank", "ifsc_prefix": "RATN"},
    "SOUTH":   {"name": "South Indian Bank", "ifsc_prefix": "SIBL"},
    "CUB":     {"name": "City Union Bank", "ifsc_prefix": "CIUB"},
    "KVB":     {"name": "Karur Vysya Bank", "ifsc_prefix": "KVBL"},
    "DCB":     {"name": "DCB Bank", "ifsc_prefix": "DCBL"},
    "PSB":     {"name": "Punjab & Sind Bank", "ifsc_prefix": "PSIB"},
    "UCO":     {"name": "UCO Bank", "ifsc_prefix": "UCBA"},
    "IOB":     {"name": "Indian Overseas Bank", "ifsc_prefix": "IOBA"},
    "INB":     {"name": "Indian Bank", "ifsc_prefix": "IDIB"},
    "MAH":     {"name": "Bank of Maharashtra", "ifsc_prefix": "MAHB"},
    "CSB":     {"name": "CSB Bank", "ifsc_prefix": "CSBK"},
    "DLB":     {"name": "Dhanlaxmi Bank", "ifsc_prefix": "DLXB"},
    "ESAF":    {"name": "ESAF Small Finance Bank", "ifsc_prefix": "ESAF"},
    "AUB":     {"name": "AU Small Finance Bank", "ifsc_prefix": "AUBL"},
    "UTKRSH":  {"name": "Utkarsh Small Finance Bank", "ifsc_prefix": "UTKS"},
    "SBM":     {"name": "SBM Bank India", "ifsc_prefix": "SBMY"},
    "SHIVALIK":{"name": "Shivalik Small Finance Bank", "ifsc_prefix": "SVSF"},
    "FBL":     {"name": "Federal Bank", "ifsc_prefix": "FDRL"},
    "SC":      {"name": "Standard Chartered", "ifsc_prefix": "SCBL"},
    "CITI":    {"name": "Citi Bank", "ifsc_prefix": "CITI"},
    "HSBC":    {"name": "HSBC", "ifsc_prefix": "HSBC"},
    "DBS":     {"name": "DBS Bank", "ifsc_prefix": "DBSS"},
    "JIO":     {"name": "Jio Payments Bank", "ifsc_prefix": "JIOP"},
    "FINO":    {"name": "Fino Payments Bank", "ifsc_prefix": "FINO"},
    "NSDL":    {"name": "NSDL Payments Bank", "ifsc_prefix": "NSDL"},
    "AIRTEL":  {"name": "Airtel Payments Bank", "ifsc_prefix": "AIRP"},
    "IPPB":    {"name": "India Post Payments Bank", "ifsc_prefix": "IPOS"},
    "CBI":     {"name": "Central Bank of India", "ifsc_prefix": "CBIN"},
    "OBC":     {"name": "Bank of Baroda", "ifsc_prefix": "BARB"},
    "SYNB":    {"name": "Canara Bank", "ifsc_prefix": "CNRB"},
    "ANDB":    {"name": "Union Bank of India", "ifsc_prefix": "UBIN"},
    "CORP":    {"name": "Union Bank of India", "ifsc_prefix": "UBIN"},
    "ALB":     {"name": "Indian Bank", "ifsc_prefix": "IDIB"},
    "DENA":    {"name": "Bank of Baroda", "ifsc_prefix": "BARB"},
    "VJYA":    {"name": "Bank of Baroda", "ifsc_prefix": "BARB"},
    "UNI":     {"name": "Punjab National Bank", "ifsc_prefix": "PUNB"},
    "PMC":     {"name": "PMC Bank", "ifsc_prefix": "PMCB"},
    "DICGC":   {"name": "DICGC", "ifsc_prefix": "DICG"},
    "SVC":     {"name": "Shamrao Vithal Cooperative Bank", "ifsc_prefix": "SVCB"},
    "TJSB":    {"name": "TJSB Sahakari Bank", "ifsc_prefix": "TJSB"},
    "COSMOS":  {"name": "Cosmos Cooperative Bank", "ifsc_prefix": "COSB"},
    "NKGSB":   {"name": "NKGSB Cooperative Bank", "ifsc_prefix": "NKGS"},
    "SAPNA":   {"name": "Apna Sahakari Bank", "ifsc_prefix": "ASBL"},
    "SASF":    {"name": "Saraswat Cooperative Bank", "ifsc_prefix": "SRCB"},
}


app = FastAPI(
    title="raxXftosint",
    description="GSTIN + Fastag + Challan + PAN + PK SIM lookup - single project, multi endpoint",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
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


@app.get("/", include_in_schema=False)
@app.get("/api", include_in_schema=False)
def root() -> dict[str, object]:
    return {
        "service": "raxXftosint",
        "docs": "/api/docs",
        "endpoints": {
            "gstin": "/api/gstin?gstinNum=21AABCF8078M2ZC",
            "search": "/api/search?keyword=flipkart",
            "returns": "/api/returns?gstinNum=21AABCF8078M2ZC&financial_year=2026-27",
            "gstin_to_pan": "/api/gstin-to-pan?gstin=29AAAAA0000A1Z5",
            "fastag": "/api/fastag?vehicle_number=KA01AB1234",
            "challan": "/api/challan?vehicle_number=KA01AB1234&status=PENDING",
            "pan": "/api/pan?pan=AXDPR2606K",
            "pk": "/api/pk?number=03359736848",
            "upi": "/api/upi?upi=test@ybl",
            "phone_to_upi": "/api/phone-to-upi?phone=7065202121",
            "vehicle": "/api/vehicle?rc=DL8CAF5030",
            "health": "/api/health",
        },
    }


@app.get("/home", include_in_schema=False)
@app.get("/api/home", include_in_schema=False)
def home_redirect() -> RedirectResponse:
    return RedirectResponse(url="/api/docs")


@app.get("/health")
@app.get("/api/health")
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


@app.get("/api/pan", tags=["pan"])
def pan_lookup(pan: str = Query(..., min_length=10, max_length=10)) -> dict[str, object]:
    code = pan.strip().upper()
    if not PAN_RE.match(code):
        return {"status": "error", "message": "Invalid PAN format (e.g. AXDPR2606K)"}
    try:
        r = requests.get(
            TURTLE_BASE,
            params={"pan": code, "tokenId": TURTLE_TOKEN_ID},
            headers=TURTLE_HEADERS,
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return {"status": "error", "message": f"Upstream request failed: {e}"}
    if r.status_code == 401:
        return {"status": "error", "message": "Upstream auth expired (401). Token needs refresh."}
    if r.status_code == 429:
        return {"status": "error", "message": "Upstream rate limit (429). Try again later."}
    try:
        body = r.json()
    except ValueError:
        return {"status": "error", "message": f"Upstream non-JSON (HTTP {r.status_code})"}
    if not isinstance(body, dict):
        return {"status": "error", "message": "Unexpected upstream shape"}
    data = body.get("data")
    if not isinstance(data, dict) or not data:
        return {"status": "error", "message": body.get("message") if isinstance(body.get("message"), str) else "No data found for this PAN"}
    return {"status": "success", "pan": code, "data": data}


def _pk_search(number: str) -> dict[str, object]:
    payload = {
        "post_id": "413",
        "form_id": "5e17544",
        "referer_title": "SIM & CNIC Ownership Search",
        "queried_id": "413",
        "form_fields[search]": number,
        "action": "elementor_pro_forms_send_form",
        "referrer": "https://imsidata.com/search/",
    }
    last_err = "upstream failed"
    for attempt in range(3):
        if attempt:
            time.sleep(attempt * 2)
        try:
            r = requests.post(IMSIDATA_URL, data=payload, headers=IMSIDATA_HEADERS, timeout=8)
        except requests.RequestException as e:
            last_err = f"Upstream request failed: {e}"
            continue
        if r.status_code != 200:
            last_err = f"Upstream HTTP {r.status_code}"
            continue
        try:
            body = r.json()
        except ValueError:
            last_err = "Upstream non-JSON response"
            continue
        if not isinstance(body, dict):
            last_err = "Unexpected upstream shape"
            continue
        if body.get("success") is True or "data" in body:
            return {"ok": True, "payload": body}
        last_err = f"Upstream error: {str(body)[:200]}"
    return {"ok": False, "error": last_err}


def _pk_normalize(payload: dict[str, object]) -> list[dict[str, str]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    inner = data.get("data")
    if isinstance(inner, dict):
        data = inner
    results = data.get("results")
    if not isinstance(results, list):
        return []
    out: list[dict[str, str]] = []
    for rec in results:
        if not isinstance(rec, dict):
            continue
        out.append({
            "mobile": str(rec.get("MOBILE") or rec.get("mobile") or "").strip(),
            "name": str(rec.get("NAME") or rec.get("name") or "").strip(),
            "cnic": str(rec.get("CNIC") or rec.get("cnic") or "").strip(),
            "address": str(rec.get("ADDRESS") or rec.get("address") or "").strip(),
            "network": str(rec.get("NETWORK") or rec.get("network") or "").strip(),
        })
    return out


@app.get("/api/pk", tags=["pk"])
def pk_lookup_get(number: str = Query(..., min_length=10, max_length=15)) -> dict[str, object]:
    code = number.strip().replace(" ", "").replace("-", "")
    if not PK_PHONE_RE.match(code):
        return {"status": "error", "message": "Invalid number format (e.g. 03359736848)"}
    res = _pk_search(code)
    if not res.get("ok"):
        return {"status": "error", "message": str(res.get("error", "lookup failed"))}
    payload = res.get("payload")
    results = _pk_normalize(payload) if isinstance(payload, dict) else []
    return {"status": "success", "number": code, "count": len(results), "data": results}


@app.post("/api/pk", tags=["pk"])
def pk_lookup_post(body: dict[str, object]) -> dict[str, object]:
    raw = body.get("number", "")
    code = str(raw).strip().replace(" ", "").replace("-", "")
    if not PK_PHONE_RE.match(code):
        return {"status": "error", "message": "Invalid number format (e.g. 03359736848)"}
    res = _pk_search(code)
    if not res.get("ok"):
        return {"status": "error", "message": str(res.get("error", "lookup failed"))}
    payload = res.get("payload")
    results = _pk_normalize(payload) if isinstance(payload, dict) else []
    return {"status": "success", "number": code, "count": len(results), "data": results}

def _upi_verify(vpa: str) -> tuple[int, str]:
    payload = {"recipientVpa": vpa, "clientContext": {"pageType": "EAP", "useCase": "SEND_MONEY"}}
    h = dict(AMAZON_HEADERS)
    h['Cookie'] = AMAZON_COOKIE + "; " + AMAZON_DEVICE
    r = requests.post(AMAZON_URL, data=json.dumps(payload), headers=h, timeout=12)
    return r.status_code, r.text


def _cash_login_and_session() -> str:
    s = __import__("requests").Session()
    s.headers.update({"User-Agent": CASHFREE_UA, "Accept": "*/*"})
    r = s.post("https://digisevapoint.com/api/auth.php", data={"mobile": DIGI_MOBILE, "password": DIGI_PASS, "action": "login"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"login failed: {data}")
    r2 = s.post("https://digisevapoint.com/views/add_fund.php", data={"amount": DIGI_AMOUNT}, headers={"Referer": "https://digisevapoint.com/views/dashboard.php", "Content-Type": "application/x-www-form-urlencoded", "Origin": "https://digisevapoint.com"}, timeout=20)
    r2.raise_for_status()
    import re as _re
    m = _re.search(r'paymentSessionId:\s*"([^"]+)"', r2.text)
    if not m:
        m = _re.search(r"(session_[A-Za-z0-9_-]{20,})", r2.text)
    if not m:
        raise RuntimeError("payment_session_id not found")
    return m.group(1)

def _cash_get_session(force: bool = False) -> str:
    import time as _time
    with _cash_lock:
        now = _time.time()
        sid = _cash_cache.get("session_id")
        created = float(_cash_cache.get("created_at") or 0)
        ttl = int(_cash_cache.get("ttl") or 240)
        if not force and sid and (now - created) < ttl:
            return str(sid)
        sid2 = _cash_login_and_session()
        _cash_cache["session_id"] = sid2
        _cash_cache["created_at"] = now
        return sid2

def _cash_lookup_vpa(phone: str, session_id: str) -> dict[str, object]:
    import requests as _rq
    r = _rq.get("https://api.cashfree.com/checkout/api/checkouts/instruments/vpas", params={"phone_number": phone}, cookies={"chx_session_id": session_id}, headers={"User-Agent": CASHFREE_UA, "Accept": "application/json", "Referer": "https://api.cashfree.com/checkout/", "Origin": "https://api.cashfree.com"}, timeout=20)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500]}
    return {"http_status": r.status_code, "body": body}

def _enrich_vpa_amazon(vpa: str) -> dict[str, object]:
    code, body = _upi_verify(vpa)
    try:
        data = json.loads(body)
    except Exception:
        data = {}
    if isinstance(data, dict) and data.get("validVpa"):
        handle = vpa.split("@")[-1].lower() if "@" in vpa else ""
        pinfo = PSP.get(handle, {})
        bank_id = str(data.get("bankNameStringId") or "")
        binfo = BANK_INFO.get(bank_id, {})
        bank_name = binfo.get("name") or str(data.get("bankNameDisplayString") or "") or pinfo.get("bank") or "Unknown Bank"
        return {"vpa": vpa, "upi_id": vpa, "name": data.get("recipientBankAccountName"), "bank": bank_name, "app": pinfo.get("app"), "handle": handle, "valid": True, "account_type": data.get("accountType"), "raw": data}
    return {"vpa": vpa, "upi_id": vpa, "error": "invalid_vpa", "raw": data if isinstance(data, dict) else {}}

@app.get("/api/upi", tags=["upi"])
def upi_lookup_get(upi: str = Query(..., min_length=3)) -> dict[str, object]:
    if "@" not in upi:
        return {"status": "error", "message": "Invalid UPI (e.g. test@ybl)"}
    username, handle = upi.lower().split("@", 1)
    code, body = _upi_verify(upi)
    try:
        data = json.loads(body)
    except Exception:
        data = {}
    if not isinstance(data, dict) or not data.get("validVpa"):
        return {"status": "error", "message": data.get("gatewayResponseMessage") or "Invalid or non-existent UPI", "upi_id": upi, "raw": data}
    bank_id = str(data.get("bankNameStringId") or "")
    binfo = BANK_INFO.get(bank_id, {})
    pinfo = PSP.get(handle, {})
    bank_name = binfo.get("name") or str(data.get("bankNameDisplayString") or "") or pinfo.get("bank") or "Unknown Bank"
    result: dict[str, object] = {
        "status": "success",
        "upi_id": upi,
        "username": username,
        "handle": handle,
        "valid": data.get("validVpa"),
        "name": data.get("recipientBankAccountName"),
        "account_type": data.get("accountType"),
        "bank": bank_name,
        "bank_id": bank_id,
        "app": pinfo.get("app"),
        "handle_bank": pinfo.get("bank"),
        "is_merchant": data.get("isMerchant"),
        "raw": data,
    }
    return result

@app.post("/api/upi", tags=["upi"])
def upi_lookup_post(body: dict[str, object]) -> dict[str, object]:
    upi = str(body.get("upi") or body.get("vpa") or "").strip()
    if "@" not in upi:
        return {"status": "error", "message": "Invalid UPI (e.g. test@ybl)"}
    return upi_lookup_get(upi)

def _do_phone_to_vpa(phone: str) -> dict[str, object]:
    import re as _re
    phone = _re.sub(r"\D", "", phone)
    if len(phone) == 12 and phone.startswith("91"):
        phone = phone[2:]
    if len(phone) != 10:
        return {"ok": False, "error": "invalid_phone"}
    try:
        sid = _cash_get_session()
    except Exception as e:
        return {"ok": False, "phone": phone, "error": f"digiseva_login_failed: {e}"}
    res = _cash_lookup_vpa(phone, sid)
    body = res.get("body")
    if res.get("http_status") == 400 or (isinstance(body, dict) and body.get("code") in ("payment_session_id_invalid", "request_failed")):
        try:
            sid = _cash_get_session(force=True)
            res = _cash_lookup_vpa(phone, sid)
            body = res.get("body")
        except Exception:
            pass
    if isinstance(body, dict) and body.get("status") == "SUCCESS":
        vpa = body.get("vpa")
        vpas = body.get("vpas") or ([vpa] if vpa else [])
        vpas = [v for v in vpas if v]
        enriched = [_enrich_vpa_amazon(v) for v in vpas]
        primary = enriched[0] if enriched else {}
        resp: dict[str, object] = {
            "ok": True,
            "phone": phone,
            "vpa": primary.get("vpa") or vpa,
            "holder_name": primary.get("name"),
            "bank": primary.get("bank"),
            "upi_app": primary.get("app"),
            "handle": primary.get("handle"),
            "valid": primary.get("valid"),
            "account_type": primary.get("account_type"),
            "raw_cashfree": body,
            "enriched": enriched,
        }
        if len(vpas) > 1:
            resp["vpa_count"] = len(vpas)
            resp["other_vpas"] = ",".join(vpas[1:])
        return resp
    msg = body.get("message") if isinstance(body, dict) else "lookup_failed"
    return {"ok": False, "phone": phone, "error": msg, "raw": body}

@app.get("/api/phone-to-upi", tags=["phone-upi"])
def phone_to_upi_get(phone: str = Query(..., min_length=10, max_length=15)) -> dict[str, object]:
    return _do_phone_to_vpa(phone)

@app.get("/api/num-to-upi", tags=["phone-upi"], include_in_schema=False)
def num_to_upi_alias(phone: str = Query(..., min_length=10, max_length=15)) -> dict[str, object]:
    return _do_phone_to_vpa(phone)

@app.post("/api/phone-to-upi", tags=["phone-upi"])
def phone_to_upi_post(body: dict[str, object]) -> dict[str, object]:
    phone = str(body.get("phone") or body.get("mobile") or body.get("number") or "").strip()
    if not phone:
        return {"ok": False, "error": "phone required"}
    return _do_phone_to_vpa(phone)

def _jp_headers(referer: str = "https://web.justpolicy.in/car-insurance/?type=rollover") -> dict[str, str]:
    return {
        "Host": "web.justpolicy.in",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": referer,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

def _jp_unwrap(data: object) -> object:
    while isinstance(data, dict) and "data" in data and len(data) == 1:
        data = data["data"]
    if isinstance(data, dict) and "data" in data:
        inner = data["data"]
        extra = {k: v for k, v in data.items() if k != "data"}
        inner = _jp_unwrap(inner)
        if isinstance(inner, dict):
            return {**inner, **extra}
        return inner
    return data

def _jp_clean(data: object) -> object:
    if isinstance(data, dict):
        out: dict[str, object] = {}
        for k, v in data.items():
            if k in ("mmvResponse", "blacklistDetails", "blacklistStatus", "dbResult", "partialData"):
                continue
            if v is not None and v != "" and v != [] and v != "NA":
                out[k] = _jp_clean(v)
        return out
    if isinstance(data, list):
        return [_jp_clean(x) for x in data if x not in ("", None, "NA")]
    return data

def _fetch_vehicle(rc: str) -> dict[str, object]:
    rc = rc.upper().strip()
    try:
        s = __import__("requests").Session()
        r = s.get("https://web.justpolicy.in/car-insurance/?type=rollover", headers=_jp_headers(), timeout=10)
        if r.status_code != 200 or not s.cookies.get("PHPSESSID"):
            return {"error": "session_failed", "status": r.status_code}
        url = f"https://web.justpolicy.in/php-vahaan/service.php/?action=VAHAAN_DETAILS&reg_number={rc}&type=rc"
        r2 = s.get(url, headers=_jp_headers(f"https://web.justpolicy.in/car-insurance/?reg_no={rc}"), timeout=12)
        if r2.status_code != 200:
            return {"error": f"upstream {r2.status_code}", "raw": r2.text[:300]}
        import json as _json
        try:
            parsed = _json.loads(r2.text)
        except Exception:
            return {"error": "non_json", "raw": r2.text[:500]}
        flat = _jp_unwrap(parsed)
        cleaned = _jp_clean(flat)
        if isinstance(cleaned, dict) and cleaned.get("regNo"):
            return {"data": cleaned}
        if isinstance(cleaned, dict) and cleaned:
            return {"data": cleaned}
        return {"error": "no_data", "raw": cleaned}
    except Exception as e:
        return {"error": str(e)[:200]}

@app.get("/api/vehicle", tags=["vehicle"])
def vehicle_lookup(rc: str = Query(..., min_length=4, description="RC number e.g. DL8CAF5030")) -> dict[str, object]:
    rc = rc.upper().strip()
    res = _fetch_vehicle(rc)
    if "error" in res:
        return {"status": "error", "rc": rc, "message": res.get("error"), "raw": res.get("raw")}
    return {"status": "success", "rc": rc, "data": res.get("data")}

@app.get("/api/rc", tags=["vehicle"], include_in_schema=False)
def rc_alias(rc: str = Query(..., min_length=4)) -> dict[str, object]:
    return vehicle_lookup(rc)
