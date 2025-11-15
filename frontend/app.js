/**
 * ZED 2i Dashboard Application with Three.js Point Cloud Visualization
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const API_URL = 'http://192.168.1.3:8005';
let currentTab = 'video';

// Initialization flags
let eventMonitoringInitialized = false;

// Frame counting
let frameCount = 0;
let lastTime = Date.now();

// Three.js Point Cloud variables
let scene, camera, renderer, controls;
let pointCloudMesh;
let pointCloudGeometry;
let pointCloudMaterial;

/**
 * Tab Switching
 */
function switchTab(tabName) {
    currentTab = tabName;

    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active from all buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Set active button
    const activeButton = Array.from(document.querySelectorAll('.tab-button'))
        .find(btn => btn.textContent.includes(getTabIcon(tabName)));
    if (activeButton) {
        activeButton.classList.add('active');
    }

    // Initialize Point Cloud on tab switch
    if (tabName === 'pointcloud' && !renderer) {
        initPointCloud();
    }

    // Initialize Event Monitoring on tab switch (only once)
    if (tabName === 'events' && !eventMonitoringInitialized) {
        initEventMonitoring();
        eventMonitoringInitialized = true;
    }
}

function getTabIcon(tabName) {
    const icons = {
        'video': '📹',
        'pointcloud': '🌐',
        'tracking': '🏃',
        'sensors': '📊',
        'aimonitoring': '🤖',
        'events': '🎯',
        'ipcameras': '📷',
        'settings': '⚙️'
    };
    return icons[tabName] || '';
}

/**
 * Server Status Check
 */
async function checkStatus() {
    try {
        const response = await fetch(`${API_URL}/`);
        const data = await response.json();

        document.getElementById('connection-status').textContent = 'Connected';

        if (data.mock_mode) {
            document.getElementById('camera-mode-stat').textContent = 'MOCK';
        } else {
            document.getElementById('camera-mode-stat').textContent = 'ZED 2i';
        }
    } catch (error) {
        document.getElementById('connection-status').textContent = 'Disconnected';
        console.error('Status check failed:', error);
    }
}

/**
 * Video Streams Update
 */
function updateStreams() {
    if (currentTab === 'video') {
        const timestamp = new Date().getTime();
        document.getElementById('rgb-stream').src = `${API_URL}/stream/rgb?t=${timestamp}`;
        document.getElementById('depth-stream').src = `${API_URL}/stream/depth?t=${timestamp}`;

        // Calculate FPS
        frameCount++;
        const now = Date.now();
        if (now - lastTime >= 1000) {
            const fps = frameCount;
            document.getElementById('rgb-fps').textContent = `${fps} FPS`;
            document.getElementById('depth-fps').textContent = `${fps} FPS`;
            document.getElementById('camera-fps').textContent = fps;
            frameCount = 0;
            lastTime = now;
        }
    }
}

/**
 * Initialize Three.js Point Cloud Renderer
 */
function initPointCloud() {
    const container = document.getElementById('pointcloud-canvas');
    if (!container) return;

    // Create scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    // Create camera
    camera = new THREE.PerspectiveCamera(
        75,
        container.clientWidth / container.clientHeight,
        0.1,
        1000
    );
    camera.position.set(0, 2, 5);

    // Create renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // Add OrbitControls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.screenSpacePanning = false;
    controls.minDistance = 1;
    controls.maxDistance = 50;

    // Create point cloud geometry
    pointCloudGeometry = new THREE.BufferGeometry();
    pointCloudMaterial = new THREE.PointsMaterial({
        size: 0.02,
        vertexColors: true,
        sizeAttenuation: true
    });

    pointCloudMesh = new THREE.Points(pointCloudGeometry, pointCloudMaterial);
    scene.add(pointCloudMesh);

    // Add grid helper
    const gridHelper = new THREE.GridHelper(10, 10, 0x444444, 0x222222);
    scene.add(gridHelper);

    // Add axes helper
    const axesHelper = new THREE.AxesHelper(2);
    scene.add(axesHelper);

    // Add ambient light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    // Add directional light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 7.5);
    scene.add(directionalLight);

    // Handle window resize
    window.addEventListener('resize', onWindowResize, false);

    // Start animation loop
    animate();

    console.log('Three.js Point Cloud initialized 🌐');
}

