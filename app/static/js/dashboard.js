/**
 * DMRC Intelligent Demand & Scheduling Interactive Client
 */

const METRO_LINE_COLORS = {
    'Red Line': '#e32017',
    'Yellow Line': '#e5b500',
    'Blue Line': '#0066b3',
    'Blue Line branch': '#0066b3',
    'Green Line': '#00843d',
    'Green Line branch': '#00843d',
    'Violet Line': '#7b2d5b',
    'Pink Line': '#df1683',
    'Magenta Line': '#8c1d82',
    'Orange Line': '#ed7d31',
    'Grey Line': '#6c7074',
    'Aqua Line': '#00a6a6'
};

function getLineColor(lineName) {
    if (!lineName) return '#0284c7';
    for (const [key, color] of Object.entries(METRO_LINE_COLORS)) {
        if (lineName.toLowerCase().includes(key.toLowerCase()) || key.toLowerCase().includes(lineName.toLowerCase())) {
            return color;
        }
    }
    return '#0284c7';
}

let demandChart = null;
let lineChart = null;
let currentData = null;
let currentTravelTimes = [];
let predictionRequestId = 0;

document.addEventListener('DOMContentLoaded', () => {
    initControls();
    fetchPrediction(); // Populate the analysis for the default scenario.
});

function initControls() {
    const stationSelect = document.getElementById('station');
    const timeSlider = document.getElementById('timeSlider');
    const timeInput = document.getElementById('time');
    const dateInput = document.getElementById('date');
    const lineSelect = document.getElementById('lineSelect');
    const travelSearchInput = document.getElementById('travelSearchInput');
    const predictionForm = document.getElementById('predictionForm');
    if (predictionForm) predictionForm.addEventListener('submit', (event) => event.preventDefault());

    // Station selection change
    if (stationSelect) {
        stationSelect.addEventListener('change', () => {
            updateLineSelectOptions();
            fetchPrediction();
        });
    }

    // Slider change
    if (timeSlider) {
        timeSlider.addEventListener('input', (e) => {
            const h = String(e.target.value).padStart(2, '0');
            if (timeInput) timeInput.value = `${h}:00`;
            document.getElementById('selectedTimeLabel').textContent = `${h}:00`;
            fetchPrediction();
        });
    }

    // Time input change
    if (timeInput) {
        timeInput.addEventListener('change', (e) => {
            const parts = e.target.value.split(':');
            const h = parseInt(parts[0], 10);
            if (timeSlider && !isNaN(h)) {
                timeSlider.value = h;
                document.getElementById('selectedTimeLabel').textContent = e.target.value;
            }
            fetchPrediction();
        });
    }

    // Date change
    if (dateInput) {
        dateInput.addEventListener('change', () => {
            document.querySelectorAll('.btn-preset-day').forEach(b => b.classList.remove('active'));
            fetchPrediction();
        });
    }

    // Line selection change
    if (lineSelect) {
        lineSelect.addEventListener('change', () => {
            fetchPrediction();
        });
    }

    // Travel station search input filter
    if (travelSearchInput) {
        travelSearchInput.addEventListener('input', () => {
            filterAndDisplayTravelTimes();
        });
    }

    // Quick Day Preset buttons
    document.querySelectorAll('.btn-preset-day').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const preset = btn.getAttribute('data-preset');
            if (dateInput) {
                const target = new Date();
                target.setHours(12, 0, 0, 0);
                if (preset === 'weekday') {
                    do { target.setDate(target.getDate() + 1); }
                    while (target.getDay() === 0 || target.getDay() === 6);
                } else if (preset === 'saturday' || preset === 'sunday') {
                    const wantedDay = preset === 'saturday' ? 6 : 0;
                    do { target.setDate(target.getDate() + 1); }
                    while (target.getDay() !== wantedDay);
                }
                const targetDate = [target.getFullYear(), String(target.getMonth() + 1).padStart(2, '0'), String(target.getDate()).padStart(2, '0')].join('-');
                dateInput.value = targetDate;
                document.querySelectorAll('.btn-preset-day').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                fetchPrediction();
            }
        });
    });

    updateLineSelectOptions();
}

