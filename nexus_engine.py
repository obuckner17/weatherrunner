import os
import re
import json
import time
import shutil
import urllib.request
import boto3
from botocore.config import Config
from openai import OpenAI

def get_inference_client() -> tuple[OpenAI, str]:
    client = OpenAI(
        api_key=os.environ["AKAMAI_API_KEY"],
        base_url=os.environ.get("AKAMAI_BASE_URL", "https://api.akamai-inference.com/v1"),
    )
    model_id = os.environ.get("CHAT_MODEL", "qwen3-8-27b")
    return client, model_id

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["OBJ_ENDPOINT"],
        aws_access_key_id=os.environ["OBJ_ACCESS_KEY"],
        aws_secret_access_key=os.environ["OBJ_SECRET_KEY"],
        config=Config(signature_version="s3v4", request_checksum_calculation="when_required"),
    )

STOPWORDS = {
    "the", "is", "in", "and", "to", "of", "a", "for", "on", "with", "as",
    "by", "at", "an", "be", "this", "that", "from", "or", "are", "was", "it"
}

def preprocess_nlp_text(raw_text: str) -> dict:
    no_html = re.sub(r"<[^>]+>", " ", raw_text)
    no_urls = re.sub(r"https?://\S+|www\.\S+", "", no_html)
    normalized = " ".join(no_urls.split())
    tokens = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", normalized.lower())
    filtered_tokens = [t for t in tokens if t not in STOPWORDS]
    entities = sorted(set(re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", normalized)))

    freq = {}
    for tok in filtered_tokens:
        freq[tok] = freq.get(tok, 0) + 1
    top_keywords = [k for k, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]]
    compression_ratio = round((1 - (len(filtered_tokens) / max(1, len(raw_text.split())))) * 100, 1)

    return {
        "cleaned_text": normalized,
        "token_count": len(filtered_tokens),
        "compression_saved_pct": max(0.0, compression_ratio),
        "top_keywords": top_keywords,
        "ground_truth_entities": entities[:12]
    }

def tool_fetch_nws_weather(lat: float = 47.6101, lon: float = -122.2015) -> str:
    """Fetches live National Weather Service forecast periods and active alerts for coordinates."""
    headers = {"User-Agent": "WeatherRunner-AkamaiBuildathon/1.0 (contact@weatherrunner.local)"}
    try:
        pt_req = urllib.request.Request(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", headers=headers)
        with urllib.request.urlopen(pt_req, timeout=6) as r:
            pt_data = json.loads(r.read().decode("utf-8"))
        forecast_url = pt_data["properties"]["forecast"]
        city = pt_data["properties"]["relativeLocation"]["properties"]["city"]
        state = pt_data["properties"]["relativeLocation"]["properties"]["state"]

        fc_req = urllib.request.Request(forecast_url, headers=headers)
        with urllib.request.urlopen(fc_req, timeout=6) as r:
            fc_data = json.loads(r.read().decode("utf-8"))
        periods = fc_data["properties"]["periods"][:3]

        al_req = urllib.request.Request(f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}", headers=headers)
        with urllib.request.urlopen(al_req, timeout=6) as r:
            al_data = json.loads(r.read().decode("utf-8"))
        alerts = [f["properties"]["headline"] for f in al_data.get("features", [])[:3]]

        return json.dumps({
            "location": f"{city}, {state}",
            "coordinates": [lat, lon],
            "active_alerts": alerts if alerts else ["No active NWS weather alerts"],
            "upcoming_periods": [
                {
                    "name": p["name"],
                    "temp": f"{p['temperature']}{p['temperatureUnit']}",
                    "wind": f"{p['windSpeed']} {p['windDirection']}",
                    "short_forecast": p["shortForecast"]
                } for p in periods
            ]
        })
    except Exception as e:
        return json.dumps({"error": f"NWS telemetry unreachable: {str(e)}", "coordinates": [lat, lon]})

def tool_read_akamai_object(object_key: str) -> str:
    s3 = get_s3_client()
    bucket = os.environ["OBJ_BUCKET"]
    resp = s3.get_object(Bucket=bucket, Key=object_key)
    raw_content = resp["Body"].read().decode("utf-8", errors="replace")
    nlp_summary = preprocess_nlp_text(raw_content)
    return json.dumps({
        "bucket": bucket,
        "key": object_key,
        "nlp_metrics": {
            "token_count": nlp_summary["token_count"],
            "compression_saved_pct": nlp_summary["compression_saved_pct"],
            "top_keywords": nlp_summary["top_keywords"],
            "ground_truth_entities": nlp_summary["ground_truth_entities"]
        },
        "cleaned_content": nlp_summary["cleaned_text"][:3000]
    })

def tool_check_linux_telemetry(path: str = "/") -> str:
    target = path if os.path.exists(path) else "/"
    total, used, free = shutil.disk_usage(target)
    try:
        with open("/proc/loadavg", "r") as f:
            load_1m, load_5m, _ = f.read().split()[:3]
    except Exception:
        load_1m, load_5m = "0.00", "0.00"

    return json.dumps({
        "mount": target,
        "disk_free_gb": round(free / (1024**3), 2),
        "disk_used_pct": round((used / total) * 100, 1),
        "cpu_load_1m": float(load_1m),
        "cpu_load_5m": float(load_5m)
    })

def tool_calibrate_pacing(drag_sec: float, target_sec: float = 6.0) -> str:
    deviation = abs(drag_sec - target_sec)
    score = max(0, min(100, round(100 - (deviation / target_sec) * 100)))
    return json.dumps({
        "measured_sec": round(drag_sec, 2),
        "target_sec": target_sec,
        "kinetic_match_score": score,
        "status": "STABILIZED" if score >= 70 else "SYNC_DRIFT"
    })

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "tool_fetch_nws_weather",
            "description": "Fetch live National Weather Service (NWS) forecast and active severe weather alerts for latitude/longitude coordinates (defaults to Bellevue/Seattle, WA: 47.6101, -122.2015).",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude coordinate"},
                    "lon": {"type": "number", "description": "Longitude coordinate"}
                },
                "required": ["lat", "lon"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_read_akamai_object",
            "description": "Retrieve and NLP-preprocess a field report, route manifest, or log stored in Akamai Object Storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "object_key": {"type": "string", "description": "Filename key inside the Akamai Object Storage bucket"}
                },
                "required": ["object_key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_check_linux_telemetry",
            "description": "Inspect live Linux edge node disk capacity and CPU load averages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Filesystem path such as '/'"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_calibrate_pacing",
            "description": "Compute operator somatosensory focus pacing stability score against a 6.0s target.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drag_sec": {"type": "number", "description": "Measured slider drag duration in seconds"}
                },
                "required": ["drag_sec"]
            }
        }
    }
]