/**
 * Handle window resize
 */
function onWindowResize() {
    const container = document.getElementById('pointcloud-canvas');
    if (!container || !renderer) return;

    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
}

/**
 * Animation loop
 */
function animate() {
    requestAnimationFrame(animate);

    if (controls) {
        controls.update();
    }

    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
}

/**
 * Update Point Cloud from API
 */
async function updatePointCloud() {
    if (currentTab !== 'pointcloud') return;

    try {
        const response = await fetch(`${API_URL}/api/pointcloud`);
        if (!response.ok) return;

        const data = await response.json();
        if (!data.points || data.points.length === 0) return;

        // Create arrays for positions and colors
        const positions = new Float32Array(data.points.length * 3);
        const colors = new Float32Array(data.points.length * 3);

        data.points.forEach((point, i) => {
            // Position
            positions[i * 3] = point.x;
            positions[i * 3 + 1] = point.y;
            positions[i * 3 + 2] = point.z;

            // Color (RGB 0-255 to 0-1)
            colors[i * 3] = point.r / 255;
            colors[i * 3 + 1] = point.g / 255;
            colors[i * 3 + 2] = point.b / 255;
        });

        // Update geometry
        pointCloudGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        pointCloudGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        pointCloudGeometry.computeBoundingSphere();

        // Update overlay
        const overlay = document.querySelector('#tab-pointcloud .video-overlay');
        if (overlay) {
            overlay.textContent = `Points: ${data.points.length.toLocaleString()} / ${data.total_points.toLocaleString()}`;
        }

    } catch (error) {
        console.error('Failed to update point cloud:', error);
    }
}

/**
 * Update Sensor Data Display
 */
async function updateSensorData() {
    if (currentTab !== 'sensors') return;

    try {
        const response = await fetch(`${API_URL}/api/sensors`);
        if (!response.ok) return;

        const data = await response.json();
        const sensors = data.sensors;

        if (!sensors) return;

        // Update IMU data with safe access
        const accelX = sensors?.accel?.[0]?.toFixed(2) ?? '0.00';
        const accelY = sensors?.accel?.[1]?.toFixed(2) ?? '0.00';
        const accelZ = sensors?.accel?.[2]?.toFixed(2) ?? '0.00';

        document.getElementById('accel-x').textContent = `${accelX} m/s²`;
        document.getElementById('accel-y').textContent = `${accelY} m/s²`;
        document.getElementById('accel-z').textContent = `${accelZ} m/s²`;

        const gyroX = sensors?.gyro?.[0]?.toFixed(2) ?? '0.00';
        const gyroY = sensors?.gyro?.[1]?.toFixed(2) ?? '0.00';
        const gyroZ = sensors?.gyro?.[2]?.toFixed(2) ?? '0.00';

        document.getElementById('gyro-x').textContent = `${gyroX} rad/s`;
        document.getElementById('gyro-y').textContent = `${gyroY} rad/s`;
        document.getElementById('gyro-z').textContent = `${gyroZ} rad/s`;

        // Update environmental sensors
        if (sensors.temperature !== undefined) {
            document.getElementById('temperature').textContent = `${sensors.temperature.toFixed(1)}°C`;
        }

        if (sensors.pressure !== undefined) {
            document.getElementById('barometer').textContent = `${sensors.pressure.toFixed(1)} hPa`;
        }

    } catch (error) {
        console.error('Failed to update sensor data:', error);
    }
}

/**
 * Update Body Tracking Display
 */
async function updateBodyTracking() {
    if (currentTab !== 'tracking') return;

    try {
        const response = await fetch(`${API_URL}/api/bodies`);
        if (!response.ok) return;

        const data = await response.json();

        // Update overlay
        const overlay = document.querySelector('#tab-tracking .video-overlay');
        if (overlay) {
            if (data.bodies && data.bodies.length > 0) {
                overlay.textContent = `Detected ${data.bodies.length} body/bodies`;
            } else {
                overlay.textContent = 'No bodies detected';
            }
        }

    } catch (error) {
        console.error('Failed to update body tracking:', error);
    }
}

/**
 * Initialize Application
 */
