const elements = {
    countdown: document.getElementById('countdown'),
    btnForceStart: document.getElementById('btn-force-start'),
    btnReplay: document.getElementById('btn-replay'),
    btnShowResults: document.getElementById('btn-show-results'),
    potsContainer: document.getElementById('pots-container'),
    teamsContainer: document.getElementById('teams-container'),
    
    stageIdle: document.getElementById('stage-idle'),
    idleTitle: document.getElementById('idle-title'),
    idleSubtitle: document.getElementById('idle-subtitle'),
    replayActions: document.getElementById('replay-actions'),
    stageActive: document.getElementById('stage-active'),
    stageFinished: document.getElementById('stage-finished'),
    
    currentPotLabel: document.getElementById('current-pot-label'),
    drawCard: document.getElementById('draw-card'),
    drawnPlayerName: document.getElementById('drawn-player-name'),
    drawnPlayerHc: document.getElementById('drawn-player-hc'),
    drawnTeamLabel: document.getElementById('drawn-team-label'),
    drawnCardBack: document.getElementById('drawn-card-back'),
};

let config = null;
let drawSequence = [];
let currentStep = 0;
let timerInterval = null;
let rouletteInterval = null;

// Audio context or simple sounds could be added here if desired

const urlParams = new URLSearchParams(window.location.search);
const drawId = urlParams.get('draw') || '45_Loch_Challenge';

async function init() {
    try {
        if (window.drawConfig) {
            config = window.drawConfig;
        } else {
            const configRes = await fetch(`${drawId}.json`);
            config = await configRes.json();
        }
        
        let existingResults = null;
        if (window.existingResults) {
            existingResults = window.existingResults;
        } else {
            try {
                const resRes = await fetch(`results_${drawId}.json`);
                if (resRes.ok) {
                    existingResults = await resRes.json();
                }
            } catch (e) {
                console.log("No existing results found.");
            }
        }

        renderPots();
        renderTeams();
        
        if (window.isStreamlit || urlParams.get('streamlit') === 'true') {
            if (elements.btnForceStart) elements.btnForceStart.style.display = 'none';
        }

        const scheduled = new Date(config.scheduled_time);
        const dateString = scheduled.toLocaleDateString('de-DE', {day: '2-digit', month: '2-digit', year: 'numeric'});
        const timeString = scheduled.toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'});
        const scheduleDateEl = document.getElementById('schedule-date');
        if (scheduleDateEl) scheduleDateEl.innerText = `(am ${dateString} um ${timeString} Uhr)`;

        const autoplay = urlParams.get('autoplay') === 'true' || window.autoplay === true;

        if (existingResults && existingResults.sequence) {
            // Draw already happened
            drawSequence = existingResults.sequence;
            if (autoplay) {
                // Reset UI and start replay directly
                currentStep = 0;
                renderPots();
                renderTeams();
                startDrawProcess(true);
            } else {
                showReplayPrompt();
            }
        } else {
            // Need to generate
            startTimer(new Date(config.scheduled_time));
        }

        elements.btnForceStart.addEventListener('click', () => {
            clearInterval(timerInterval);
            startDrawProcess();
        });

        elements.btnReplay.addEventListener('click', () => {
            // Reset UI and start replay
            currentStep = 0;
            renderPots();
            renderTeams();
            startDrawProcess(true);
        });
        
        elements.btnShowResults.addEventListener('click', () => {
            showFinishedState();
        });

    } catch (e) {
        console.error("Failed to initialize:", e);
    }
}

function startTimer(scheduledTime) {
    const updateTimer = () => {
        const now = new Date();
        const diff = scheduledTime - now;

        if (diff <= 0) {
            clearInterval(timerInterval);
            elements.countdown.innerText = "00:00:00";
            startDrawProcess();
            return;
        }

        const h = Math.floor(diff / (1000 * 60 * 60)).toString().padStart(2, '0');
        const m = Math.floor((diff / 1000 / 60) % 60).toString().padStart(2, '0');
        const s = Math.floor((diff / 1000) % 60).toString().padStart(2, '0');
        elements.countdown.innerText = `${h}:${m}:${s}`;
    };

    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
}

