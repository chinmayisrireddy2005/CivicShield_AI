# 🛡️ CivicShield AI

## AI-Powered Emergency Coordination & Response Platform

CivicShield AI is a smart emergency response platform designed to help citizens report **fires, floods, road accidents, medical emergencies, and other public-safety incidents** through text or multilingual voice. The platform identifies the emergency location, analyzes the situation using AI, determines the appropriate severity approach, and helps users identify **nearby real emergency resources** such as hospitals, ambulances, police stations, and fire stations. An interactive map provides location, distance, and route information, while an IoT emergency simulator demonstrates how sensor-based emergency alerts can be generated without a citizen report.

---

## 🚨 Problem Statement

Urban emergencies can become difficult to manage when emergency information is delayed, fragmented, or lacks accurate location and resource information. Citizens may not know how to report an incident quickly or where the nearest emergency facilities are located. Emergency responders also need clear information about the incident, its location, severity, and available nearby resources.

CivicShield AI addresses this gap by bringing emergency reporting, AI-based situation analysis, location intelligence, nearby resource discovery, mapping, incident storage, and IoT-based emergency simulation into a single platform.

---

## 💡 Proposed Solution

CivicShield AI provides a unified platform where users can report emergencies through **text or multilingual voice**. The system identifies the incident location and emergency type, analyzes the situation using AI, and provides relevant information about the incident.

For **flood emergencies**, the system can automatically assess severity based on the reported situation. For other emergencies, the user can select the severity level.

The platform then finds nearby hospitals, ambulances, police stations, and, for fire-related incidents, fire stations. These resources are displayed on an interactive map along with distance and route information. Incidents are stored for tracking, and human verification is included before final resolution.

---

## ✨ Key Features

### 🚨 Emergency Reporting

* Report emergencies using text.
* Report emergencies using voice.
* Support multilingual voice input where supported by the browser.
* Select the emergency type.
* Select severity for applicable emergencies.
* Capture or enter the incident location.

### 🧠 AI Emergency Analysis

* Analyze the emergency description.
* Identify important information from the report.
* Generate a situation summary.
* Provide AI-assisted emergency insights.
* Support automatic flood severity assessment.

### 🌊 Flood Severity Assessment

Flood emergencies use a different severity approach.

Instead of requiring the user to manually select a severity level, the system analyzes the reported flood situation and estimates the severity from the available information.

### 📍 Location Intelligence

* Identify the emergency location.
* Search locations across India.
* Convert place names into geographic coordinates.
* Display the incident location on the map.

### 🏥 Nearby Emergency Resources

The system can identify nearby resources such as:

* 🏥 Hospitals
* 🚑 Ambulances
* 👮 Police stations
* 🔥 Fire stations for fire-related emergencies

The platform focuses on nearby resources relevant to the reported emergency.

### 🗺️ Interactive Emergency Map

The dashboard provides a map showing:

* Emergency location
* Nearby resources
* Resource categories
* Distance information
* Route information
* Different map markers for different locations

### 📡 IoT Emergency Simulation

The application includes an IoT simulation feature to demonstrate emergency detection through simulated sensor signals.

This represents scenarios where an emergency could be detected without a citizen manually submitting a report.

Example simulated signals:

* Fire detection
* Flood detection
* Environmental emergency
* Other sensor-based alerts

### 💾 Incident Management

* Store reported incidents.
* Maintain incident details.
* Track incident status.
* View previous incidents.
* Update incident information.
* Resolve incidents after verification.

### 👤 Human Verification

AI-generated analysis is treated as decision support rather than final authority.

A human can review the incident information before the incident is marked as resolved.

---

## 🔄 Application Workflow