function initApp() {
    console.log('ZED 2i Dashboard initializing 🎥');

    // Attach switchTab to window for button onclick
    window.switchTab = switchTab;

    // Check server status
    checkStatus();
    setInterval(checkStatus, 5000);

    // Update video streams
    setInterval(updateStreams, 100); // ~10fps for smooth display

    // Update Point Cloud
    setInterval(updatePointCloud, 500); // 2fps for point cloud

    // Update Sensor Data
    setInterval(updateSensorData, 100); // 10fps for sensor data

    // Update Body Tracking
    setInterval(updateBodyTracking, 200); // 5fps for body tracking

    // Update AI Statistics
    setInterval(updateAIStats, 1000); // 1fps for AI stats

    console.log('ZED 2i Dashboard ready ✅');
}

/**
 * ============================================
 * AI Monitoring Functions
 * ============================================
 */

/**
 * Motion Detection
 */
async function detectMotion() {
    try {
        const response = await fetch(`${API_URL}/api/ai/motion/detect`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Motion detection failed');

        const data = await response.json();

        // Update UI
        document.getElementById('motion-status').textContent = data.motion_detected ? '감지됨!' : '감지 안됨';
        document.getElementById('motion-count').textContent = data.detection_count;
        document.getElementById('motion-time').textContent = new Date(data.timestamp).toLocaleTimeString('ko-KR');

        console.log('Motion detection:', data);
    } catch (error) {
        console.error('Motion detection error:', error);
        document.getElementById('motion-status').textContent = '오류 발생';
    }
}

/**
 * Person Detection (YOLO)
 */
async function detectPerson() {
    try {
        const response = await fetch(`${API_URL}/api/ai/person/detect`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Person detection failed');

        const data = await response.json();

        // Update UI
        document.getElementById('person-count').textContent = data.person_count;
        document.getElementById('person-time').textContent = new Date(data.timestamp).toLocaleTimeString('ko-KR');

        if (data.detections && data.detections.length > 0) {
            const avgConfidence = data.detections.reduce((sum, d) => sum + d.confidence, 0) / data.detections.length;
            document.getElementById('person-confidence').textContent = (avgConfidence * 100).toFixed(1) + '%';
        } else {
            document.getElementById('person-confidence').textContent = '-';
        }

        console.log('Person detection:', data);
    } catch (error) {
        console.error('Person detection error:', error);
        document.getElementById('person-count').textContent = '오류';
    }
}

/**
 * Set Structure Baseline
 */
async function setStructureBaseline() {
    try {
        const response = await fetch(`${API_URL}/api/ai/structure/set-baseline`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Baseline setting failed');

        const data = await response.json();

        // Update UI
        if (data.baseline_set) {
            document.getElementById('structure-baseline').textContent = '설정됨 ✅';
            document.getElementById('structure-baseline').style.color = '#4ade80';
        }

        console.log('Baseline set:', data);
        alert('기준선이 설정되었습니다! 이제 구조 변화를 감지할 수 있습니다.');
    } catch (error) {
        console.error('Baseline setting error:', error);
        alert('기준선 설정 실패: ' + error.message);
    }
}

/**
 * Detect Structure Changes
 */
async function detectStructure() {
    try {
        const response = await fetch(`${API_URL}/api/ai/structure/detect`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Structure detection failed');

        const data = await response.json();

        // Update UI
        document.getElementById('structure-displacement-mm').textContent = data.displacement_mm.toFixed(2);
        document.getElementById('structure-displacement-px').textContent = data.displacement_pixels.toFixed(2);
        document.getElementById('structure-detected').textContent = data.change_detected ? '변화 감지됨! ⚠️' : '변화 없음';

        if (data.change_detected) {
            document.getElementById('structure-detected').style.color = '#f87171';
        } else {
            document.getElementById('structure-detected').style.color = '#4ade80';
        }

        console.log('Structure detection:', data);
    } catch (error) {
        console.error('Structure detection error:', error);
        document.getElementById('structure-detected').textContent = '오류 발생';
    }
}

/**
 * Analyze Scene (AI)
 */
async function analyzeScene() {
    try {
        document.getElementById('ai-description').textContent = '분석 중... 🔄';
        document.getElementById('ai-type').textContent = '장면 분석';

        const response = await fetch(`${API_URL}/api/ai/analyze/scene`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Scene analysis failed');

        const data = await response.json();

        // Update UI
        document.getElementById('ai-description').textContent = data.description;
        document.getElementById('ai-confidence').textContent = (data.confidence * 100).toFixed(1) + '%';
        document.getElementById('ai-processing-time').textContent = data.processing_time.toFixed(2) + '초';

        // Update anomalies
        const anomaliesDiv = document.getElementById('ai-anomalies');
        if (data.anomalies && data.anomalies.length > 0) {
            anomaliesDiv.innerHTML = data.anomalies.map(a =>
                `<div style="padding: 5px; margin: 5px 0; background: rgba(255, 0, 0, 0.2); border-radius: 4px;">⚠️ ${a}</div>`
            ).join('');
        } else {
            anomaliesDiv.innerHTML = '<span style="opacity: 0.7;">이상 항목이 없습니다.</span>';
        }

        console.log('Scene analysis:', data);
    } catch (error) {
        console.error('Scene analysis error:', error);
        document.getElementById('ai-description').textContent = '분석 실패: ' + error.message;
    }
}

/**
 * Analyze Anomaly (AI)
 */
async function analyzeAnomaly() {
    try {
        document.getElementById('ai-description').textContent = '이상 감지 중... 🔄';
        document.getElementById('ai-type').textContent = '이상 감지';

        const response = await fetch(`${API_URL}/api/ai/analyze/anomaly`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Anomaly detection failed');

        const data = await response.json();

        // Update UI
        document.getElementById('ai-description').textContent = data.description;
        document.getElementById('ai-confidence').textContent = (data.confidence * 100).toFixed(1) + '%';

        // Update anomalies
        const anomaliesDiv = document.getElementById('ai-anomalies');
        if (data.anomalies_detected && data.anomalies && data.anomalies.length > 0) {
            anomaliesDiv.innerHTML = data.anomalies.map(a =>
                `<div style="padding: 5px; margin: 5px 0; background: rgba(255, 0, 0, 0.3); border-radius: 4px;">🚨 ${a}</div>`
            ).join('');
        } else {
            anomaliesDiv.innerHTML = '<span style="opacity: 0.7; color: #4ade80;">✅ 이상 항목이 없습니다.</span>';
        }

        console.log('Anomaly detection:', data);
    } catch (error) {
        console.error('Anomaly detection error:', error);
        document.getElementById('ai-description').textContent = '분석 실패: ' + error.message;
    }
}

/**
 * Update AI Statistics
 */
async function updateAIStats() {
    if (currentTab !== 'aimonitoring') return;

    try {
        const response = await fetch(`${API_URL}/api/ai/stats`);
        if (!response.ok) return;

        const data = await response.json();

        // Update stats
        if (data.motion) {
            document.getElementById('stats-motion').textContent = data.motion.length || 0;
        }

        if (data.person && data.person.total_detections !== undefined) {
            document.getElementById('stats-person').textContent = data.person.total_detections;
        }

        if (data.structure) {
            document.getElementById('stats-structure').textContent = data.structure.length || 0;
        }

        if (data.analyzer && data.analyzer.total_analyses !== undefined) {
            document.getElementById('stats-ai').textContent = data.analyzer.total_analyses;
        }

    } catch (error) {
        console.error('Failed to update AI stats:', error);
    }
}

/**
 * ============================================================
 * 이벤트 모니터링 시스템
 * ============================================================
 */

// Event system state
let eventWebSocket = null;
let activeEventFilter = 'all';
let eventHistory = [];
let eventStats = {
    totalEvents: 0,
    eventsPerMin: 0,
    activeObjects: 0
};
let lastEventTime = Date.now();
let recentEventTimestamps = [];  // 최근 이벤트 타임스탬프 배열

/**
 * Initialize Event Monitoring System
 */
function initEventMonitoring() {
    // Setup event filter buttons
    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeEventFilter = btn.dataset.filter;
            filterEventFeed();
        });
    });

    // Setup refresh button
    const refreshBtn = document.getElementById('refresh-history');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadEventHistory);
    }

    // Connect to WebSocket
    connectEventWebSocket();

    // Load initial data
    loadEventHistory();
    loadSystemStats();

    // Update stats periodically
    setInterval(updateEventStats, 5000);
}

