function initIncidentDashboard(payload) {
    const mapElement = document.getElementById('incident-map');
    if (!mapElement) return;

    const incidentLat = Number(payload.lat || 0);
    const incidentLon = Number(payload.lon || 0);
    if (!incidentLat && !incidentLon) {
        mapElement.textContent = 'Add an incident location to see nearby resources.';
        const resourceList = document.getElementById('resource-list');
        if (resourceList) resourceList.textContent = 'Add an incident location to see nearby resources.';
        return;
    }
    const map = L.map('incident-map').setView([incidentLat, incidentLon], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const incidentMarker = L.marker([incidentLat, incidentLon], { icon: L.divIcon({ className: 'marker-red', html: '🔴' }) }).addTo(map);
    incidentMarker.bindPopup('Incident location');

    const resourceList = document.getElementById('resource-list');
    const routeInfo = document.getElementById('route-info');
    const allReadinessMap = {
        hospital: 'medical-support-status',
        police: 'police-support-status',
        fire_station: 'fire-support-status'
    };
    const isFireIncident = String(payload.emergencyType || '').toUpperCase().includes('FIRE');
    const readinessMap = Object.fromEntries(
        Object.entries(allReadinessMap).filter(([type]) => type !== 'fire_station' || isFireIncident)
    );

    const updateReadiness = (resourceType, present) => {
        const statusElement = document.getElementById(readinessMap[resourceType]);
        if (statusElement) {
            statusElement.textContent = present ? 'Nearby' : 'Search map below';
        }
    };

    const appendMapSearch = (resourceType) => {
        const labels = {
            hospital: 'Hospitals',
            police: 'Police Stations',
            fire_station: 'Fire Stations'
        };
        const card = document.createElement('div');
        card.className = 'resource-item resource-search-item';
        const heading = document.createElement('h4');
        heading.textContent = labels[resourceType];
        const link = document.createElement('a');
        const query = `${labels[resourceType]} near ${incidentLat.toFixed(5)}, ${incidentLon.toFixed(5)}`;
        link.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Search Google Maps';
        card.append(heading, link);
        resourceList.appendChild(card);
    };

    const markers = [];
    const fetchResources = async () => {
        try {
            const response = await fetch(`/api/resources?incident_id=${encodeURIComponent(payload.incidentId)}`);
            const data = await response.json();
            if (!data || !data.ok || !data.resources) {
                resourceList.textContent = data && data.message
                    ? data.message
                    : 'Nearby resource lookup failed. Check your connection and try refreshing.';
                Object.keys(readinessMap).forEach((typeKey) => {
                    updateReadiness(typeKey, false);
                    appendMapSearch(typeKey);
                });
                return;
            }

            const resources = data.resources.filter((resource) => resource && readinessMap[resource.type]);
            resourceList.innerHTML = '';
            if (data.stale && data.message) {
                const notice = document.createElement('p');
                notice.className = 'resource-stale-note';
                notice.setAttribute('role', 'status');
                notice.textContent = data.message;
                resourceList.appendChild(notice);
            }
            if (!resources.length) {
                Object.keys(readinessMap).forEach((typeKey) => {
                    updateReadiness(typeKey, false);
                    appendMapSearch(typeKey);
                });
                return;
            }
            const typeUsage = {};
            resources.forEach((resource) => {
                const markerColor = {
                    hospital: 'green',
                    fire_station: 'orange',
                    police: 'purple'
                }[resource.type] || 'red';
                const markerIcon = L.divIcon({ className: 'resource-marker', html: markerColor === 'green' ? '🟢' : markerColor === 'orange' ? '🟠' : '🟣' });
                const marker = L.marker([resource.lat, resource.lon], { icon: markerIcon }).addTo(map);
                const popup = document.createElement('div');
                const popupName = document.createElement('strong');
                popupName.textContent = resource.name;
                popup.append(popupName, document.createElement('br'), document.createTextNode(resource.type_label), document.createElement('br'), document.createTextNode(resource.address));
                marker.bindPopup(popup);
                markers.push(marker);
                typeUsage[resource.type] = true;

                const card = document.createElement('div');
                card.className = 'resource-item';
                const heading = document.createElement('h4');
                heading.textContent = resource.name;
                card.appendChild(heading);
                [
                    ['Type', resource.type_label || resource.type.replace('_', ' ')],
                    ['Address', resource.address],
                    ['Distance', resource.distance_km !== null && resource.distance_km !== undefined
                        ? `${resource.distance_km} km`
                        : ''],
                    ['Phone', resource.phone],
                    ['Website', resource.website]
                ].filter(([, value]) => value && value !== 'Address unavailable').forEach(([label, value]) => {
                    const paragraph = document.createElement('p');
                    const strong = document.createElement('strong');
                    strong.textContent = `${label}: `;
                    paragraph.append(strong, document.createTextNode(value));
                    card.appendChild(paragraph);
                });
                const sourceUrl = resource.source_url || resource.osm_url;
                if (sourceUrl) {
                    const sourceLink = document.createElement('a');
                    sourceLink.href = sourceUrl;
                    sourceLink.target = '_blank';
                    sourceLink.rel = 'noopener noreferrer';
                    sourceLink.textContent = resource.source === 'Google Maps'
                        ? 'View on Google Maps'
                        : 'View OpenStreetMap record';
                    card.appendChild(sourceLink);
                }
                card.addEventListener('click', () => {
                    document.querySelectorAll('.resource-item').forEach((item) => item.classList.remove('selected'));
                    card.classList.add('selected');
                    fetchRoute(resource);
                });
                resourceList.appendChild(card);
            });

            Object.keys(readinessMap).forEach((typeKey) => {
                const present = Boolean(typeUsage[typeKey]);
                updateReadiness(typeKey, present);
                if (!present) appendMapSearch(typeKey);
            });
            if (!isFireIncident) {
                typeUsage.fire_station = false;
            }

            if (resources.length) {
                const bounds = L.latLngBounds([
                    [incidentLat, incidentLon],
                    ...resources.map((resource) => [resource.lat, resource.lon])
                ]);
                map.fitBounds(bounds, { padding: [30, 30] });
            }
        } catch (error) {
            resourceList.textContent = 'Could not connect to the nearby-resource service. Check your internet connection and refresh to retry.';
            Object.keys(readinessMap).forEach((typeKey) => {
                updateReadiness(typeKey, false);
                appendMapSearch(typeKey);
            });
        }
    };

    const fetchRoute = async (resource) => {
        try {
            const routeResponse = await fetch(`/api/route?start_lat=${incidentLat}&start_lon=${incidentLon}&end_lat=${resource.lat}&end_lon=${resource.lon}`);
            const routeData = await routeResponse.json();
            if (!routeData.ok) {
                routeInfo.textContent = routeData.message || 'Road route unavailable';
                return;
            }
            routeInfo.innerHTML = '';
            [
                ['Destination', resource.name],
                ['Distance', `${routeData.distance_km} km`],
                ['Travel time', `${routeData.duration_min} min`]
            ].forEach(([label, value]) => {
                const paragraph = document.createElement('p');
                const strong = document.createElement('strong');
                strong.textContent = `${label}: `;
                paragraph.append(strong, document.createTextNode(value));
                routeInfo.appendChild(paragraph);
            });
        } catch (error) {
            routeInfo.textContent = 'Road route unavailable';
        }
    };

    fetchResources();
}

window.initIncidentDashboard = initIncidentDashboard;
