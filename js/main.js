// Helping Hands Core Logic

document.addEventListener('DOMContentLoaded', () => {

    // --- Date Time Logic ---
    function updateDateTime() {
        const dtElement = document.getElementById('dateTimeDisplay');
        if (!dtElement) return;

        const now = new Date();
        const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' };
        dtElement.textContent = now.toLocaleDateString('en-IN', options);
    }

    setInterval(updateDateTime, 1000);
    updateDateTime();


    // --- Navigation Drawer Logic ---
    const menuToggle = document.getElementById('menuToggle');
    const closeNavBtn = document.getElementById('closeNavBtn');
    const navDrawer = document.getElementById('navDrawer');

    if (menuToggle && navDrawer) {
        menuToggle.addEventListener('click', () => {
            navDrawer.classList.toggle('open');
        });
    }
    if (closeNavBtn && navDrawer) {
        closeNavBtn.addEventListener('click', () => {
            navDrawer.classList.remove('open');
        });
    }

    // Optional: close drawer if clicking outside
    document.addEventListener('click', (e) => {
        if (navDrawer && navDrawer.classList.contains('open') &&
            !navDrawer.contains(e.target) &&
            !menuToggle.contains(e.target)) {
            navDrawer.classList.remove('open');
        }
    });

    // --- View Navigation Logic ---
    const btnReportIssue = document.getElementById('btnReportIssue');
    const btnBecomeVolunteer = document.getElementById('btnBecomeVolunteer');

    if (btnReportIssue) {
        btnReportIssue.addEventListener('click', () => {
            showView('reportIssueView');
        });
    }

    if (btnBecomeVolunteer) {
        btnBecomeVolunteer.addEventListener('click', () => {
            showView('registerVolunteerView');
        });
    }

    // --- Report Issue Logic & Auto-assign Algorithm Simulation ---
    const reportIssueForm = document.getElementById('reportIssueForm');
    let currentIssuePayload = null;

    if (reportIssueForm) {
        reportIssueForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const location = document.getElementById('issueLocation').value;
            const problemType = document.getElementById('issueProblemType').value;
            const description = document.getElementById('issueDescription').value;
            const urgencyNode = document.querySelector('input[name="urgency"]:checked');
            const urgency = urgencyNode ? urgencyNode.value : 'low';

            currentIssuePayload = {
                location: location,
                problem_type: problemType,
                urgency: urgency,
                description: description
            };

            try {
                window.showToast('Validating with AI...', 'info');

                const valRes = await fetch('/api/validate_issue', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(currentIssuePayload)
                });

                if (!valRes.ok) throw new Error("Validation request failed");
                const validationResult = await valRes.json();

                if (validationResult.isValid === false) {
                    const modal = document.getElementById('aiValidationModal');
                    const content = document.getElementById('aiValidationContent');

                    content.innerHTML = `
                        <p class="mb-2"><strong class="color-yellow"><i class="fas fa-exclamation-triangle"></i> We noticed a potential mismatch:</strong></p>
                        <p class="mb-2 text-muted">${validationResult.reason}</p>
                        <div class="glass-mini-card p-2">
                            <p><strong>Suggested Problem Type:</strong> ${validationResult.suggestion.problem_type}</p>
                            <p><strong>Suggested Urgency:</strong> <span class="capitalize">${validationResult.suggestion.urgency}</span></p>
                        </div>
                    `;

                    window.suggestedPayload = {
                        ...currentIssuePayload,
                        problem_type: validationResult.suggestion.problem_type,
                        urgency: validationResult.suggestion.urgency
                    };

                    modal.classList.remove('hidden');
                } else {
                    submitFinalIssue(currentIssuePayload);
                }
            } catch (error) {
                console.error("AI Validation Error:", error);
                submitFinalIssue(currentIssuePayload);
            }
        });
    }

    async function submitFinalIssue(payload) {
        try {
            const response = await fetch('/api/report_issue', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error('Failed to report issue');

            const result = await response.json();

            window.addMarkerToMap(payload);

            const liElement = addIssueToSidebar(payload, false);
            showView('matchingView');
            simulateAutoAssign(result.matched_volunteer, payload, liElement);
            reportIssueForm.reset();
        } catch (error) {
            console.error('Error reporting issue:', error);
            if (window.showToast) {
                window.showToast('Failed to report issue to backend', 'error');
            } else {
                alert('Failed to report issue to backend.');
            }
        }
    }

    const btnKeepInput = document.getElementById('btnKeepInput');
    const btnTakeSuggestion = document.getElementById('btnTakeSuggestion');
    const aiValidationModal = document.getElementById('aiValidationModal');
    const closeValidationModalBtn = document.getElementById('closeValidationModalBtn');

    if (btnKeepInput && aiValidationModal) {
        btnKeepInput.addEventListener('click', () => {
            aiValidationModal.classList.add('hidden');
            submitFinalIssue(currentIssuePayload);
        });
    }

    if (btnTakeSuggestion && aiValidationModal) {
        btnTakeSuggestion.addEventListener('click', () => {
            aiValidationModal.classList.add('hidden');
            submitFinalIssue(window.suggestedPayload);
        });
    }

    if (closeValidationModalBtn && aiValidationModal) {
        closeValidationModalBtn.addEventListener('click', () => {
            aiValidationModal.classList.add('hidden');
        });
    }

    // --- Volunteer Form Logic ---
    const volunteerForm = document.getElementById('volunteerForm');
    if (volunteerForm) {
        volunteerForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const name = document.getElementById('volName').value;
            const skills = document.getElementById('volSkills').value;
            const location = document.getElementById('volLocation').value;
            const availability = document.getElementById('volAvailability').value;

            const payload = {
                name: name,
                skills: skills,
                location: location,
                availability: availability
            };

            try {
                const response = await fetch('/api/register_volunteer', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    throw new Error('Failed to register volunteer');
                }

                window.showToast('Registered as volunteer successfully!', 'success');
                showView('dashboardView');
                volunteerForm.reset();
            } catch (error) {
                console.error('Error registering volunteer:', error);
                if (window.showToast) {
                    window.showToast('Failed to register volunteer', 'error');
                } else {
                    alert('Failed to register volunteer.');
                }
            }
        });
    }

    const LOCATION_COORDS_JS = {
        'andheri': [19.1136, 72.8697],
        'juhu': [19.1075, 72.8263],
        'bandra': [19.0596, 72.8295],
        'kurla': [19.0726, 72.8845],
        'dadar': [19.0178, 72.8478],
        'colaba': [18.9067, 72.8147],
        'borivali': [19.2307, 72.8567],
        'kandivali': [19.2047, 72.8361],
        'powai': [19.1176, 72.9060],
        'sion': [19.0390, 72.8619],
        'thane': [19.2183, 72.9781],
        'goregaon': [19.1663, 72.8526],
        'dharavi': [19.0380, 72.8538]
    };

    window.addMarkerToMap = function (issue) {
        if (!window.appMapLayerGroup) return;
        const locClean = (issue.location || '').toLowerCase();
        const coords = LOCATION_COORDS_JS[locClean];
        if (!coords) return;

        let type = 'green';
        if (issue.urgency === 'critical' || issue.urgency === 'high') type = 'red';
        else if (issue.urgency === 'medium') type = 'yellow';

        const priorityStr = type === 'red' ? 'Critical' : (type === 'yellow' ? 'Medium' : 'Low');

        // Add minimal deterministic/random jitter so issues at identical suburbs don't perfectly eclipse each other
        const jitterX = (Math.random() - 0.5) * 0.015;
        const jitterY = (Math.random() - 0.5) * 0.015;
        const finalCoords = [coords[0] + jitterX, coords[1] + jitterY];

        const customIcon = L.divIcon({
            html: `<div class="dot ${type}" style="width: 14px; height: 14px; border: 2px solid white; box-shadow: 0 0 10px var(--color-${type}); animation: blink-pulse 2s infinite;"></div>`,
            className: '',
            iconSize: [14, 14],
            iconAnchor: [7, 7]
        });

        L.marker(finalCoords, { icon: customIcon })
            .addTo(window.appMapLayerGroup)
            .bindPopup(`<strong>${issue.problem_type} (${issue.location})</strong><br>Urgency: ${priorityStr}`, {
                closeButton: true
            });
    }

    // --- Interactive Map Initialization ---
    function initMap() {
        const mapContainer = document.getElementById('map');
        if (!mapContainer) return;

        // Mumbai coordinates
        const map = L.map('map').setView([19.0760, 72.8777], 11);
        window.appMap = map; // For global access to invalidateSize
        window.appMapLayerGroup = L.layerGroup().addTo(map);

        // Adding realistic map tiles (OpenStreetMap)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }).addTo(map);
    }
    // --- AI Summary Logic ---
    const btnAiSummary = document.getElementById('btnAiSummary');
    const aiSummaryModal = document.getElementById('aiSummaryModal');
    const closeAiModalBtn = document.getElementById('closeAiModalBtn');
    const aiSummaryContent = document.getElementById('aiSummaryContent');

    if (btnAiSummary && aiSummaryModal) {
        btnAiSummary.addEventListener('click', async () => {
            aiSummaryModal.classList.remove('hidden');
            aiSummaryContent.innerHTML = '<div class="text-center"><i class="fas fa-circle-notch fa-spin fa-2x color-secondary mb-2" style="margin-bottom:10px;"></i><p>Scanning global reports with Gemini AI...</p></div>';

            try {
                const response = await fetch('/api/ai_summary');
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to fetch AI summary');
                }

                let summaryText = data.summary;
                if (summaryText.includes('AI_REC_MARKER')) {
                    summaryText = summaryText.replace('AI_REC_MARKER', '<div class="glass-mini-card" style="border-left: 3px solid var(--color-yellow); margin-top: 10px; background: rgba(255, 193, 7, 0.1);"><strong class="color-yellow"><i class="fas fa-lightbulb"></i> AI Recommendation:</strong><br/>');
                    summaryText += '</div>';
                }

                aiSummaryContent.innerHTML = `<div class="fade-in">${summaryText.replace(/\n/g, '<br>')}</div>`;
            } catch (error) {
                console.error('AI Summary Error:', error);
                aiSummaryContent.innerHTML = `<div class="color-red fade-in"><i class="fas fa-exclamation-triangle"></i> Error: ${error.message}</div>`;
            }
        });

        closeAiModalBtn.addEventListener('click', () => {
            aiSummaryModal.classList.add('hidden');
        });

        aiSummaryModal.addEventListener('click', (e) => {
            if (e.target === aiSummaryModal) {
                aiSummaryModal.classList.add('hidden');
            }
        });
    }

    initMap();

    // --- Persistence: Load Existing Reports ---
    async function loadExistingReports() {
        try {
            const res = await fetch('/api/get_reports');
            if (!res.ok) return;
            const reports = await res.json();
            console.log("Fetched reports from DB:", reports);

            const pendingList = document.getElementById('pendingIssuesList');
            const resolvedList = document.getElementById('resolvedIssuesList');

            let criticalCount = 0, mediumCount = 0, lowCount = 0;
            reports.forEach(r => {
                const urg = (r.urgency || '').toLowerCase();
                if (urg === 'critical' || urg === 'high') criticalCount++;
                else if (urg === 'medium') mediumCount++;
                else lowCount++;
            });

            const elCritical = document.getElementById('countCritical');
            const elMedium = document.getElementById('countMedium');
            const elLow = document.getElementById('countLow');

            if (elCritical) elCritical.textContent = criticalCount;
            if (elMedium) elMedium.textContent = mediumCount;
            if (elLow) elLow.textContent = lowCount;

            // Sort reports by timestamp (newest first)
            if (reports.length > 0) {
                reports.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            }

            // Take recent 5
            const recentReports = reports.slice(0, 5);

            if (window.appMapLayerGroup) {
                window.appMapLayerGroup.clearLayers();
            }

            // Sort reports so we can insert them at the top correctly
            // We iterate through recent reports and use insertBefore(firstChild)
            // To keep the newest at the very top, we process from oldest to newest in this slice
            recentReports.reverse().forEach(report => {
                window.addMarkerToMap(report);

                let color = 'green';
                if (report.urgency === 'critical' || report.urgency === 'high') color = 'red';
                else if (report.urgency === 'medium') color = 'yellow';

                const li = document.createElement('li');

                if (report.matched_volunteer && (Array.isArray(report.matched_volunteer) ? report.matched_volunteer.length > 0 : true)) {
                    const vols = Array.isArray(report.matched_volunteer) ? report.matched_volunteer : [report.matched_volunteer];
                    const volNames = vols.map(v => v.name).join(', ');
                    li.innerHTML = `<div class="dot green"></div> ${report.problem_type} <span class="loc">(${report.location})</span> <span class="text-xs" style="color: var(--color-green);"> - Assigned to ${volNames}</span>`;
                    if (resolvedList) resolvedList.insertBefore(li, resolvedList.firstChild);
                } else {
                    li.innerHTML = `<div class="dot ${color}"></div> ${report.problem_type} <span class="loc">(${report.location})</span>`;
                    if (pendingList) pendingList.insertBefore(li, pendingList.firstChild);
                }
            });
        } catch (e) {
            console.error("Error loading reports", e);
        }
    }
    loadExistingReports();

});

