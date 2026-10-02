document.addEventListener('DOMContentLoaded', function () {
    const steps = Array.from(document.querySelectorAll('.step-panel'));
    const stepBadges = Array.from(document.querySelectorAll('.wizard-step'));
    const nextBtn = document.getElementById('next-step');
    const prevBtn = document.getElementById('prev-step');
    const submitBtn = document.getElementById('submit-report');
    const floodNote = document.getElementById('flood-severity-note');
    const reviewSummary = document.getElementById('review-summary');
    const emergencyTypeInputs = document.querySelectorAll('input[name="emergency_type"]');
    const locationSearchInput = document.getElementById('location-search');
    const searchLocationBtn = document.getElementById('search-location-btn');
    const currentLocationBtn = document.getElementById('use-current-location');
    const locationSuggestions = document.getElementById('location-suggestions');
    const latitudeInput = document.getElementById('latitude-input');
    const longitudeInput = document.getElementById('longitude-input');
    const addressInput = document.getElementById('address-input');
    const cityInput = document.getElementById('city-input');
    const stateInput = document.getElementById('state-input');
    const incidentDescription = document.getElementById('incident-description');

    if (steps.length && nextBtn) {
        let currentStep = 0;
        const showStep = (index) => {
            currentStep = Math.max(0, Math.min(index, steps.length - 1));
            steps.forEach((step, stepIndex) => step.classList.toggle('active', stepIndex === currentStep));
            stepBadges.forEach((badge, badgeIndex) => badge.classList.toggle('active', badgeIndex === currentStep));
            nextBtn.classList.toggle('hidden', currentStep === steps.length - 1);
            submitBtn.classList.toggle('hidden', currentStep !== steps.length - 1);
            prevBtn.style.visibility = currentStep === 0 ? 'hidden' : 'visible';
            if (currentStep === steps.length - 1) {
                const selectedType = document.querySelector('input[name="emergency_type"]:checked')?.value || 'OTHER_EMERGENCY';
                const selectedSeverity = document.querySelector('input[name="severity"]:checked')?.value || 'Moderate';
                const selectedPhoto = document.getElementById('incident-photo')?.files[0];
                const summaryItems = [
                    ['Emergency Type', selectedType],
                    ['Description', incidentDescription.value || 'Not provided'],
                    ['Photo', selectedPhoto ? selectedPhoto.name : 'None attached'],
                    ['Location', addressInput.value || 'Not provided'],
                    ['City', cityInput.value || 'Unknown'],
                    ['State', stateInput.value || 'Unknown'],
                    ['Severity', selectedSeverity]
                ];
                reviewSummary.replaceChildren(...summaryItems.map(([label, value]) => {
                    const row = document.createElement('p');
                    const title = document.createElement('strong');
                    title.textContent = `${label}: `;
                    row.append(title, document.createTextNode(value));
                    return row;
                }));
            }
        };

        nextBtn.addEventListener('click', () => showStep(currentStep + 1));
        prevBtn.addEventListener('click', () => showStep(currentStep - 1));
        showStep(0);
    }

    const updateSeverityUI = () => {
        const selected = document.querySelector('input[name="emergency_type"]:checked')?.value || 'FIRE';
        const severityInputs = document.querySelectorAll('input[name="severity"]');
        const showFlood = selected === 'FLOOD';

        if (floodNote) {
            if (showFlood) {
                floodNote.classList.remove('hidden');
            } else {
                floodNote.classList.add('hidden');
            }
        }

        if (!severityInputs.length) return;

        if (showFlood) {
            severityInputs.forEach((input) => {
                input.checked = false;
                input.disabled = true;
            });
            const softInput = document.querySelector('input[name="severity"][value="Moderate"]');
            if (softInput) softInput.checked = true;
        } else {
            severityInputs.forEach((input) => {
                input.disabled = false;
            });
        }
    };

    if (emergencyTypeInputs.length) {
        emergencyTypeInputs.forEach((input) => input.addEventListener('change', updateSeverityUI));
        updateSeverityUI();
    }

    const renderLocationSuggestions = (resultList = []) => {
        if (!locationSuggestions) return;
        locationSuggestions.innerHTML = '';

        if (!resultList.length) {
            locationSuggestions.innerHTML = '<div class="location-empty">No matching places found. Try a more specific landmark or city name.</div>';
            return;
        }

        const suggestions = resultList.slice(0, 4).map((result) => {
            const suggestion = document.createElement('button');
            suggestion.type = 'button';
            suggestion.className = 'location-result';
            suggestion.innerHTML = `
                <strong>${result.place || result.city || 'Place'}</strong>
                <span>${result.city || ''}${result.city && result.state ? ', ' : ''}${result.state || ''}</span>
            `;
            suggestion.addEventListener('click', () => {
                setLocation({ ok: true, ...result });
                if (locationSuggestions) locationSuggestions.innerHTML = '';
            });
            return suggestion;
        });

        suggestions.forEach((card) => locationSuggestions.appendChild(card));
    };

    const setLocation = (result) => {
        if (!result || !result.ok) {
            alert(result?.message || 'Unable to locate this place. Please try another location.');
            return;
        }
        latitudeInput.value = result.latitude;
        longitudeInput.value = result.longitude;
        addressInput.value = result.address || '';
        cityInput.value = result.city || '';
        stateInput.value = result.state || '';
        const mapTarget = document.getElementById('location-preview-map');
        if (mapTarget) {
            mapTarget.innerHTML = '';
            const map = L.map(mapTarget).setView([result.latitude, result.longitude], 12);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 18,
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);
            L.marker([result.latitude, result.longitude]).addTo(map);
            map.invalidateSize();
        }
    };

    const fetchGeocode = async (query, shouldShowSuggestions = true) => {
        const searchValue = (query || '').trim();
        if (!searchValue) return;

        const response = await fetch(`${window.CIVICSHIELD?.reportUrl || '/api/geocode'}?q=${encodeURIComponent(searchValue)}`);
        const data = await response.json();
        if (!data.ok) {
            alert(data.message || 'Unable to locate this place. Please try another location.');
            return;
        }

        const resultList = Array.isArray(data.results) && data.results.length ? data.results : [data];
        if (shouldShowSuggestions) {
            renderLocationSuggestions(resultList);
        }
        setLocation(data);
    };

    if (searchLocationBtn && locationSearchInput) {
        searchLocationBtn.addEventListener('click', () => {
            const searchValue = locationSearchInput.value.trim();
            if (!searchValue) {
                alert('Please enter a location to search.');
                return;
            }
            fetchGeocode(searchValue, true);
        });

        locationSearchInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                const searchValue = locationSearchInput.value.trim();
                if (searchValue) fetchGeocode(searchValue, true);
            }
        });

        locationSearchInput.addEventListener('input', () => {
            const searchValue = locationSearchInput.value.trim();
            if (searchValue.length < 3) {
                if (locationSuggestions) locationSuggestions.innerHTML = '';
                return;
            }
            fetchGeocode(searchValue, true);
        });
    }

    if (currentLocationBtn) {
        currentLocationBtn.addEventListener('click', () => {
            if (!navigator.geolocation) {
                alert('Geolocation is not supported by this browser.');
                return;
            }
            navigator.geolocation.getCurrentPosition(async (position) => {
                const response = await fetch(`/api/geocode?lat=${position.coords.latitude}&lon=${position.coords.longitude}`);
                const data = await response.json();
                setLocation(data);
            }, () => {
                alert('Unable to access your current location. Please use a search instead.');
            });
        });
    }

    const photoInput = document.getElementById('incident-photo');
    const photoPreview = document.getElementById('incident-photo-preview');
    const photoStatus = document.getElementById('incident-photo-status');
    const cameraPanel = document.getElementById('camera-panel');
    const cameraPreview = document.getElementById('camera-preview');
    const openCameraBtn = document.getElementById('open-camera');
    const capturePhotoBtn = document.getElementById('capture-photo');
    const closeCameraBtn = document.getElementById('close-camera');
    let cameraStream = null;
    let photoPreviewUrl = null;

    const closeCamera = () => {
        if (cameraStream) {
            cameraStream.getTracks().forEach((track) => track.stop());
            cameraStream = null;
        }
        if (cameraPreview) cameraPreview.srcObject = null;
        if (cameraPanel) cameraPanel.classList.add('hidden');
    };

    const showPhoto = (file) => {
        if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
        photoPreviewUrl = URL.createObjectURL(file);
        photoPreview.src = photoPreviewUrl;
        photoPreview.classList.remove('hidden');
        photoStatus.textContent = `${file.name} selected (${(file.size / (1024 * 1024)).toFixed(2)} MB).`;
    };

    if (photoInput && photoPreview && photoStatus) {
        const photoSelectLabel = document.querySelector('label[for="incident-photo"]');
        if (photoSelectLabel) {
            photoSelectLabel.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    photoInput.click();
                }
            });
        }
        photoInput.addEventListener('change', () => {
            const file = photoInput.files[0];
            if (!file) return;
            if (file.size > 8 * 1024 * 1024) {
                photoInput.value = '';
                photoPreview.classList.add('hidden');
                photoStatus.textContent = 'The photo must be 8 MB or smaller.';
                return;
            }
            showPhoto(file);
        });
    }

    if (openCameraBtn && cameraPanel && cameraPreview) {
        openCameraBtn.addEventListener('click', async () => {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                photoStatus.textContent = 'Camera access requires a supported browser over HTTPS or localhost. Choose an existing photo instead.';
                return;
            }
            try {
                cameraStream = await navigator.mediaDevices.getUserMedia({
                    audio: false,
                    video: { facingMode: { ideal: 'environment' } }
                });
                cameraPreview.srcObject = cameraStream;
                cameraPanel.classList.remove('hidden');
                photoStatus.textContent = 'Camera ready. Take a photo when the scene is clear.';
                await cameraPreview.play();
            } catch (error) {
                closeCamera();
                photoStatus.textContent = error.name === 'NotAllowedError'
                    ? 'Camera permission was denied. Allow camera access or choose an existing photo.'
                    : 'Could not open the camera. Choose an existing photo instead.';
            }
        });
    }

    if (capturePhotoBtn && cameraPreview && photoInput) {
        capturePhotoBtn.addEventListener('click', () => {
            if (!cameraPreview.videoWidth || !cameraPreview.videoHeight) {
                photoStatus.textContent = 'The camera is not ready yet. Please wait and try again.';
                return;
            }
            const canvas = document.createElement('canvas');
            canvas.width = cameraPreview.videoWidth;
            canvas.height = cameraPreview.videoHeight;
            canvas.getContext('2d').drawImage(cameraPreview, 0, 0);
            canvas.toBlob((blob) => {
                if (!blob) {
                    photoStatus.textContent = 'Could not capture the photo. Please try again.';
                    return;
                }
                const photo = new File([blob], 'emergency-photo.jpg', { type: 'image/jpeg' });
                const transfer = new DataTransfer();
                transfer.items.add(photo);
                photoInput.files = transfer.files;
                showPhoto(photo);
                closeCamera();
            }, 'image/jpeg', 0.9);
        });
    }

    if (closeCameraBtn) closeCameraBtn.addEventListener('click', closeCamera);
    window.addEventListener('pagehide', closeCamera);
});