DISPATCH = {
    "tool_fetch_nws_weather": tool_fetch_nws_weather,
    "tool_read_akamai_object": tool_read_akamai_object,
    "tool_check_linux_telemetry": tool_check_linux_telemetry,
    "tool_calibrate_pacing": tool_calibrate_pacing,
}

def run_verified_agent(user_prompt: str, object_key: str = "", pacing_sec: float = 6.0) -> dict:
    t0 = time.perf_counter()
    client, model_id = get_inference_client()

    system_msg = (
        "You are WEATHER RUNNER, an Akamai Cloud Meteorological & Edge Operations Agent. "
        "Always call tool_fetch_nws_weather for live NWS telemetry, inspect any specified Akamai Object Storage file, "
        "check Linux edge host health, and evaluate operator pacing. Ground every claim strictly in tool outputs."
    )

    full_prompt = user_prompt
    if object_key:
        full_prompt += f"\nTarget Akamai Object Storage file key: '{object_key}'."
    full_prompt += f"\nOperator somatosensory pacing duration: {pacing_sec:.2f}s."

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": full_prompt}
    ]

    trace = {"model": model_id, "tool_calls": [], "verification": {}}
    ground_truth_entities = []

    resp = client.chat.completions.create(
        model=model_id,
        messages=messages,
        tools=TOOLS_SCHEMA,
        tool_choice="auto",
        temperature=0.2
    )
    msg = resp.choices[0].message
    messages.append(msg)

    if msg.tool_calls:
        for call in msg.tool_calls:
            fn = call.function.name
            args = json.loads(call.function.arguments or "{}")
            raw_out = DISPATCH[fn](**args) if fn in DISPATCH else '{"error": "unknown tool"}'
            parsed_out = json.loads(raw_out)

            if fn == "tool_read_akamai_object":
                ground_truth_entities.extend(parsed_out.get("nlp_metrics", {}).get("ground_truth_entities", []))
            elif fn == "tool_fetch_nws_weather" and "location" in parsed_out:
                ground_truth_entities.append(parsed_out["location"].split(",")[0])

            trace["tool_calls"].append({"tool": fn, "args": args, "output": parsed_out})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": raw_out})

        final_resp = client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=0.2
        )
        answer = final_resp.choices[0].message.content or ""
    else:
        answer = msg.content or ""

    matched_entities = [e for e in ground_truth_entities if e.lower() in answer.lower()]
    grounding_score = (
        round((len(matched_entities) / len(ground_truth_entities)) * 100, 1)
        if ground_truth_entities else 100.0
    )
    trace["verification"] = {
        "schema_valid": bool(answer.strip()),
        "tools_invoked_count": len(trace["tool_calls"]),
        "ground_truth_entities_checked": ground_truth_entities,
        "entities_verified_in_output": matched_entities,
        "grounding_confidence_pct": grounding_score
    }

    return {
        "answer": answer,
        "latency_ms": round((time.perf_counter() - t0) * 1000),
        "trace": trace
    }