/**
 * Get WebSocket URL from API_URL
 */
function getWebSocketURL(path) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = API_URL.replace(/^https?:\/\//, '');
    return `${protocol}//${host}${path}`;
}

/**
 * Connect to Event WebSocket
 */
function connectEventWebSocket() {
    const wsUrl = getWebSocketURL('/api/ws/events');

    try {
        eventWebSocket = new WebSocket(wsUrl);

        eventWebSocket.onopen = () => {
            console.log('✅ Event WebSocket connected');
            updateWSStatus('connected');
        };

        eventWebSocket.onmessage = (event) => {
            try {
                const eventData = JSON.parse(event.data);
                handleIncomingEvent(eventData);
            } catch (error) {
                console.error('Failed to parse event:', error);
            }
        };

        eventWebSocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateWSStatus('error');
        };

        eventWebSocket.onclose = () => {
            console.log('❌ Event WebSocket disconnected');
            updateWSStatus('disconnected');

            // Reconnect after 5 seconds
            setTimeout(() => {
                if (currentTab === 'events') {
                    connectEventWebSocket();
                }
            }, 5000);
        };
    } catch (error) {
        console.error('Failed to create WebSocket:', error);
        updateWSStatus('error');
    }
}

/**
 * Update WebSocket Status Indicator
 */