function renderPots() {
    elements.potsContainer.innerHTML = '';
    config.pots.forEach(pot => {
        const potEl = document.createElement('div');
        potEl.className = 'pot-item';
        potEl.id = `pot-${pot.id}`;
        
        const header = document.createElement('div');
        header.className = 'pot-header';
        header.innerHTML = `<span>${pot.name}</span><span class="pot-count" id="count-${pot.id}">${pot.players.length}</span>`;
        
        const playersDiv = document.createElement('div');
        playersDiv.className = 'pot-players';
        playersDiv.id = `players-${pot.id}`;
        
        pot.players.forEach(p => {
            const pEl = document.createElement('div');
            pEl.className = 'player-chip';
            pEl.id = `chip-${p.id}`;
            pEl.innerHTML = `<span>${p.name}</span><span>${p.handicap}</span>`;
            playersDiv.appendChild(pEl);
        });

        potEl.appendChild(header);
        potEl.appendChild(playersDiv);
        elements.potsContainer.appendChild(potEl);
    });
}

function renderTeams() {
    elements.teamsContainer.innerHTML = '';
    config.teams.forEach(team => {
        const teamEl = document.createElement('div');
        teamEl.className = 'team-card';
        teamEl.id = `team-${team.id}`;
        
        const header = document.createElement('div');
        header.className = 'team-header';
        header.style.backgroundColor = team.color;
        header.style.color = team.textColor;
        header.innerText = team.name;

        const playersDiv = document.createElement('div');
        playersDiv.className = 'team-players';
        playersDiv.id = `team-players-${team.id}`;

        teamEl.appendChild(header);
        teamEl.appendChild(playersDiv);
        elements.teamsContainer.appendChild(teamEl);
    });
}

async function startDrawProcess(isReplay = false) {
    elements.stageIdle.classList.add('hidden');
    elements.stageFinished.classList.add('hidden');
    elements.stageActive.classList.remove('hidden');
    
    if (!isReplay && drawSequence.length === 0) {
        generateDrawSequence();
        await saveResults();
    }
    
    currentStep = 0;
    runNextDrawStep();
}

function generateDrawSequence() {
    drawSequence = [];
    const pots = JSON.parse(JSON.stringify(config.pots));
    
    pots.forEach((pot, potIndex) => {
        // Shuffle players in this pot
        const shuffledPlayers = pot.players.sort(() => Math.random() - 0.5);
        // Do NOT shuffle teams to keep the original assignment order
        const orderedTeams = JSON.parse(JSON.stringify(config.teams));
        
        for (let i = 0; i < shuffledPlayers.length; i++) {
            drawSequence.push({
                pot: { id: pot.id, name: pot.name },
                player: shuffledPlayers[i],
                team: orderedTeams[i],
                isLastInPot: (i === shuffledPlayers.length - 1),
                potDrawIndex: potIndex + 1 // "Zieht 1. Spieler für Team x..."
            });
        }
    });
}

async function saveResults() {
    try {
        await fetch('/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ drawId: drawId, sequence: drawSequence, generated_at: new Date().toISOString() })
        });
    } catch (e) {
        console.error("Failed to save results", e);
    }
}

function runNextDrawStep() {
    if (currentStep >= drawSequence.length) {
        finishDraw();
        return;
    }

    const stepData = drawSequence[currentStep];
    
    // Highlight Pot & Team
    document.querySelectorAll('.pot-item').forEach(el => el.classList.remove('active'));
    const activePot = document.getElementById(`pot-${stepData.pot.id}`);
    if (activePot) activePot.classList.add('active');
    
    document.querySelectorAll('.team-card').forEach(el => el.classList.remove('highlighting'));
    const activeTeam = document.getElementById(`team-${stepData.team.id}`);
    if (activeTeam) activeTeam.classList.add('highlighting');

    elements.currentPotLabel.innerText = `Zieht ${stepData.potDrawIndex}. Teilnehmer für ${stepData.team.name} aus ${stepData.pot.name}...`;
    
    // Reset Card
    elements.drawCard.classList.remove('flipped', 'pop-out');
    elements.drawnCardBack.style.borderColor = 'rgba(255,255,255,0.1)';
    elements.drawnCardBack.style.boxShadow = 'none';

    // Roulette Animation
    if (rouletteInterval) clearInterval(rouletteInterval);
    const availableChips = Array.from(document.querySelectorAll(`#players-${stepData.pot.id} .player-chip:not(.drawn)`));
    if (availableChips.length > 1) {
        let rouletteIdx = 0;
        rouletteInterval = setInterval(() => {
            availableChips.forEach(c => c.classList.remove('highlighting'));
            availableChips[rouletteIdx].classList.add('highlighting');
            rouletteIdx = (rouletteIdx + 1) % availableChips.length;
        }, 150);
    } else if (availableChips.length === 1) {
        availableChips[0].classList.add('highlighting');
    }

    // Wait for suspense (faster if last in pot)
    let suspenseTime = stepData.isLastInPot ? 800 : 3500;
    setTimeout(() => {
        if (rouletteInterval) clearInterval(rouletteInterval);
        document.querySelectorAll('.player-chip').forEach(c => c.classList.remove('highlighting'));
        
        // Highlight actual drawn player right before revealing
        const actualChip = document.getElementById(`chip-${stepData.player.id}`);
        if (actualChip) actualChip.classList.add('highlighting');
        
        revealCard(stepData);
    }, suspenseTime);
}