function updateLineSelectOptions() {
    const stationSelect = document.getElementById('station');
    const lineSelect = document.getElementById('lineSelect');
    if (!stationSelect || !lineSelect || !window.STATIONS_META) return;

    const selectedStation = stationSelect.value;
    const meta = window.STATIONS_META[selectedStation];

    lineSelect.innerHTML = '<option value="">All Lines (Station Overview)</option>';
    if (meta && meta.all_lines && meta.all_lines.length > 0) {
        meta.all_lines.forEach(line => {
            const opt = document.createElement('option');
            opt.value = line;
            opt.textContent = line;
            lineSelect.appendChild(opt);
        });
        document.getElementById('lineSelectGroup').style.display = 'block';
    } else {
        document.getElementById('lineSelectGroup').style.display = 'none';
    }
}

async function fetchPrediction() {
    const requestId = ++predictionRequestId;
    const station = document.getElementById('station').value;
    const date = document.getElementById('date').value;
    const time = document.getElementById('time').value;
    const line = document.getElementById('lineSelect').value;

    const loader = document.getElementById('loadingIndicator');
    const formStatus = document.getElementById('forecastFormStatus');
    if (loader) loader.style.display = 'inline-block';
    if (formStatus) {
        formStatus.textContent = 'Updating analysis…';
        formStatus.classList.remove('is-error');
    }

    try {
        const res = await fetch('/api/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ station, date, time, line })
        });
        const data = await res.json();
        if (requestId !== predictionRequestId) return;
        if (data.status === 'success') {
            currentData = data;
            renderDashboard(data);
            document.body.classList.add('forecast-ready');
            if (formStatus) formStatus.textContent = '';
            requestAnimationFrame(() => {
                if (demandChart) demandChart.resize();
                if (lineChart) lineChart.resize();
            });
        } else if (formStatus) {
            formStatus.textContent = data.message || 'The forecast could not be generated. Check the selected inputs and try again.';
            formStatus.classList.add('is-error');
        }
    } catch (err) {
        console.error('Error fetching prediction:', err);
        if (formStatus) {
            formStatus.textContent = 'We could not reach the forecasting service. Please try again.';
            formStatus.classList.add('is-error');
        }
    } finally {
        if (requestId === predictionRequestId) {
            if (loader) loader.style.display = 'none';
        }
    }
}