function updateWSStatus(status) {
    const statusElement = document.getElementById('ws-status');
    if (!statusElement) return;

    const statusDot = statusElement.querySelector('.status-dot');
    const statusText = {
        'connected': '연결됨',
        'disconnected': '연결 끊김',
        'error': '오류'
    };

    const statusColors = {
        'connected': '#4ade80',
        'disconnected': '#888',
        'error': '#ef4444'
    };

    if (statusDot) {
        statusDot.style.background = statusColors[status] || '#888';
    }

    const textNode = Array.from(statusElement.childNodes)
        .find(node => node.nodeType === Node.TEXT_NODE);
    if (textNode) {
        textNode.textContent = ' ' + statusText[status];
    }
}

/**
 * Handle Incoming Event from WebSocket
 */
function handleIncomingEvent(eventData) {
    const now = Date.now();

    // Add to history
    eventHistory.unshift(eventData);
    if (eventHistory.length > 100) {
        eventHistory.pop();
    }

    // Update stats
    eventStats.totalEvents++;
    lastEventTime = now;

    // Add timestamp for accurate per-minute calculation
    recentEventTimestamps.push(now);

    // Remove timestamps older than 60 seconds
    recentEventTimestamps = recentEventTimestamps.filter(
        ts => (now - ts) <= 60000
    );

    // Update UI
    addEventToFeed(eventData);
    updateEventStats();
}

/**
 * Add Event to Real-time Feed
 */