```text
                         🛡️ CIVICSHIELD AI
                                │
                ┌───────────────┴────────────────┐
                │                                │
          🔐 LOGIN / SIGN UP              🚨 QUICK REPORT
                │                                │
                ▼                                ▼
        👤 USER DASHBOARD                 REPORT EMERGENCY
                │                                │
                │                 ┌──────────────┴──────────────┐
                │                 │                             │
                │              📝 TEXT                       🎙️ VOICE
                │                 │                             │
                │                 └──────────────┬──────────────┘
                │                                ▼
                │                           📍 LOCATION
                │                                │
                │                                ▼
                │                     🚨 EMERGENCY TYPE
                │                                │
                │                    ┌───────────┴───────────┐
                │                    │                       │
                │              🌊 FLOOD               OTHER EMERGENCIES
                │                    │                       │
                │              AI calculates            👤 USER SELECTS
                │              severity                 SEVERITY
                │                    │                       │
                │                    └───────────┬───────────┘
                │                                ▼
                │                         INCIDENT CREATED
                │                                │
                └────────────────┬───────────────┘
                                 ▼
                    🚨 EMERGENCY DASHBOARD
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
         INCIDENT            🧠 AI ANALYSIS        🗺️ MAP
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 ▼
                       📍 NEARBY RESOURCES
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
             🏥 Hospital      🚑 Ambulance       👮 Police
                                 │
                          🔥 Fire Station
                           (Fire only)
                                 │
                                 ▼
                      🚦 ROUTE + DISTANCE
                                 │
                                 ▼
                       👤 HUMAN VERIFICATION
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
             🔄 UPDATE PLAN              ✅ RESOLVE
```

---

## 🏗️ System Architecture

```text
                    ┌─────────────────────┐
                    │      Citizen        │
                    └──────────┬──────────┘
                               │
                         Text / Voice
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Flask Web App    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌────────────┐   ┌─────────────┐   ┌─────────────┐
       │ AI Service │   │  Location   │   │  Resource   │
       │  Gemini    │   │   Service   │   │   Service   │
       └────────────┘   └─────────────┘   └─────────────┘
              │                │                │
              │                ▼                ▼
              │         OpenStreetMap      Nearby Places
              │         / Nominatim        / Overpass
              │
              ▼
       Emergency Analysis
              │
              └───────────────┬────────────────┐
                              ▼                ▼
                         SQLite Database     Map / Route
                                             │
                                             ▼
                                       Emergency Dashboard
```

---

## 🛠️ Technology Stack

| Category         | Technology                    |
| ---------------- | ----------------------------- |
| Frontend         | HTML, CSS, JavaScript         |
| Web Framework    | Flask                         |
| Backend          | Python                        |
| AI               | Google Gemini API             |
| Mapping          | OpenStreetMap                 |
| Geocoding        | Nominatim                     |
| Nearby Resources | Overpass API                  |
| Routing          | OSRM                          |
| Interactive Map  | Leaflet                       |
| Voice Reporting  | Web Speech API                |
| Database         | SQLite                        |
| IoT              | Simulated JSON sensor signals |
| Development      | VS Code                       |
| Version Control  | Git & GitHub                  |

---

## 🌐 APIs Used

CivicShield AI is designed to use a limited number of APIs:

### 1. Gemini API

Used for:

* Emergency situation analysis
* Emergency information extraction
* Flood severity assessment
* AI-generated situation summaries

### 2. Nominatim

Used for:

* Converting location names into coordinates
* Searching geographic locations

### 3. Overpass API

Used for:

* Finding nearby hospitals
* Finding nearby police stations
* Finding nearby fire stations
* Finding other relevant map-based resources

### 4. OSRM

Used for:

* Route calculation
* Distance calculation
* Estimated travel route information

### 5. Web Speech API

Used in the browser for:

* Voice input
* Multilingual speech recognition where supported

---

## 📂 Project Structure

```text
CivicShield_AI/
│
├── app.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
│
├── database/
│   └── civicshield.db
│
├── services/
│   ├── ai_service.py
│   ├── geocoding_service.py
│   ├── resource_service.py
│   └── routing_service.py
│
├── data/
│   └── iot_signals.json
│
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── signup.html
│   ├── user_dashboard.html
│   ├── report.html
│   ├── dashboard.html
│   └── incidents.html
│
└── static/
    ├── css/
    │   └── app.css
    │
    └── js/
        ├── app.js
        ├── voice.js
        └── map.js
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/chinmayisrireddy2005/CivicShield_AI.git
```