function renderDashboard(data) {
    if (!data || !data.scheduling) return;
    const { station, datetime, footfall, scheduling, profile_24h, station_info } = data;
    const hl = scheduling.headline;
    const serviceClosed = datetime.service_open === false;
    const selectedLine = document.getElementById('lineSelect')?.value || '';
    const lineDemand = Number.isFinite(Number(hl.line_demand)) ? Number(hl.line_demand) : footfall.hourly_demand;
    const originEl = document.getElementById('travelOriginName');
    if (originEl) originEl.textContent = station;
    const contextLine = document.getElementById('dispForecastContext');
    if (contextLine) {
        const calendar = data.calendar_context || {};
        const dateLabel = new Date(`${datetime.date}T12:00:00`).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
        const occasion = calendar.occasion || 'No major occasion in the loaded calendar';
        contextLine.textContent = `${dateLabel} · ${calendar.day_status || 'Day type unavailable'} · ${datetime.time} · ${occasion}`;
    }

    const calendarEl = document.getElementById('calendarContext');
    if (calendarEl && data.calendar_context) {
        const calendar = data.calendar_context;
        const occasion = calendar.occasion || 'No major occasion in the loaded calendar';
        const source = calendar.calendar_source ? ` Calendar: ${calendar.calendar_source}.` : '';
        calendarEl.textContent = serviceClosed
            ? `${calendar.weekday}, ${datetime.date} · ${calendar.day_status} · ${occasion}. ${datetime.time}: Metro closed; no trains or passenger demand are modeled. Daily operating-hours peak ${calendar.daily_peak_hour}.${source}`
            : `${calendar.weekday}, ${datetime.date} · ${calendar.day_status} · ${occasion}. ${datetime.time}: ${calendar.hour_band}, relative to this station’s forecast curve; daily peak ${calendar.daily_peak_hour}.${source}`;
    }

    try {
        // Station badges & details
        const stNameEl = document.getElementById('dispStationName');
        if (stNameEl) stNameEl.textContent = station;
        const stLineEl = document.getElementById('dispStationLine');
        if (stLineEl) {
            stLineEl.textContent = station_info.is_interchange 
                ? `Interchange Hub (${station_info.all_lines.join(', ')})`
                : station_info.line;
        }

        // KPI 1: Hourly Demand
        const ffEl = document.getElementById('dispFootfall');
        if (ffEl) ffEl.textContent = lineDemand.toLocaleString();
        const instFfEl = document.getElementById('dispInstantFootfall');
        const currentShare = footfall.hourly_demand ? lineDemand / footfall.hourly_demand : 1;
        if (instFfEl) instFfEl.textContent = serviceClosed ? 'Metro closed; no passenger service' : `${selectedLine ? `${selectedLine} · ` : (hl.is_station_summary ? 'All lines · ' : '')}Interpolated estimate: ${Math.round(footfall.instant_interpolated * currentShare).toLocaleString()}`;
        
        // KPI 2: Recommended Headway
        const recHwEl = document.getElementById('dispRecHeadway');
        if (recHwEl) recHwEl.textContent = serviceClosed ? 'Closed' : (hl.is_station_summary ? 'Varies' : `${hl.recommended_headway_min}m`);
        const existHwEl = document.getElementById('dispExistingHeadway');
        if (existHwEl) existHwEl.textContent = serviceClosed ? 'No service at selected time' : (hl.is_station_summary ? `See ${hl.line_count} line recommendations below` : `Baseline: ${hl.existing_headway_min}m (${hl.is_peak ? 'Peak' : 'Off-Peak'})`);

        // KPI 3: Trains Per Hour
        const recTrEl = document.getElementById('dispRecTrains');
        if (recTrEl) recTrEl.textContent = serviceClosed ? '0' : `${hl.recommended_trains_per_hour}`;
        const existTrEl = document.getElementById('dispExistingTrains');
        if (existTrEl) existTrEl.textContent = serviceClosed ? 'No trains operating' : (hl.is_station_summary ? `Combined across ${hl.line_count} lines · trains/hour` : `Baseline: ${hl.existing_trains_per_hour} trains/hr`);

        // KPI 4: Capacity Utilization & Crowding Risk
        const utilEl = document.getElementById('dispUtilization');
        if (utilEl) utilEl.textContent = serviceClosed ? 'N/A' : `${hl.capacity_utilization_pct}%`;
        const utilContextEl = document.getElementById('dispUtilizationContext');
        if (utilContextEl) {
            const scope = hl.is_station_summary ? 'All lines' : (selectedLine || hl.line);
            const capacity = Number(hl.recommended_clearance_capacity || 0).toLocaleString();
            utilContextEl.textContent = serviceClosed ? 'Metro closed' : `${scope} · estimated boarding capacity ${capacity}/hr`;
        }
        // KPI 5: Average Wait Time
        const waitEl = document.getElementById('dispWaitTime');
        if (waitEl) waitEl.textContent = serviceClosed ? 'N/A' : `${hl.avg_wait_time_rec_min} min`;
        const fleetEl = document.getElementById('dispFleetDeployed');
        if (fleetEl) fleetEl.textContent = serviceClosed ? 'No trains operating' : `Active Fleet: ${hl.trains_deployed_rec}/${hl.fleet_size_available} trains`;

        // Operational Explanation Box
        const expEl = document.getElementById('dispExplanationText');
        if (expEl) expEl.textContent = hl.explanation;
    } catch (e) {
        console.error('Error rendering KPI elements:', e);
    }

    try {
        // Render 24h Demand Curve Chart
        let demandProfile = profile_24h;
        if (selectedLine && profile_24h.line_curves && profile_24h.line_curves[selectedLine]) {
            const share = footfall.hourly_demand ? lineDemand / footfall.hourly_demand : 1;
            demandProfile = {
                ...profile_24h,
                predicted: profile_24h.line_curves[selectedLine],
                historical: (profile_24h.historical || []).map(value => Math.round(value * share))
            };
        }
        const chartTitle = document.querySelector('#demandChartCanvas')?.closest('.card')?.querySelector('.card-title span');
        if (chartTitle) chartTitle.textContent = selectedLine ? `${selectedLine} passenger demand by hour` : 'Passenger demand by operating hour';
        renderDemandChart(demandProfile, datetime.hour);
    } catch (e) {
        console.error('Error rendering demand chart:', e);
    }

    try {
        // Render Line Breakdown (Always shown, whether interchange or single line!)
        renderInterchangeBreakdown(scheduling);
    } catch (e) {
        console.error('Error rendering line breakdown:', e);
    }

    try {
        // Render travel-time estimates for all reachable destination stations.
        renderTravelTimes(data.travel_times);
    } catch (e) {
        console.error('Error rendering travel times:', e);
    }
}

