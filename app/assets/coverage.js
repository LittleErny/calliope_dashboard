window.dash_clientside = Object.assign({}, window.dash_clientside, {
    coverage: {
        fullscreen: async function(clicks, id) {
            const card = document.getElementById('coverage-card-' + id.location);
            if (!card) return window.dash_clientside.no_update;
            if (document.fullscreenElement) await document.exitFullscreen();
            else await card.requestFullscreen();
            return 'Toggle full screen · Esc to exit';
        }
    }
});
document.addEventListener('fullscreenchange', function() {
    // Plotly must measure the chart again after entering or leaving full screen.
    requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
});
