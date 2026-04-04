/* ── DOM ─────────────────────────────────── */
const video         = document.getElementById('videoElement');
const overlay       = document.getElementById('overlayCanvas');
const captureCanvas = document.getElementById('captureCanvas');
const ctx           = overlay.getContext('2d');
const capCtx        = captureCanvas.getContext('2d');
const camSel        = document.getElementById('camera-select');
const statusEl      = document.getElementById('statusText');
const countEl       = document.getElementById('detectionCounter');
const timeEl        = document.getElementById('timeOverlay');

const config = JSON.parse(document.getElementById('config-data').textContent);

let stream = null, loop = null, detections = 0;
const API  = config.api;
const RATE = config.rate;

// Inject CSS variables
for (const [k, v] of Object.entries(config)) {
    if (k.startsWith("c_")) {
        document.body.style.setProperty("--" + k.replace(/_/g, "-"), v);
    }
}

const DOT_OK  = '<span class="dot dot-green"></span>';
const DOT_ERR = '<span class="dot dot-red"></span>';

function setStatus(msg, err) {
    statusEl.innerHTML = (err ? DOT_ERR : DOT_OK) + msg;
}

/* ── Clock ──────────────────────────────── */
!function tick() {
    const d = new Date();
    timeEl.textContent = d.toLocaleTimeString('en-IN',{hour12:false}) + '  ' + d.toLocaleDateString('en-IN');
    setTimeout(tick, 1000);
}();

/* ── Camera enum ────────────────────────── */
async function init() {
    try {
        await navigator.mediaDevices.getUserMedia({video:true});
        const devs = (await navigator.mediaDevices.enumerateDevices())
            .filter(d => d.kind==='videoinput');
        camSel.innerHTML = '';
        devs.forEach((d,i) => {
            const o = document.createElement('option');
            o.value = d.deviceId;
            o.text  = d.label || 'Camera '+(i+1);
            camSel.appendChild(o);
        });
        devs.length ? startCam(devs[0].deviceId) : setStatus('NO CAMERAS',true);
    } catch(e) { setStatus('ACCESS DENIED',true); }
}

async function startCam(id) {
    if (stream) stream.getTracks().forEach(t=>t.stop());
    try {
        stream = await navigator.mediaDevices.getUserMedia(
            {video: id ? {deviceId:{exact:id}} : true});
        video.srcObject = stream;
        setStatus('LIVE STREAM ACTIVE', false);
        video.onloadedmetadata = () => {
            overlay.width = captureCanvas.width = video.videoWidth;
            overlay.height = captureCanvas.height = video.videoHeight;
            if (loop) clearInterval(loop);
            loop = setInterval(detect, RATE);
        };
    } catch(e) { setStatus('STREAM FAILED',true); }
}

camSel.addEventListener('change', e => startCam(e.target.value));

/* ── Detection loop ────────────────────── */
async function detect() {
    if (video.readyState !== video.HAVE_ENOUGH_DATA) return;
    capCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
    const img = captureCanvas.toDataURL('image/jpeg', 0.8);
    try {
        const r = await (await fetch(API, {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({image:img})
        })).json();
        ctx.clearRect(0, 0, overlay.width, overlay.height);
        if (r.detected && r.bbox) {
            const [x1,y1,x2,y2] = r.bbox;
            detections++;
            countEl.innerHTML = 'DETECTIONS: <strong>'+detections+'</strong>';
            // Box
            ctx.shadowColor = config.c_india_green;
            ctx.shadowBlur = 10;
            ctx.strokeStyle = config.c_india_green;
            ctx.lineWidth = 3;
            ctx.strokeRect(x1,y1,x2-x1,y2-y1);
            ctx.shadowBlur = 0;
            // Label
            const lbl = r.hazard_type + ' (' + r.confidence.toFixed(2) + ')';
            ctx.font = '600 15px "Roboto Mono", monospace';
            const w = ctx.measureText(lbl).width;
            const ly = Math.max(26, y1-8);
            ctx.fillStyle = 'rgba(27,42,74,0.88)';
            ctx.fillRect(x1, ly-16, w+14, 22);
            ctx.fillStyle = config.c_india_green;
            ctx.fillText(lbl, x1+7, ly);
            // Alert
            setStatus('DETECTED: '+r.hazard_type.toUpperCase(), true);
            setTimeout(() => setStatus('LIVE STREAM ACTIVE',false), 1200);
        }
    } catch(e) { console.error('Detect error:', e); }
}

init();
