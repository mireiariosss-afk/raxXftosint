import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3

urllib3.disable_warnings()

APEX_BASE = "https://apex.renewbuyinsurance.com"
APEX_MOBILE = "9361046680"
APEX_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "authorization": "null",
    "priority": "u=1, i",
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
}
MOTOR_HEADERS = {
    **APEX_HEADERS,
    "referer": "https://apex.renewbuyinsurance.com/motor/?vehicle=fourWheeler",
}
CV_HEADERS = {
    **APEX_HEADERS,
    "referer": "https://apex.renewbuyinsurance.com/cv/",
}
VAHAN_HOME = "https://vahan.parivahan.gov.in/vahanservice/vahan/ui/statevalidation/homepage.xhtml?statecd=Mzc2MzM2MzAzNjY0MzIzODM3NjIzNjY0MzY2MjM3NDQ0Yw=="
VAHAN_HOME_POST = "https://vahan.parivahan.gov.in/vahanservice/vahan/ui/statevalidation/homepage.xhtml"
VAHAN_LOGIN = "https://vahan.parivahan.gov.in/vahanservice/vahan/ui/usermgmt/login.xhtml"
VAHAN_FITNESS = "https://vahan.parivahan.gov.in/vahanservice/vahan/ui/balanceservice/form_reschedule_fitness.xhtml"
VAHAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
VAHAN_AJAX_HEADERS = {
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded",
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://vahan.parivahan.gov.in",
}


def normalize_rc(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def apex_extract(payload: object) -> object | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("status") is True and isinstance(payload.get("vaahan_details"), dict):
        return payload["vaahan_details"]
    if payload.get("chassis_number") or payload.get("engine_number"):
        return payload
    meta = payload.get("meta_data")
    if isinstance(meta, dict):
        signzy = meta.get("signzy_response")
        if isinstance(signzy, dict) and isinstance(signzy.get("result"), dict):
            return signzy["result"]
    return None


def apex_call(source: str, rc: str):
    if source == "commercial":
        url = f"{APEX_BASE}/cv/api/v1/vaahan/registration_number/"
        params = {"regn_no": rc}
        headers = CV_HEADERS
    else:
        url = f"{APEX_BASE}/api/v1/vaahan/registration_number/"
        params = {
            "regn_no": rc,
            "partner_code": "",
            "mobile_no": APEX_MOBILE,
            "source": "apex",
            "originData": "false",
        }
        headers = MOTOR_HEADERS
    try:
        response = requests.get(url, params=params, headers=headers, timeout=8)
        try:
            payload = response.json()
        except ValueError:
            payload = response.text[:300]
        return source, response.status_code, payload
    except requests.RequestException as exc:
        return source, 0, {"error": str(exc)[:200]}


def apex_lookup(rc: str) -> dict[str, object]:
    normalized = normalize_rc(rc)
    if len(normalized) < 6:
        return {"status": "error", "message": "Invalid RC number"}
    results: dict[str, tuple[int, object]] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(apex_call, source, normalized) for source in ("motor", "commercial")]
        for future in as_completed(futures):
            source, status, payload = future.result()
            results[source] = (status, payload)
    for source in ("motor", "commercial"):
        status, payload = results.get(source, (0, None))
        data = apex_extract(payload)
        if status == 200 and isinstance(data, dict):
            return {
                "status": "success",
                "rc": normalized,
                "source": source,
                "vehicle_type": (
                    "commercial" if data.get("is_commercial") is True else
                    "bike" if data.get("is_two_wheeler") is True else
                    "car" if data.get("is_four_wheeler") is True else "motor"
                ),
                "data": data,
                "attempts": {key: value[0] for key, value in results.items()},
            }
    return {
        "status": "error",
        "rc": normalized,
        "message": "No record found in Apex lookup",
        "attempts": {key: value[0] for key, value in results.items()},
    }


def vahan_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(VAHAN_HEADERS)
    session.verify = False
    return session


def vahan_request(session: requests.Session, url: str, data=None, headers=None, referer=None):
    merged = dict(headers or {})
    if referer:
        merged["Referer"] = referer
    if data is None:
        response = session.get(url, headers=merged, timeout=8)
    else:
        response = session.post(url, data=data, headers=merged, timeout=8)
    return response.text


