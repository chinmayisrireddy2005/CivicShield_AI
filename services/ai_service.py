import base64
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
GEMINI_FILES_UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_FILES_URL = "https://generativelanguage.googleapis.com/v1beta/files"
GEMINI_TRANSCRIPTION_MODEL = "gemini-3.5-transcribe"


class VoiceTranscriptionError(Exception):
    pass


def _extract_text(response_json: Dict[str, Any]) -> str:
    candidates = response_json.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts") or []
    collected = []
    for part in parts:
        if isinstance(part, dict):
            collected.append(part.get("text", ""))
    return "\n".join(item for item in collected if item).strip()


def _extract_interaction_text(response_json: Dict[str, Any]) -> str:
    output_text = response_json.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    text_parts = []
    for output in response_json.get("outputs") or []:
        if isinstance(output, dict) and isinstance(output.get("text"), str):
            text_parts.append(output["text"])
        elif isinstance(output, dict):
            for part in output.get("content") or []:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
    return "\n".join(part for part in text_parts if part).strip()


def _gemini_http_error(status_code: Optional[int], operation: str) -> VoiceTranscriptionError:
    if status_code in {401, 403}:
        message = "Gemini rejected the API key. Check GEMINI_API_KEY and its API restrictions."
    elif status_code == 404:
        message = "Gemini's transcription model or API endpoint is unavailable. Check model access and the API endpoint."
    elif status_code == 429:
        message = "Gemini's request quota or rate limit was reached. Try again later."
    elif status_code == 400:
        message = "Gemini rejected the audio request. Try a shorter recording or a supported browser audio format."
    else:
        message = f"Gemini {operation} failed (HTTP {status_code or 'unknown'}). Try again later."
    return VoiceTranscriptionError(message)


def _post_gemini(url: str, headers: Dict[str, str], operation: str, **kwargs: Any) -> requests.Response:
    try:
        response = requests.post(url, headers=headers, **kwargs)
        response.raise_for_status()
        return response
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        raise _gemini_http_error(status_code, operation) from exc
    except requests.RequestException as exc:
        raise VoiceTranscriptionError(
            f"Could not connect to Gemini to {operation}. Check the app server's internet connection and try again."
        ) from exc


def _transcribe_inline_audio(
    audio_data: bytes,
    mime_type: str,
    language: str,
    headers: Dict[str, str],
) -> str:
    prompt = (
        f"Transcribe this recording in {language}. Return only the words spoken, "
        "preserving the original wording. Do not translate, summarize, or add commentary."
    )
    response = _post_gemini(
        GEMINI_API_URL,
        {**headers, "Content-Type": "application/json"},
        "transcribe the recording",
        json={
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(audio_data).decode("ascii"),
                        }
                    },
                ]
            }],
            "generationConfig": {"temperature": 0},
        },
        timeout=(5, 90),
    )
    payload = response.json()
    if not isinstance(payload, dict):
        raise VoiceTranscriptionError("Gemini returned an invalid transcription response. Please try again.")
    return _extract_text(payload)


