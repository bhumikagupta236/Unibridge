# 🌟 UniBridge - Universal Communication & Learning Platform

UniBridge is a full-stack web application designed to break down communication barriers. It provides tools and learning modules for Sign Language, Braille, and Speech, all in one accessible, web-based platform.

This project features real-time communication, computer vision, and user authentication to track learning progress.

## ✨ Core Features

This platform combines multiple communication and learning tools into a single, cohesive interface:

*   **User Authentication & Activity Logging:** Secure registration and login system powered by SQLite and Flask sessions. It tracks user activities across the platform, which can be viewed and cleared from a personalized Dashboard.
*   **Speech ↔ Text:** Uses the browser's Web Speech API for real-time speech recognition (Speech-to-Text) and speech synthesis (Text-to-Speech).
*   **Braille ↔ Text:** A bidirectional translator that converts regular text to Braille and Braille back to text using a robust Python backend dictionary.
*   **Live Sign Recognition:** Uses OpenCV, NumPy, and Socket.IO to stream a live webcam feed to the Python server, analyze hand shapes in real-time using contour detection, and recognize signs (such as A, B, C, V, W).
*   **Learn Sign Language:** An interactive e-learning module that helps users learn the ASL alphabet by dynamically loading ASL images.
*   **Learn Braille:** An e-learning module for learning the Braille alphabet interactively.

## 🛠️ Tech Stack

### Backend
*   **Python 3:** Core programming language.
*   **Flask:** The core web server, routing, and session management.
*   **Flask-SocketIO:** For real-time, bidirectional communication (crucial for streaming webcam frames).
*   **SQLite:** Lightweight database for user accounts and activity logging (`database.py`).
*   **Werkzeug:** Password hashing and verification.
*   **OpenCV-Python / NumPy:** For computer vision tasks, frame processing, contour detection, and shape analysis.

### Frontend
*   **HTML5 / CSS / JavaScript:** Structured, semantic markup and interactivity.
*   **Tailwind CSS:** For styling, accessible components, and responsive design.
*   **Web Speech API:** Browser-native API for speech capabilities.
*   **Socket.IO Client:** Connects to the Python server for real-time video streaming.

## 🚀 How to Run Locally

Follow these steps to get a local copy of the project up and running.

### Prerequisites:
*   Python 3.8+
*   pip (Python package installer)

### 1. Clone the Repository:
```bash
git clone https://github.com/YOUR_USERNAME/unibridge-project.git
cd unibridge-project
```

### 2. Create and Activate a Virtual Environment:
```bash
# Create the environment
python -m venv venv

# Activate it (Windows)
.\venv\Scripts\activate

# Activate it (Mac/Linux)
source venv/bin/activate
```

### 3. Install Requirements:
Install all the required Python libraries:
```bash
pip install -r requirements.txt
```

### 4. Run the Application:
Start the Flask/Socket.IO server:
```bash
python app.py
```

### 5. Open Your Browser:
Navigate to http://127.0.0.1:5000 to interact with the application.

## 📁 Project Structure

```text
unibridge/
├── .gitignore          # Tells Git what to ignore
├── README.md           # Project documentation
├── requirements.txt    # Python library dependencies
├── database.py         # SQLite database definitions and queries
├── uni.py              # Main Flask server and application logic
├── unibridge.db        # SQLite database file (created automatically)
│
├── templates/          # HTML templates
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── speech.html
│   ├── braille.html
│   ├── sign.html
│   ├── learn-sign.html
│   ├── learn-braille.html
│   └── test-svg.html
│
└── static/             # Static assets (CSS, images)
```