def view_state(html: str) -> str | None:
    match = re.search(r'<input[^>]*name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    return match.group(1) if match else None


def ajax_view_state(html: str) -> str | None:
    match = re.search(r'<update id="j_id1:javax\.faces\.ViewState:0"><!\[CDATA\[(.*?)\]\]></update>', html)
    return match.group(1) if match else None


def vahan_mobile(reg_no: str, chassis_last5: str) -> dict[str, object]:
    session = vahan_session()
    html = vahan_request(session, VAHAN_HOME)
    state = view_state(html)
    if not state:
        return {"success": False, "error": "Vahan homepage ViewState missing"}
    checkbox = re.search(r'<div[^>]*id="(j_idt\d+)"[^>]*class="[^"]*ui-chkbox', html)
    checkbox_id = checkbox.group(1) if checkbox else "j_idt193"
    ajax = {**VAHAN_AJAX_HEADERS, "Referer": VAHAN_HOME}
    base = {
        "javax.faces.partial.ajax": "true",
        "homepageformid": "homepageformid",
        "javax.faces.ViewState": state,
    }
    html = vahan_request(session, VAHAN_HOME_POST, {**base, "javax.faces.source": "fit_c_office_to", "javax.faces.partial.execute": "fit_c_office_to", "javax.faces.behavior.event": "change", "javax.faces.partial.event": "change", "fit_c_office_to_input": "1"}, ajax)
    state = ajax_view_state(html) or state
    html = vahan_request(session, VAHAN_HOME_POST, {**base, "javax.faces.ViewState": state, "javax.faces.source": checkbox_id, "javax.faces.partial.execute": checkbox_id, "javax.faces.partial.render": "proccedHomeButtonId", "javax.faces.behavior.event": "change", f"{checkbox_id}_input": "on"}, ajax)
    state = ajax_view_state(html) or state
    html = vahan_request(session, VAHAN_HOME_POST, {**base, "javax.faces.ViewState": state, "javax.faces.source": "proccedHomeButtonId", "javax.faces.partial.execute": "@all", "proccedHomeButtonId": "proccedHomeButtonId", f"{checkbox_id}_input": "on"}, ajax)
    state = ajax_view_state(html) or state
    dialog = re.search(r'id="(j_idt\d+)"[^>]*class="[^"]*ui-button', html)
    dialog_id = dialog.group(1) if dialog else "j_idt536"
    html = vahan_request(session, VAHAN_HOME_POST, {**base, "javax.faces.ViewState": state, "javax.faces.source": dialog_id, "javax.faces.partial.execute": "@all", dialog_id: dialog_id, f"{checkbox_id}_input": "on"}, ajax)
    state = ajax_view_state(html) or state
    html = vahan_request(session, VAHAN_LOGIN + "?faces-redirect=true", referer=VAHAN_HOME)
    state = view_state(html)
    if not state:
        return {"success": False, "error": "Vahan login ViewState missing"}
    submit = re.search(r'id="(j_idt\d+)"[^>]*name="\1"[^>]*type="submit"', html)
    submit_id = submit.group(1) if submit else "j_idt506"
    vahan_request(session, VAHAN_LOGIN, {"loginForm": "loginForm", submit_id: submit_id, "javax.faces.ViewState": state, "fitbalcTest": "fitbalcTest", "pur_cd": "86"}, {"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://vahan.parivahan.gov.in"}, VAHAN_LOGIN + "?faces-redirect=true")
    html = vahan_request(session, VAHAN_FITNESS, referer=VAHAN_LOGIN + "?faces-redirect=true")
    state = view_state(html)
    if not state:
        return {"success": False, "error": "Vahan fitness ViewState missing"}
    html = vahan_request(session, VAHAN_FITNESS, {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "balanceFeesFine:validate_dtls",
        "javax.faces.partial.execute": "@all",
        "javax.faces.partial.render": "balanceFeesFine:auth_panel",
        "balanceFeesFine:validate_dtls": "balanceFeesFine:validate_dtls",
        "balanceFeesFine": "balanceFeesFine",
        "balanceFeesFine:tf_reg_no": reg_no,
        "balanceFeesFine:tf_chasis_no": chassis_last5,
        "javax.faces.ViewState": state,
    }, {**ajax, "Referer": VAHAN_FITNESS})
    patterns = [
        r'id="balanceFeesFine:tf_mobile"[^>]*value="(\d{10})"',
        r'value="(\d{10})"[^>]*id="balanceFeesFine:tf_mobile"',
        r'balanceFeesFine:tf_mobile[^>]*value="(\d{10})"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match and re.match(r"^[6-9]", match.group(1)):
            return {"success": True, "mobile_number": match.group(1)}
    numbers = re.findall(r"\b[6-9]\d{9}\b", html)
    if numbers:
        return {"success": True, "mobile_number": numbers[0]}
    return {"success": False, "error": "Mobile number not found in Vahan response"}


def lookup(reg_no: str) -> dict[str, object]:
    started = time.time()
    apex = apex_lookup(reg_no)
    output: dict[str, object] = {
        "status": apex.get("status", "error"),
        "rc": apex.get("rc", normalize_rc(reg_no)),
        "vehicle_type": apex.get("vehicle_type"),
        "chassis_number": None,
        "engine_number": None,
        "mobile_number": None,
        "source": apex.get("source"),
    }
    if apex.get("status") != "success" or not isinstance(apex.get("data"), dict):
        output["error"] = apex.get("message", "Apex lookup failed")
        output["response_time_seconds"] = round(time.time() - started, 2)
        return output
    data = apex["data"]
    if not isinstance(data, dict):
        output["error"] = "Apex returned invalid data"
        output["response_time_seconds"] = round(time.time() - started, 2)
        return output
    chassis = str(data.get("chassis_number") or "").replace(" ", "")
    engine = str(data.get("engine_number") or "").strip()
    output["chassis_number"] = chassis
    output["engine_number"] = engine
    if not chassis:
        output["error"] = "Apex returned no chassis number"
        output["response_time_seconds"] = round(time.time() - started, 2)
        return output
    try:
        rc_value = str(apex.get("rc") or normalize_rc(reg_no))
        mobile = vahan_mobile(rc_value, chassis[-5:])
        output["mobile_number"] = mobile.get("mobile_number")
        if not mobile.get("success"):
            output["error"] = mobile.get("error")
    except requests.RequestException as exc:
        output["error"] = f"Vahan request failed: {str(exc)[:200]}"
    output["response_time_seconds"] = round(time.time() - started, 2)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reg_no", nargs="?", help="vehicle registration number")
    args = parser.parse_args()
    reg_no = args.reg_no or input("Enter vehicle number: ").strip()
    result = lookup(reg_no)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("mobile_number") else 1


if __name__ == "__main__":
    sys.exit(main())
