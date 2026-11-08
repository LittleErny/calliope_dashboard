window.dash_clientside = Object.assign({}, window.dash_clientside, {
    timeWindow: {
        edit: function(draft, applied, from, to, timestamps, limits, previous, iso) {
            const api = window.dash_clientside;
            const no = api.no_update;
            const triggered = (api.callback_context.triggered[0] || {}).prop_id || '';
            const appliedTitle = 'Showing ' + timestamps[applied[0]] + ' – ' + timestamps[applied[1]];
            let message = '';
            let candidate = draft.slice();
            if (triggered.startsWith('time-start-input.') || triggered.startsWith('time-end-input.')) {
                const text = String(triggered.startsWith('time-start') ? from : to).trim().replace(' ', 'T');
                const valid = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(text);
                const date = new Date(text + ':00Z');
                if (!valid || Number.isNaN(date.getTime()) || date.toISOString().slice(0,16) !== text || text < iso[0] || text > iso[iso.length-1]) {
                    return [no, no, no, no, 'Check dates', true, no, no,
                        'Enter a valid model date: ' + iso[0].replace('T',' ') + ' – ' + iso[iso.length-1].replace('T',' '), appliedTitle];
                }
                let low = 0, high = iso.length;
                while (low < high) {
                    const mid = Math.floor((low + high) / 2);
                    if (iso[mid] < text) low = mid + 1;
                    else high = mid;
                }
                const isStart = triggered.startsWith('time-start');
                const exact = iso[low] === text;
                const position = isStart || exact ? low : Math.max(0, low-1);
                if (isStart) candidate = [position, Math.max(position, candidate[1])];
                else candidate = [Math.min(candidate[0], position), position];
                if (!exact) message = 'Snapped to an available model timestep.';
            }
            const range = api.timeWindow.normalize(candidate, previous, limits);
            if (range[0] !== candidate[0] || range[1] !== candidate[1]) message = 'Window limited to one calendar year.';
            const output = api.timeWindow.update(range, applied, timestamps, limits, previous);
            output[0] = range[0] === draft[0] && range[1] === draft[1] ? no : range;
            const startText = iso[range[0]].replace('T',' '), endText = iso[range[1]].replace('T',' ');
            return [...output, from === startText ? no : startText, to === endText ? no : endText, message, appliedTitle];
        },
        normalize: function(draft, previous, limits) {
            if (!draft || !limits.max_end.length) return draft;
            let [start, end] = draft;
            if (end > limits.max_end[start]) {
                if (previous && start === previous[0] && end !== previous[1]) {
                    // The end handle moved: keep it under the pointer and move
                    // the start to the earliest permissible timestep.
                    let low = 0, high = end;
                    while (low < high) {
                        const mid = Math.floor((low + high) / 2);
                        if (limits.max_end[mid] < end) low = mid + 1;
                        else high = mid;
                    }
                    start = low;
                } else {
                    end = limits.max_end[start];
                }
            }
            return [start, end];
        },
        update: function(draft, applied, timestamps, limits, previous) {
            if (!draft || !timestamps.length) return [draft, draft, '', '', 'No timesteps', true];
            const range = window.dash_clientside.timeWindow.normalize(draft, previous, limits);
            const corrected = range[0] !== draft[0] || range[1] !== draft[1];
            const unchanged = range[0] === applied[0] && range[1] === applied[1];
            const status = unchanged ? 'Applied' : 'Not applied';
            return [corrected ? range : window.dash_clientside.no_update, range,
                timestamps[range[0]], timestamps[range[1]], status, unchanged];
        }
    }
});