function addEventToFeed(eventData) {
    const feedElement = document.getElementById('event-feed');
    if (!feedElement) return;

    // Remove placeholder
    const placeholder = feedElement.querySelector('.event-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    // Filter check
    if (activeEventFilter !== 'all' && eventData.event_type !== activeEventFilter) {
        return;
    }

    // Create event item
    const eventItem = document.createElement('div');
    eventItem.className = `event-item ${eventData.event_type}`;

    const eventTypeLabels = {
        'zone_entry': '🚪 구역 진입',
        'zone_exit': '🚶 구역 이탈',
        'idle': '⏸️ 정지',
        'distance_change': '📏 거리 변화',
        'speed_alert': '⚡ 속도 경고',
        'fall': '🚨 낙상 감지',
        'new_object': '🆕 새 객체'
    };

    const timeStr = new Date(eventData.timestamp).toLocaleTimeString('ko-KR');

    let detailsHTML = `객체: ${eventData.object_id || 'N/A'}`;
    if (eventData.zone_name) {
        detailsHTML += ` | 구역: ${eventData.zone_name}`;
    }
    if (eventData.movement_distance !== null && eventData.movement_distance !== undefined) {
        detailsHTML += ` | 거리: ${eventData.movement_distance.toFixed(2)}m`;
    }
    if (eventData.movement_speed !== null && eventData.movement_speed !== undefined) {
        detailsHTML += ` | 속도: ${eventData.movement_speed.toFixed(2)}m/s`;
    }

    eventItem.innerHTML = `
        <div class="event-header">
            <span class="event-type">${eventTypeLabels[eventData.event_type] || eventData.event_type}</span>
            <span class="event-time">${timeStr}</span>
        </div>
        <div class="event-details">${detailsHTML}</div>
    `;

    // Insert at top
    feedElement.insertBefore(eventItem, feedElement.firstChild);

    // Limit to 50 items
    while (feedElement.children.length > 50) {
        feedElement.removeChild(feedElement.lastChild);
    }
}

/**
 * Filter Event Feed
 */
function filterEventFeed() {
    const feedElement = document.getElementById('event-feed');
    if (!feedElement) return;

    // Clear feed
    feedElement.innerHTML = '<div class="event-placeholder">필터링된 이벤트를 표시합니다...</div>';

    // Re-add filtered events
    eventHistory.forEach(eventData => {
        if (activeEventFilter === 'all' || eventData.event_type === activeEventFilter) {
            addEventToFeed(eventData);
        }
    });
}

/**
 * Load Event History from API
 */
async function loadEventHistory() {
    try {
        const response = await fetch(`${API_URL}/api/events/latest?limit=50`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        const events = data.events || [];

        // Update eventHistory array for filter functionality
        eventHistory = events.slice();

        // Update table
        const tbody = document.getElementById('event-history-body');
        if (!tbody) return;

        if (events.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #888;">이벤트가 없습니다</td></tr>';
            return;
        }

        tbody.innerHTML = events.map(event => {
            const timeStr = new Date(event.timestamp).toLocaleString('ko-KR');
            const position = `(${(event.position_x || 0).toFixed(2)}, ${(event.position_y || 0).toFixed(2)}, ${(event.position_z || 0).toFixed(2)})`;
            const movement = event.movement_distance !== null
                ? `${event.movement_distance.toFixed(2)}m / ${(event.movement_speed || 0).toFixed(2)}m/s`
                : '-';

            return `
                <tr>
                    <td>${timeStr}</td>
                    <td>${event.event_type}</td>
                    <td>${event.camera_id}</td>
                    <td>${event.object_id || '-'}</td>
                    <td>${event.zone_id || '-'}</td>
                    <td>${position}</td>
                    <td>${movement}</td>
                    <td>${(event.confidence * 100).toFixed(0)}%</td>
                </tr>
            `;
        }).join('');

    } catch (error) {
        console.error('Failed to load event history:', error);
        const tbody = document.getElementById('event-history-body');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #ef4444;">데이터 로드 실패: ${error.message}</td></tr>`;
        }
    }
}

/**
 * Load System Statistics
 */
async function loadSystemStats() {
    try {
        const response = await fetch(`${API_URL}/api/system/health`);
        if (!response.ok) return;

        const data = await response.json();

        // Update active objects count
        if (data.components && data.components.movement_tracker) {
            const activeCount = data.components.movement_tracker.active_objects || 0;
            document.getElementById('active-objects').textContent = activeCount;
            eventStats.activeObjects = activeCount;
        }

        // Update zones count
        if (data.components && data.components.event_detector) {
            const zonesCount = data.components.event_detector.zones_count || 2;
            document.getElementById('active-zones').textContent = zonesCount;
        }

    } catch (error) {
        console.error('Failed to load system stats:', error);
    }
}

/**
 * Update Event Statistics
 */
function updateEventStats() {
    const now = Date.now();

    // Update total events
    document.getElementById('total-events').textContent = eventStats.totalEvents;

    // Clean up old timestamps (older than 60 seconds)
    recentEventTimestamps = recentEventTimestamps.filter(
        ts => (now - ts) <= 60000
    );

    // Calculate accurate events per minute
    eventStats.eventsPerMin = recentEventTimestamps.length;
    document.getElementById('events-per-min').textContent = eventStats.eventsPerMin;
}

// Attach event monitoring functions to window
window.initEventMonitoring = initEventMonitoring;

// Attach AI functions to window for button onclick
window.detectMotion = detectMotion;
window.detectPerson = detectPerson;
window.setStructureBaseline = setStructureBaseline;
window.detectStructure = detectStructure;
window.analyzeScene = analyzeScene;
window.analyzeAnomaly = analyzeAnomaly;

// Initialize on DOM loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