// Global showToast for custom popup messages
window.showToast = function (message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<i class="fas fa-check-circle"></i> <span>${message}</span>`;

    container.appendChild(toast);

    // Trigger entrance animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400); // Wait for transition
    }, 3000);
};

// Global showView function for onclick attributes in HTML
window.showView = function (viewId, pushHistory = true) {
    const views = document.querySelectorAll('.view');
    views.forEach(v => {
        v.classList.remove('active');
        v.classList.add('hidden');
    });

    const targetView = document.getElementById(viewId);
    if (targetView) {
        targetView.classList.remove('hidden');
        targetView.classList.add('active');

        // Ensure map renders correctly if it was hidden
        if (viewId === 'dashboardView' && window.appMap) {
            setTimeout(() => {
                window.appMap.invalidateSize();
            }, 100);
        }
    }

    // If drawer is open, close it on navigation
    const navDrawer = document.getElementById('navDrawer');
    if (navDrawer && navDrawer.classList.contains('open')) {
        navDrawer.classList.remove('open');
    }

    // Push state so the browser's back button works seamlessly
    if (pushHistory) {
        window.history.pushState({ view: viewId }, '', `#${viewId}`);
    }
};

// Handle the browser "Undo" or "Back" arrow 
window.addEventListener('popstate', (e) => {
    if (e.state && e.state.view) {
        showView(e.state.view, false);
    } else {
        showView('dashboardView', false);
    }
});

