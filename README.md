# CivicShield AI

CivicShield AI is a location-aware emergency decision-support platform built with Flask, SQLite, Gemini AI, Nominatim, Overpass, and OSRM.

## Local setup

1. Create a virtual environment and install dependencies:
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
2. Add your Gemini API key in `.env` (`GEMINI_API_KEY`); Gemini 3.8 Flash is used for incident analysis and Gemini 3.5 Transcribe is used for voice reports.
3. For live Google Places results, enable Places API (New), billing, and a restricted Google Maps Platform key, then set `GOOGLE_MAPS_API_KEY` in `.env`. Google Maps Platform usage may incur charges.
4. Start the app:
   python app.py

## Features
- Text and multilingual voice-based emergency reporting
- Voice reporting records in the browser; pressing Stop or reaching the 1 minute 40 second limit uploads audio to Gemini 3.5 Transcribe and inserts the transcript into the report description (Gemini API key, internet connection, microphone permission, and HTTPS or localhost required). Uploaded audio is deleted from Gemini after transcription.
- India-wide place lookup through Nominatim
- AI-based situation analysis with graceful fallback
- Nearby named hospitals and police stations for all incidents, plus fire stations for fire incidents, using Google Places when configured and OpenStreetMap as a fallback
- Road-route and travel-time access using OSRM
- SQLite-backed incident tracking and history
- Demo IoT simulation flow for emergency scenarios
