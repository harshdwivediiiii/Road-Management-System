/* ── Counter animation for stat cards (once on load) ── */
(function() {
    var animated = {};

    function animateCounter(el) {
        if (animated[el.id]) return;
        var raw = el.textContent.trim();
        var isPercent = raw.endsWith('%');
        var numStr = raw.replace(/[^0-9.]/g, '');
        var target = parseFloat(numStr);
        if (isNaN(target) || target === 0) return;
        
        animated[el.id] = true;
        var duration = 1200;
        var startTime = performance.now();
        var isInt = target === Math.floor(target) && !isPercent;
        
        function fmt(n) {
            var s = isInt ? Math.round(n).toLocaleString() : n.toFixed(2);
            return isPercent ? s + '%' : s;
        }
        
        function step(now) {
            var t = Math.min((now - startTime) / duration, 1);
            var ease = 1 - Math.pow(1 - t, 3);
            el.textContent = fmt(target * ease);
            if (t < 1) {
                requestAnimationFrame(step);
            } else {
                el.textContent = raw; // Restore Dash's original exact string
            }
        }
        requestAnimationFrame(step);
    }

    var cardIds = ['card-total','card-pending','card-progress','card-fixed','card-high','card-rate'];
    var obs = new MutationObserver(function(mutations) {
        mutations.forEach(function(m) {
            var el = m.target.nodeType === 1 ? m.target : m.target.parentElement;
            if (el && cardIds.indexOf(el.id) !== -1) {
                animateCounter(el);
            }
        });
    });

    window.addEventListener('DOMContentLoaded', function() {
        obs.observe(document.body, {childList: true, characterData: true, subtree: true});
    });
})();