def transcribe_audio(audio_data: bytes, mime_type: str, language: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key.lower() in {"", "your_key_here", "your_gemini_api_key_here"}:
        raise VoiceTranscriptionError(
            "Voice transcription is not configured. Set GEMINI_API_KEY in the app environment."
        )
    if not audio_data:
        raise VoiceTranscriptionError("The recording was empty. Please record your report again.")

    headers = {"x-goog-api-key": api_key}
    uploaded_file_name = ""
    try:
        try:
            upload_start = _post_gemini(
                GEMINI_FILES_UPLOAD_URL,
                {
                    **headers,
                    "X-Goog-Upload-Protocol": "resumable",
                    "X-Goog-Upload-Command": "start",
                    "X-Goog-Upload-Header-Content-Length": str(len(audio_data)),
                    "X-Goog-Upload-Header-Content-Type": mime_type,
                    "Content-Type": "application/json",
                },
                "start the audio upload",
                json={"file": {"display_name": "civicshield-voice-report"}},
                timeout=(5, 30),
            )
        except VoiceTranscriptionError as exc:
            if not isinstance(exc.__cause__, requests.RequestException):
                raise
            transcript = _transcribe_inline_audio(audio_data, mime_type, language, headers)
        else:
            upload_url = upload_start.headers.get("x-goog-upload-url")
            if not upload_url:
                raise VoiceTranscriptionError("Gemini did not provide an audio upload session. Please try again.")

            upload_response = _post_gemini(
                upload_url,
                {
                    "Content-Length": str(len(audio_data)),
                    "X-Goog-Upload-Offset": "0",
                    "X-Goog-Upload-Command": "upload, finalize",
                },
                "upload the voice recording",
                data=audio_data,
                timeout=(5, 60),
            )
            upload_payload = upload_response.json()
            if not isinstance(upload_payload, dict):
                raise VoiceTranscriptionError("Gemini returned invalid audio upload details. Please try again.")
            file_data = upload_payload.get("file", upload_payload)
            if not isinstance(file_data, dict):
                raise VoiceTranscriptionError("Gemini returned invalid audio upload details. Please try again.")
            file_uri = file_data.get("uri")
            uploaded_file_name = file_data.get("name") or ""
            if not isinstance(file_uri, str) or not file_uri:
                raise VoiceTranscriptionError("Gemini did not return an audio file reference. Please try again.")
            if not isinstance(uploaded_file_name, str):
                raise VoiceTranscriptionError("Gemini returned an invalid audio file name. Please try again.")

            prompt = (
                f"Transcribe this recording in {language}. Return only the words spoken, "
                "preserving the original wording. Do not translate, summarize, or add commentary."
            )
            response = _post_gemini(
                GEMINI_INTERACTIONS_URL,
                {**headers, "Content-Type": "application/json"},
                "transcribe the recording",
                json={
                    "model": GEMINI_TRANSCRIPTION_MODEL,
                    "input": [
                        {"type": "text", "text": prompt},
                        {"type": "audio", "uri": file_uri, "mime_type": mime_type},
                    ],
                },
                timeout=(5, 90),
            )
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Gemini returned an invalid transcription response.")
            transcript = _extract_interaction_text(payload)
    except requests.RequestException as exc:
        raise VoiceTranscriptionError(
            "Could not connect to Gemini for transcription. Check the app server's internet connection and try again."
        ) from exc
    except ValueError as exc:
        raise VoiceTranscriptionError(
            "Gemini returned an invalid transcription response. Please try again."
        ) from exc
    finally:
        if uploaded_file_name:
            try:
                delete_response = requests.delete(
                    f"{GEMINI_FILES_URL}/{quote(uploaded_file_name, safe='/')}",
                    headers=headers,
                    timeout=(5, 15),
                )
                delete_response.raise_for_status()
            except requests.RequestException as exc:
                logging.getLogger(__name__).warning(
                    "Could not delete uploaded Gemini voice file (%s).",
                    type(exc).__name__,
                )
    transcript = transcript.strip()
    if not transcript:
        raise VoiceTranscriptionError("No speech was recognized. Please try again or type your report.")
    return transcript


def _parse_response(text: str) -> Dict[str, Any]:
    normalized = text.strip()
    if not normalized:
        return {
            "risk_level": "Moderate",
            "situation_summary": "AI analysis unavailable.",
            "likely_support_needed": ["Emergency services", "Medical support"],
            "immediate_considerations": ["Verify the reported conditions before dispatching support."],
            "reasoning_summary": "The analysis could not be generated.",
            "flood_severity": "Moderate",
        }

    result = {
        "risk_level": "Moderate",
        "situation_summary": "AI analysis available.",
        "likely_support_needed": ["Emergency services"],
        "immediate_considerations": ["Verify the report with local responders."],
        "reasoning_summary": "The model provided a general assessment.",
        "flood_severity": "Moderate",
    }

    for label, key in (
        ("RISK:", "risk_level"),
        ("SITUATION:", "situation_summary"),
        ("LIKELY SUPPORT:", "likely_support_needed"),
        ("IMMEDIATE CONSIDERATION:", "immediate_considerations"),
        ("REASONING:", "reasoning_summary"),
        ("FLOOD SEVERITY:", "flood_severity"),
    ):
        index = normalized.upper().find(label)
        if index == -1:
            continue
        tail = normalized[index + len(label):].strip()
        if not tail:
            continue
        if key in {"likely_support_needed", "immediate_considerations"}:
            items = [item.strip() for item in tail.split(";") if item.strip()]
            if items:
                result[key] = items
        else:
            result[key] = tail.splitlines()[0].strip()

    if not isinstance(result["likely_support_needed"], list):
        result["likely_support_needed"] = [str(result["likely_support_needed"])]
    if not isinstance(result["immediate_considerations"], list):
        result["immediate_considerations"] = [str(result["immediate_considerations"]) ]

    if result["risk_level"].upper() in {"LOW", "MODERATE", "HIGH", "CRITICAL"}:
        result["risk_level"] = result["risk_level"].title()
    else:
        result["risk_level"] = "Moderate"

    if result["flood_severity"].upper() in {"LOW", "MODERATE", "HIGH", "CRITICAL"}:
        result["flood_severity"] = result["flood_severity"].title()
    else:
        result["flood_severity"] = "Moderate"

    return result


def analyze_incident(
    emergency_type: str,
    description: str,
    location: str,
    severity: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    flood_details: Optional[str] = None,
) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_key_here":
        return {
            "risk_level": "Moderate",
            "situation_summary": "AI analysis temporarily unavailable.",
            "likely_support_needed": ["Medical support", "Emergency services"],
            "immediate_considerations": ["Human verification is required before dispatching support."],
            "reasoning_summary": "Gemini API key not configured.",
            "flood_severity": "Moderate",
            "error": "Gemini API key missing",
        }

    prompt = (
        "You are a safety analyst for CivicShield AI. Provide only a short structured response.\n"
        f"INCIDENT: {emergency_type}\n"
        f"DESCRIPTION: {description}\n"
        f"LOCATION: {location}\n"
        f"CITY: {city or 'Unknown'}\n"
        f"STATE: {state or 'Unknown'}\n"
        f"SEVERITY: {severity or 'Not provided'}\n"
    )
    if emergency_type.upper() == "FLOOD" and flood_details:
        prompt += f"FLOOD DETAILS: {flood_details}\n"
    prompt += (
        "Return structured information with these labels exactly in order: "
        "RISK: <LOW|MODERATE|HIGH|CRITICAL>, "
        "SITUATION: <short summary>, "
        "LIKELY SUPPORT: <support1; support2; support3>, "
        "IMMEDIATE CONSIDERATION: <item1; item2>, "
        "REASONING: <short reason>, "
        "FLOOD SEVERITY: <LOW|MODERATE|HIGH|CRITICAL>"
    )

    try:
        response = requests.post(
            GEMINI_API_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2},
            },
            timeout=20,
        )
        if response.status_code in {429, 500, 503}:
            raise requests.HTTPError(f"Gemini API returned {response.status_code}")
        response.raise_for_status()
        payload = response.json()
        text = _extract_text(payload)
        parsed = _parse_response(text)
        parsed["status"] = "ok"
        return parsed
    except Exception as exc:
        return {
            "risk_level": "Moderate",
            "situation_summary": "AI analysis temporarily unavailable.",
            "likely_support_needed": ["Emergency services", "Medical support"],
            "immediate_considerations": ["Human verification required before action."],
            "reasoning_summary": "Gemini request failed: " + str(exc),
            "flood_severity": "Moderate",
            "error": str(exc),
        }