### 2. Open the project

```bash
cd CivicShield_AI
```

### 3. Create a virtual environment

Windows:

```bash
python -m venv .venv
```

### 4. Activate the virtual environment

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

If using Command Prompt:

```cmd
.venv\Scripts\activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Configuration

Create a `.env` file in the project root.

```env
GEMINI_API_KEY=your_actual_api_key_here
```

### Important Security Rule

**Never upload `.env` to GitHub.**

The `.env.example` file should contain only:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Your `.gitignore` should include:

```gitignore
.env
.venv/
venv/
__pycache__/
*.pyc
*.db
.vscode/
```

---

## ▶️ Run the Application

Activate the virtual environment and run:

```bash
python app.py
```

The Flask application will normally be available at:

```text
http://127.0.0.1:5000
```

Open the address in your browser.

---

## 📊 Main Application Modules

### Home Page

Provides access to:

* Login / Sign Up
* Quick Emergency Report
* Application information
* IoT emergency simulation

### User Dashboard

Provides:

* User information
* Emergency reporting
* Incident overview
* Previous reports

### Emergency Report

Allows users to:

* Select emergency type
* Enter emergency description
* Use voice reporting
* Provide location
* Select severity where applicable
* Submit the incident

### Emergency Dashboard

Displays:

* Incident information
* Location
* AI analysis
* Severity
* Nearby emergency resources
* Interactive map
* Routes
* Distances
* Incident status
* Human verification controls

### Incident History

Stores and displays previously reported emergencies and their status.

---

## 📡 IoT Emergency Simulation

The IoT simulator demonstrates how emergency signals can be generated automatically.

Example:

```text
Sensor Signal
      ↓
IoT Simulator
      ↓
Emergency Detected
      ↓
Incident Created
      ↓
Location Identified
      ↓
AI Analysis
      ↓
Nearby Resources
      ↓
Emergency Dashboard
```

This demonstrates the concept of emergency detection without requiring a citizen to manually submit a report.

---

## 🌟 Innovation

CivicShield AI combines multiple emergency-support capabilities into one platform:

* AI-powered emergency analysis
* Multilingual voice reporting
* Automatic flood severity assessment
* Real nearby emergency resources
* Interactive location and route mapping
* IoT-based emergency simulation
* Incident history
* Human verification
* Location-based emergency information

---

## 🎯 Expected Impact

CivicShield AI aims to reduce delays in emergency reporting, improve awareness of nearby emergency resources, and support better emergency-response decisions by bringing reporting, AI analysis, location intelligence, mapping, and incident tracking into a single platform.

---

## 🚀 Future Enhancements

Potential future improvements include:

* Real-time IoT sensor integration
* Dedicated emergency-service dashboards
* Live ambulance availability
* Push notifications
* SMS emergency alerts
* More advanced multilingual support
* Real-time traffic-aware routing
* Predictive emergency-risk analysis
* Integration with additional public-safety data sources
* Mobile application support

---

## 👥 Project Team

**Team Name:** Neural Nexus

**Project:** CivicShield AI

### Team Members

* Draksharapu Sharon
* Srireddy Chinmayi Maitri
* Boyina Sravya
* Narni Lakshmi Priya

---

## 🏆 Project Category

**Domain:** Artificial Intelligence & Machine Learning

**Theme:** Smart Cities & Public Services

**Project Type:** AI-powered Emergency Response & Coordination Platform

---

## 📌 Disclaimer

CivicShield AI is a **prototype for demonstration and hackathon purposes**. Emergency-resource information, routes, AI analysis, and simulated IoT signals should not be treated as a replacement for official emergency services or professional emergency-response systems.

For real emergencies, users should contact the appropriate official emergency services.