function renderDemandChart(profile, currentHour) {
    const ctx = document.getElementById('demandChartCanvas');
    if (!ctx || !profile) return;

    const labels = profile.labels || [];
    const predicted = profile.predicted || [];
    const historical = profile.historical || [];

    // Mark current selected hour point
    const pointRadii = labels.map((_, i) => profile.hours && profile.hours[i] === currentHour ? 6 : 3);
    const pointBackgrounds = labels.map((_, i) => profile.hours && profile.hours[i] === currentHour ? '#ef4444' : '#0284c7');

    const datasets = [
        {
            label: 'Simulated demand estimate (model trained on synthetic data)',
            data: predicted,
            borderColor: '#0284c7',
            backgroundColor: 'rgba(2, 132, 199, 0.08)',
            borderWidth: 2.5,
            fill: true,
            tension: 0.35,
            pointRadius: pointRadii,
            pointBackgroundColor: pointBackgrounds
        },
        {
            label: 'Synthetic training-period baseline mean',
            data: historical,
            borderColor: '#94a3b8',
            borderWidth: 1.8,
            borderDash: [5, 5],
            fill: false,
            tension: 0.35,
            pointRadius: 2
        }
    ];

    // If interchange with multiple lines, add each corridor's 24-hour demand trend
    if (profile.line_curves && Object.keys(profile.line_curves).length > 1) {
        for (const [lineName, curve] of Object.entries(profile.line_curves)) {
            const lineColor = getLineColor(lineName);
            datasets.push({
                label: `${lineName} Demand Trend`,
                data: curve,
                borderColor: lineColor,
                backgroundColor: 'transparent',
                borderWidth: 2,
                borderDash: [4, 2],
                fill: false,
                tension: 0.35,
                pointRadius: 2,
                pointBackgroundColor: lineColor
            });
        }
    }

    if (demandChart) {
        demandChart.destroy();
    }

    demandChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { font: { size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toLocaleString()} passengers`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Passengers / Hour', font: { size: 12 } }
                },
                x: {
                    title: { display: true, text: 'Operating Hour (05:00 - 23:00)', font: { size: 12 } }
                }
            }
        }
    });
}

function renderInterchangeBreakdown(scheduling) {
    const container = document.getElementById('interchangeSection');
    if (!container) return;

    // ALWAYS visible for all stations
    container.style.display = 'block';

    const titleEl = document.getElementById('interchangeSectionTitle');
    const descEl = document.getElementById('interchangeSectionDesc');

    if (scheduling.is_interchange) {
        if (titleEl) titleEl.textContent = 'Interchange Line Demand Distribution';
        if (descEl) descEl.textContent = 'Demand distributed across intersecting lines using corridor capacity and network centrality weighting.';
    } else {
        if (titleEl) titleEl.textContent = 'Corridor Demand & Service Allocation';
        if (descEl) descEl.textContent = 'Full passenger demand allocated to this single-line corridor.';
    }

    const lines = scheduling.all_lines;
    const tableBody = document.getElementById('lineBreakdownTableBody');
    tableBody.innerHTML = '';

    const labels = [];
    const demands = [];
    const sliceColors = [];

    lines.forEach((l) => {
        labels.push(l.line);
        demands.push(l.line_demand);
        const lineColor = getLineColor(l.line);
        sliceColors.push(lineColor);

        const tr = document.createElement('tr');
        const serviceClosed = l.status_action === 'SERVICE_CLOSED';
        tr.innerHTML = `
            <td>
                <span class="line-chip" style="--metro-line-color: ${lineColor}"><i class="line-marker" aria-hidden="true"></i><span>${l.line}</span></span>
            </td>
            <td><strong>${serviceClosed ? '—' : `${l.demand_share_pct}%`}</strong></td>
            <td><strong>${l.line_demand.toLocaleString()}</strong> riders/hr</td>
            <td>${serviceClosed ? 'Closed' : `${l.existing_headway_min}m`}</td>
            <td><strong style="color: #0284c7;">${serviceClosed ? 'Closed' : `${l.recommended_headway_min}m (${l.recommended_trains_per_hour} tph)`}</strong></td>
            <td><span class="badge" style="background: ${l.crowding_color}; color: white;">${serviceClosed ? '—' : `${l.capacity_utilization_pct}%`}</span></td>
        `;
        tableBody.appendChild(tr);
    });

    const ctx = document.getElementById('lineChartCanvas');
    if (ctx) {
        if (lineChart) lineChart.destroy();
        lineChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: demands,
                    backgroundColor: sliceColors,
                    borderWidth: 2,
                    borderColor: getComputedStyle(document.documentElement).getPropertyValue('--surface').trim() || '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            font: { size: 12, weight: 'bold' },
                            usePointStyle: true,
                            pointStyle: 'rectRounded'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ` ${ctx.label}: ${ctx.raw.toLocaleString()} riders/hr`
                        }
                    }
                }
            }
        });
    }
}

function renderTravelTimes(times) {
    if (times) {
        currentTravelTimes = times;
    }
    filterAndDisplayTravelTimes();
}

function filterAndDisplayTravelTimes() {
    const tableBody = document.getElementById('travelTimesTableBody');
    const searchInput = document.getElementById('travelSearchInput');
    const countBadge = document.getElementById('travelStationCount');
    if (!tableBody) return;

    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

    const filtered = currentTravelTimes.filter(item => {
        if (!query) return true;
        const dest = (item.destination || item['End Station'] || '').toLowerCase();
        const line = (item.line || item['Line'] || '').toLowerCase();
        return dest.includes(query) || line.includes(query);
    });

    if (countBadge) {
        countBadge.textContent = `${filtered.length} of ${currentTravelTimes.length}`;
    }

    tableBody.innerHTML = '';

    if (filtered.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="3" style="text-align: center; color: #64748b; padding: 20px;">No destination stations matching "${query}"</td>`;
        tableBody.appendChild(tr);
        return;
    }

    filtered.forEach(item => {
        const dest = item.destination || item['End Station'];
        const mins = item.travel_time_min ?? item['Travel Time (minutes)'];
        const line = item.line || item['Line'] || 'Metro Network';
        const lineColor = getLineColor(line);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${dest}</strong></td>
            <td>
                <span class="line-chip" style="--metro-line-color: ${lineColor}">
                    <i class="line-marker" aria-hidden="true"></i><span>${line}</span>
                </span>
            </td>
            <td><span class="travel-time-value">${mins}<small> min</small></span></td>
        `;
        tableBody.appendChild(tr);
    });
}
