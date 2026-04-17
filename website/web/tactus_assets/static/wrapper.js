const page = document.body;
const metadataUrl = page.dataset.metadataUrl;
const finishUrl = page.dataset.finishUrl;
const sessionUrl = page.dataset.sessionUrl;

const statusBadge = document.getElementById('status-badge');
const finishState = document.getElementById('finish-state');
const expiresAt = document.getElementById('expires-at');
const finishButton = document.getElementById('finish-button');
const message = document.getElementById('message');
const sessionFrame = document.getElementById('session-frame');
const sessionOverlay = document.getElementById('session-overlay');
const overlayCard = sessionOverlay.querySelector('.overlay-card');
const overlayTitle = document.getElementById('overlay-title');
const overlayBody = document.getElementById('overlay-body');

let currentState = 'starting';
let finishRequested = false;
let pollTimer = null;

function formatTs(value) {
    if (!value) {
        return 'unknown';
    }
    return new Date(value * 1000).toLocaleString();
}

function setMessage(text, isError = false) {
    message.textContent = text || '';
    message.classList.toggle('error', Boolean(isError));
}

function stopPolling() {
    if (pollTimer !== null) {
        window.clearInterval(pollTimer);
        pollTimer = null;
    }
}

function showOverlay(title, body, tone = 'neutral') {
    overlayTitle.textContent = title;
    overlayBody.textContent = body;
    overlayCard.dataset.tone = tone;
    sessionOverlay.hidden = false;
}

function hideOverlay() {
    sessionOverlay.hidden = true;
    overlayCard.dataset.tone = 'neutral';
}

function disableSessionView(title, body, tone = 'neutral') {
    if (sessionFrame && !sessionFrame.classList.contains('is-hidden')) {
        sessionFrame.src = 'about:blank';
        sessionFrame.classList.add('is-hidden');
    }
    showOverlay(title, body, tone);
}

function enableSessionView() {
    if (sessionFrame) {
        if (sessionFrame.getAttribute('src') !== sessionUrl) {
            sessionFrame.src = sessionUrl;
        }
        sessionFrame.classList.remove('is-hidden');
    }
    hideOverlay();
}

function applyTerminalState(payload) {
    const terminalMessages = {
        stopped: {
            title: 'Capture completed',
            body: 'The interactive browser has been closed and the final page capture has been handed back to Lacus.',
            tone: 'done',
            message: 'The interactive session has completed.',
            error: false,
        },
        expired: {
            title: 'Session expired',
            body: 'The interactive browser has been closed because the session expired before a final capture was requested.',
            tone: 'error',
            message: 'This interactive session expired before the final capture was requested.',
            error: true,
        },
        error: {
            title: 'Session failed',
            body: 'The interactive browser is no longer available because the session entered an error state.',
            tone: 'error',
            message: 'The interactive session entered an error state.',
            error: true,
        },
    };

    const details = terminalMessages[payload.status] || terminalMessages.error;
    disableSessionView(details.title, details.body, details.tone);
    setMessage(details.message, details.error);
    stopPolling();
}

function updateUi(payload) {
    currentState = payload.status || 'unknown';
    finishRequested = Boolean(payload.finish_requested);
    statusBadge.dataset.state = currentState;
    statusBadge.textContent = currentState;
    finishState.textContent = finishRequested ? 'requested' : 'not requested';
    expiresAt.textContent = formatTs(payload.expires_at);

    const terminal = ['stopped', 'expired', 'error'].includes(currentState);
    finishButton.disabled = finishRequested || terminal;

    if (terminal) {
        applyTerminalState(payload);
        return;
    }

    if (finishRequested) {
        disableSessionView(
            'Finalizing capture',
            'The interactive browser has been closed while Lacus finalizes the capture result.',
            'pending',
        );
        setMessage('Capture requested. Waiting for the worker to finalize the result.');
        return;
    }

    enableSessionView();
    setMessage('');
}

async function refreshMetadata() {
    try {
        const response = await fetch(metadataUrl, {
            headers: { Accept: 'application/json' },
        });

        if (response.status === 404 && finishRequested) {
            currentState = 'stopped';
            applyTerminalState({ status: 'stopped' });
            return;
        }

        if (!response.ok) {
            const details = await response.text();
            throw new Error(details || `Metadata request failed with ${response.status}`);
        }

        const payload = await response.json();
        updateUi(payload);
    } catch (error) {
        setMessage(error.message || 'Unable to refresh session status.', true);
    }
}

finishButton.addEventListener('click', async () => {
    finishButton.disabled = true;
    finishRequested = true;
    disableSessionView(
        'Requesting final capture',
        'The interactive browser has been closed while Lacus requests the final capture.',
        'pending',
    );
    setMessage('Requesting final capture...');

    try {
        const response = await fetch(finishUrl, {
            method: 'POST',
            headers: { Accept: 'application/json' },
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || `Finish request failed with ${response.status}`);
        }
        updateUi(payload);
    } catch (error) {
        finishRequested = false;
        finishButton.disabled = false;
        if (!['stopped', 'expired', 'error'].includes(currentState)) {
            enableSessionView();
        }
        setMessage(error.message || 'Unable to request the final capture.', true);
    }
});

window.addEventListener('beforeunload', stopPolling);

refreshMetadata();
pollTimer = window.setInterval(refreshMetadata, 2000);