// Set the initial default state
window.history.replaceState({ view: 'dashboardView' }, '', '');

let progressInterval;

function addIssueToSidebar(payload, matchedVolunteer) {
    let color = 'green';
    const urg = (payload.urgency || '').toLowerCase();

    if (urg === 'critical' || urg === 'high') {
        color = 'red';
        const el = document.getElementById('countCritical');
        if (el) el.textContent = parseInt(el.textContent || '0') + 1;
    } else if (urg === 'medium') {
        color = 'yellow';
        const el = document.getElementById('countMedium');
        if (el) el.textContent = parseInt(el.textContent || '0') + 1;
    } else {
        const el = document.getElementById('countLow');
        if (el) el.textContent = parseInt(el.textContent || '0') + 1;
    }

    const li = document.createElement('li');
    li.innerHTML = `<div class="dot ${color}"></div> ${payload.problem_type} <span class="loc">(${payload.location})</span>`;

    if (matchedVolunteer) {
        // Add to resolved list
        const list = document.getElementById('resolvedIssuesList');
        if (list) list.insertBefore(li, list.firstChild);
    } else {
        // Add to pending list
        const list = document.getElementById('pendingIssuesList');
        if (list) list.insertBefore(li, list.firstChild);
    }
    return li;
}

function simulateAutoAssign(matchedVolunteer, payload, liElement) {
    const progressBar = document.getElementById('assignProgressBar');
    const progressText = document.getElementById('progressText');
    const progressMessage = document.getElementById('progressMessage');
    const btnReturnHome = document.getElementById('btnReturnHome');
    const container = document.getElementById('matchedVolunteerContainer');

    if (!progressBar) return;

    // Reset states
    progressBar.style.width = '0%';
    progressText.textContent = '0%';
    progressMessage.textContent = 'Auto-assigning nearest capable volunteer...';
    btnReturnHome.classList.add('hidden');
    if (container) container.innerHTML = '';

    // Clear any existing interval to prevent weird speeding up if called multiple times
    if (progressInterval) clearInterval(progressInterval);

    let progress = 0;

    // Simulate backend processing algorithm
    progressInterval = setInterval(() => {
        progress += Math.floor(Math.random() * 8) + 4;

        if (progress >= 90 && !matchedVolunteer) {
            // Stop at 90% if no volunteer found
            progress = 90;
            clearInterval(progressInterval);
            progressBar.style.width = `90%`;
            progressText.textContent = `90%`;

            progressMessage.innerHTML = '<span class="color-yellow"><i class="fas fa-exclamation-triangle"></i> We apologize for the delay. No direct match found yet, but we will assign a volunteer soon.</span>';
            btnReturnHome.classList.remove('hidden');
            return;
        }

        if (progress >= 100) {
            progress = 100;
            clearInterval(progressInterval);

            // Render matched volunteer
            if (matchedVolunteer && container) {
                const vols = Array.isArray(matchedVolunteer) ? matchedVolunteer : [matchedVolunteer];
                let html = '';
                vols.forEach(vol => {
                    html += `
                        <div class="volunteer-item glass-mini-card fade-in" style="margin-bottom: 5px;">
                            <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(vol.name)}&background=10b981&color=fff&rounded=true" alt="Volunteer" class="avatar">
                            <div class="vol-info">
                                <h4>${vol.name}</h4>
                                <p class="text-xs text-muted">Assigned Location: ${vol.location || 'Unknown'}</p>
                            </div>
                            <div class="vol-distance pulse-green"><i class="fas fa-check-circle"></i> Matched</div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }

            // Assignment Complete State
            progressMessage.innerHTML = '<span class="color-green"><i class="fas fa-check-circle"></i> Volunteer Assigned Successfully! Notification sent.</span>';
            btnReturnHome.classList.remove('hidden');

            // Move item to resolved list once assignment is complete visually
            if (matchedVolunteer && liElement) {
                const resolvedList = document.getElementById('resolvedIssuesList');
                if (resolvedList) {
                    if (liElement.parentNode) {
                        liElement.parentNode.removeChild(liElement);
                    }
                    const vols = Array.isArray(matchedVolunteer) ? matchedVolunteer : [matchedVolunteer];
                    const volNames = vols.map(v => v.name).join(', ');
                    // Update dot to green and append volunteer name
                    liElement.innerHTML = `<div class="dot green"></div> ${payload.problem_type} <span class="loc">(${payload.location})</span> <span class="text-xs" style="color: var(--color-green);"> - Assigned to ${volNames}</span>`;
                    resolvedList.insertBefore(liElement, resolvedList.firstChild);
                }
            }
        } else if (progress > 60) {
            progressMessage.textContent = 'Confirming volunteer availability...';
        } else if (progress > 30) {
            progressMessage.textContent = 'Filtering candidates based on required skills & distance...';
        }

        progressBar.style.width = `${progress}%`;
        progressText.textContent = `${progress}%`;

    }, 400); // UI updates every 400ms
}