function revealCard(stepData) {
    // Populate back of card
    elements.drawnPlayerName.innerText = stepData.player.name;
    elements.drawnPlayerHc.innerText = parseFloat(stepData.player.handicap).toFixed(1);
    elements.drawnTeamLabel.innerText = stepData.team.name;
    elements.drawnTeamLabel.style.backgroundColor = stepData.team.color;
    elements.drawnTeamLabel.style.color = stepData.team.textColor;

    elements.drawnCardBack.style.borderColor = stepData.team.color;
    elements.drawnCardBack.style.boxShadow = `0 10px 40px ${stepData.team.color}66`;

    // Flip animation
    elements.drawCard.classList.add('flipped');

    // Cross out from pot
    const chip = document.getElementById(`chip-${stepData.player.id}`);
    if (chip) chip.classList.add('drawn');
    
    // Update Pot Count
    const countEl = document.getElementById(`count-${stepData.pot.id}`);
    if (countEl) countEl.innerText = parseInt(countEl.innerText) - 1;

    // Add to Team after short delay to let user read the card
    let readTime = stepData.isLastInPot ? 1500 : 3000;
    setTimeout(() => {
        elements.drawCard.classList.add('pop-out');
        
        setTimeout(() => {
            addPlayerToTeam(stepData);
            currentStep++;
            runNextDrawStep();
        }, 1000); // Time for pop-out animation
    }, readTime); // Time looking at the revealed card
}

function addPlayerToTeam(stepData) {
    const teamPlayersDiv = document.getElementById(`team-players-${stepData.team.id}`);
    const row = document.createElement('div');
    row.className = 'team-player-row';
    row.innerHTML = `<span>${stepData.player.name}</span><strong>${stepData.player.handicap}</strong>`;
    teamPlayersDiv.appendChild(row);
}

function finishDraw() {
    elements.stageActive.classList.add('hidden');
    elements.stageFinished.classList.remove('hidden');
    document.querySelectorAll('.pot-item').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.team-card').forEach(el => el.classList.remove('highlighting'));
}

function showReplayPrompt() {
    elements.stageIdle.classList.remove('hidden');
    elements.idleTitle.innerText = "Auslosung beendet!";
    elements.idleSubtitle.innerText = "Die Auslosung für dieses Event wurde bereits durchgeführt.";
    document.getElementById('timer-container').classList.add('hidden');
    elements.replayActions.classList.remove('hidden');
}

function showFinishedState() {
    elements.stageIdle.classList.add('hidden');
    elements.stageActive.classList.add('hidden');
    elements.stageFinished.classList.remove('hidden');
    document.getElementById('timer-container').classList.add('hidden');
    
    // Immediately populate teams and cross out pots without animation
    currentStep = drawSequence.length;
    renderPots();
    renderTeams();
    drawSequence.forEach(stepData => {
        addPlayerToTeam(stepData);
        const chip = document.getElementById(`chip-${stepData.player.id}`);
        if (chip) chip.classList.add('drawn');
        const countEl = document.getElementById(`count-${stepData.pot.id}`);
        if (countEl) countEl.innerText = parseInt(countEl.innerText) - 1;
    });
}

// Start
init();
