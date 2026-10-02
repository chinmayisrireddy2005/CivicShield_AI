(function () {
    const languageSelect = document.getElementById('voice-language');
    const startBtn = document.getElementById('start-recording');
    const stopBtn = document.getElementById('stop-recording');
    const statusPill = document.getElementById('voice-status-pill');
    const descriptionBox = document.getElementById('incident-description');
    const fallbackMessage = document.getElementById('voice-fallback');
    const feedback = document.getElementById('voice-feedback');

    if (!languageSelect || !startBtn || !stopBtn || !statusPill || !descriptionBox) return;

    const setStatus = (state, message, detail) => {
        statusPill.className = 'voice-status ' + state;
        statusPill.textContent = message;
        if (feedback && detail) feedback.textContent = detail;
    };
    const showFallback = (message) => {
        if (!fallbackMessage) return;
        fallbackMessage.textContent = message;
        fallbackMessage.classList.remove('hidden');
    };
    const setControls = (busy, recording = false) => {
        startBtn.disabled = busy;
        stopBtn.disabled = !recording;
        languageSelect.disabled = busy;
    };
    const clearRecordingTimer = () => {
        if (recordingTimer !== null) {
            window.clearInterval(recordingTimer);
            recordingTimer = null;
        }
    };

    if (!window.isSecureContext) {
        showFallback('Microphone input requires HTTPS or localhost. Open this app at http://localhost:5000 or use HTTPS.');
        startBtn.disabled = true;
        stopBtn.disabled = true;
        setStatus('error', 'Secure connection required', 'Your browser blocks microphone access on this connection.');
        return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
        showFallback('Audio recording is not supported in this browser. Try the latest Chrome or Edge, or type your report below.');
        startBtn.disabled = true;
        stopBtn.disabled = true;
        setStatus('error', 'Voice input unavailable', 'Your browser does not support audio recording.');
        return;
    }

    let recorder = null;
    let mediaStream = null;
    let chunks = [];
    let baseDescription = '';
    let isStarting = false;
    let recordingTimer = null;
    let recordingStartedAt = 0;
    const maxRecordingDurationMs = 100000;

    const releaseMicrophone = () => {
        if (mediaStream) {
            mediaStream.getTracks().forEach((track) => track.stop());
            mediaStream = null;
        }
    };

    const describeRecordingError = (error) => {
        if (error && error.name === 'NotAllowedError') {
            return 'Microphone access is blocked. Allow it in your browser or operating-system settings and try again.';
        }
        if (error && error.name === 'NotFoundError') {
            return 'No microphone was found. Connect or enable a microphone, then try again.';
        }
        if (error && error.name === 'NotReadableError') {
            return 'The microphone is busy or unavailable. Close other apps using it and try again.';
        }
        return 'Could not start microphone recording. Check microphone access and try again.';
    };

    const transcribeRecording = async (audioBlob) => {
        setStatus('processing', 'Transcribing your voice note', 'The recording is sent to Google Gemini for transcription. This may take a moment.');
        try {
            if (audioBlob.size > 4 * 1024 * 1024) {
                throw new Error('This recording is too large to transcribe. Please record a shorter voice report.');
            }
            const mimeType = (audioBlob.type || 'audio/webm').split(';', 1)[0].toLowerCase();
            const extensionByMimeType = {
                'audio/webm': 'webm',
                'audio/ogg': 'ogg',
                'audio/mp4': 'mp4',
                'audio/wav': 'wav',
                'audio/mpeg': 'mp3'
            };
            const extension = extensionByMimeType[mimeType];
            if (!extension) {
                throw new Error('This browser recorded an unsupported audio format. Please try the latest Chrome or Edge.');
            }
            const formData = new FormData();
            formData.append('audio', audioBlob, `voice-recording.${extension}`);
            formData.append('language', languageSelect.value);
            const requestController = new AbortController();
            const requestTimeout = window.setTimeout(() => requestController.abort(), 210000);
            let response;
            try {
                response = await fetch('/api/transcribe', {
                    method: 'POST',
                    body: formData,
                    signal: requestController.signal
                });
            } catch (error) {
                if (error.name === 'AbortError') {
                    throw new Error('Transcription took too long. Please try again with a shorter recording.');
                }
                throw error;
            } finally {
                window.clearTimeout(requestTimeout);
            }
            const data = await response.json();
            if (!response.ok || !data.ok || !data.transcript) {
                throw new Error(data.message || 'Transcription failed. Please try again or type your report.');
            }

            const spokenText = data.transcript.trim();
            descriptionBox.value = [baseDescription, spokenText].filter(Boolean).join(baseDescription ? ' ' : '');
            setStatus('completed', 'Voice note captured', 'Review or edit your words below, then continue your report.');
            if (fallbackMessage) fallbackMessage.classList.add('hidden');
        } catch (error) {
            const message = error instanceof TypeError
                ? 'Could not reach the transcription service. Check your internet connection and try again.'
                : error.message;
            showFallback(message);
            setStatus('error', 'Transcription failed', message);
        } finally {
            recorder = null;
            chunks = [];
            setControls(false);
        }
    };

    startBtn.addEventListener('click', async () => {
        if (recorder || isStarting) return;
        isStarting = true;
        setControls(true);
        if (fallbackMessage) fallbackMessage.classList.add('hidden');
        setStatus('processing', 'Starting voice capture', 'Allow microphone access if your browser asks.');
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mimeType = typeof MediaRecorder.isTypeSupported === 'function'
                ? ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
                    .find((type) => MediaRecorder.isTypeSupported(type))
                : '';
            recorder = mimeType
                ? new MediaRecorder(mediaStream, { mimeType })
                : new MediaRecorder(mediaStream);
            chunks = [];
            baseDescription = descriptionBox.value.trim();
            recorder.addEventListener('dataavailable', (event) => {
                if (event.data && event.data.size) chunks.push(event.data);
            });
            recorder.addEventListener('error', () => {
                clearRecordingTimer();
                releaseMicrophone();
                recorder = null;
                chunks = [];
                isStarting = false;
                setControls(false);
                const message = 'Audio recording failed. Check the microphone and try again.';
                showFallback(message);
                setStatus('error', 'Recording failed', message);
            }, { once: true });
            recorder.addEventListener('stop', () => {
                clearRecordingTimer();
                releaseMicrophone();
                const audioType = recorder.mimeType || (chunks[0] && chunks[0].type) || 'audio/webm';
                const audioBlob = new Blob(chunks, { type: audioType });
                if (!audioBlob.size) {
                    recorder = null;
                    chunks = [];
                    setControls(false);
                    const message = 'No audio was recorded. Check your microphone and try again.';
                    showFallback(message);
                    setStatus('error', 'Empty recording', message);
                    return;
                }
                transcribeRecording(audioBlob);
            }, { once: true });
            recorder.start();
            isStarting = false;
            setControls(true, true);
            recordingStartedAt = Date.now();
            setStatus('listening', 'Listening now', 'Speak naturally. Press Stop when you have finished. Recording stops automatically after 1 minute 40 seconds.');
            recordingTimer = window.setInterval(() => {
                const elapsedMs = Date.now() - recordingStartedAt;
                if (elapsedMs >= maxRecordingDurationMs) {
                    clearRecordingTimer();
                    if (recorder && recorder.state === 'recording') {
                        stopBtn.disabled = true;
                        setStatus('processing', 'Recording limit reached', 'Transcribing your voice note now.');
                        recorder.stop();
                    }
                    return;
                }
                const elapsedSeconds = Math.floor(elapsedMs / 1000);
                const minutes = Math.floor(elapsedSeconds / 60);
                const seconds = String(elapsedSeconds % 60).padStart(2, '0');
                setStatus(
                    'listening',
                    'Listening now',
                    `Recording ${minutes}:${seconds}. Press Stop when you have finished.`
                );
            }, 1000);
        } catch (error) {
            clearRecordingTimer();
            releaseMicrophone();
            recorder = null;
            isStarting = false;
            setControls(false);
            const message = describeRecordingError(error);
            showFallback(message);
            setStatus('error', 'Could not start recording', message);
        }
    });

    stopBtn.addEventListener('click', () => {
        if (!recorder || recorder.state !== 'recording') return;
        clearRecordingTimer();
        stopBtn.disabled = true;
        setStatus('processing', 'Finishing your voice note', 'Preparing your recording for transcription.');
        recorder.stop();
    });

    languageSelect.addEventListener('change', () => {
        setStatus('ready', 'Language updated', 'Your voice note will be transcribed in ' + languageSelect.options[languageSelect.selectedIndex].text + '.');
    });
})();
