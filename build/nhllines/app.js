// Global state
let allRecommendations = [];
let allOddsData = {};
let currentStake = 1.0;
let filtersSetUp = false;
let currentFilters = {
    grade: 'all',
    type: 'all',
    book: 'all',
    sortBy: 'edge'
};

// Tab switching
function showTab(tabName) {
    document.getElementById('today-tab').style.display = 'none';
    document.getElementById('performance-tab').style.display = 'none';
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));

    if (tabName === 'today') {
        document.getElementById('today-tab').style.display = 'block';
        document.querySelectorAll('.tab-button')[0].classList.add('active');
    } else if (tabName === 'performance') {
        document.getElementById('performance-tab').style.display = 'block';
        document.querySelectorAll('.tab-button')[1].classList.add('active');
        loadPerformanceData();
    }
}

// Load and display NHL betting analysis
async function loadAnalysis() {
    try {
        const response = await fetch(`latest_analysis.json?v=${Date.now()}`);
        if (!response.ok) {
            throw new Error(`Failed to load data: ${response.status} ${response.statusText}`);
        }
        const data = await response.json();
        displayAnalysis(data);
        document.getElementById('loading').style.display = 'none';
        showTab('today');
    } catch (error) {
        console.error('Error loading analysis:', error);
        document.getElementById('loading').style.display = 'none';
        const errorDiv = document.getElementById('error');
        errorDiv.style.display = 'block';
        errorDiv.innerHTML = `<p>Error: ${error.message}</p><p style="font-size:0.85rem;margin-top:6px;opacity:0.7;">Check browser console for details.</p>`;
    }
}

// Load performance data
async function loadPerformanceData() {
    try {
        const ts = Date.now();
        const [resultsResponse, historyResponse] = await Promise.all([
            fetch(`bet_results.json?v=${ts}`),
            fetch(`analysis_history.json?v=${ts}`)
        ]);
        let results = resultsResponse.ok ? await resultsResponse.json() : null;
        let history = historyResponse.ok ? await historyResponse.json() : null;
        displayPerformance(results, history);
    } catch (error) {
        console.error('Error loading performance data:', error);
        displayNoPerformanceData();
    }
}

function displayPerformance(results, history) {
    if (!results || !results.results || Object.keys(results.results).length === 0) {
        displayNoPerformanceData();
        return;
    }

    const resolvedBets = Object.values(results.results);
    const wonBets = resolvedBets.filter(r => r.result === 'won');
    const totalBets = resolvedBets.length;
    const winRate = (wonBets.length / totalBets * 100).toFixed(1);
    const totalStaked = resolvedBets.reduce((sum, r) => sum + r.bet.stake, 0);
    const totalProfit = resolvedBets.reduce((sum, r) => sum + r.profit, 0);
    const roi = (totalProfit / totalStaked * 100).toFixed(1);

    document.getElementById('perf-total-bets').textContent = totalBets;
    document.getElementById('perf-win-rate').textContent = `${winRate}%`;
    document.getElementById('perf-roi').textContent = `${roi}%`;
    document.getElementById('perf-profit').textContent = `$${totalProfit.toFixed(2)}`;

    const expectedGain = resolvedBets.reduce((sum, r) => sum + (r.bet.stake || 0.5) * r.bet.edge, 0);
    const difference = totalProfit - expectedGain;

    document.getElementById('expected-gain').textContent = `$${expectedGain.toFixed(2)}`;
    document.getElementById('actual-gain').textContent = `$${totalProfit.toFixed(2)}`;

    const diffEl = document.getElementById('gain-difference');
    diffEl.textContent = `${difference >= 0 ? '+' : ''}$${difference.toFixed(2)}`;
    diffEl.className = `big-number ${difference >= 0 ? 'positive' : 'negative'}`;

    displayGradePerformance(resolvedBets);
    displayRecentResults(resolvedBets);
    displayProfitChart(resolvedBets);
}

function displayGradePerformance(resolvedBets) {
    const grades = {};
    resolvedBets.forEach(r => {
        const grade = getGrade(r.bet.edge);
        if (!grades[grade]) grades[grade] = { bets: [], won: 0, staked: 0, profit: 0 };
        grades[grade].bets.push(r);
        grades[grade].staked += r.bet.stake;
        grades[grade].profit += r.profit;
        if (r.result === 'won') grades[grade].won++;
    });

    const container = document.getElementById('grade-performance-list');
    container.innerHTML = ['A', 'B+', 'B', 'C+'].filter(g => grades[g]).map(grade => {
        const d = grades[grade];
        const winRate = (d.won / d.bets.length * 100).toFixed(1);
        const roi = (d.profit / d.staked * 100).toFixed(1);
        const gc = getGradeClass(grade);
        return `
            <div class="grade-performance-item">
                <div class="grade-performance-badge ${gc}">${grade}</div>
                <div class="grade-performance-stats">
                    <div class="grade-stat">
                        <span class="grade-stat-label">Bets</span>
                        <span class="grade-stat-value">${d.bets.length}</span>
                    </div>
                    <div class="grade-stat">
                        <span class="grade-stat-label">Win Rate</span>
                        <span class="grade-stat-value">${winRate}%</span>
                    </div>
                    <div class="grade-stat">
                        <span class="grade-stat-label">ROI</span>
                        <span class="grade-stat-value ${d.profit >= 0 ? 'positive' : 'negative'}">${roi}%</span>
                    </div>
                    <div class="grade-stat">
                        <span class="grade-stat-label">Profit</span>
                        <span class="grade-stat-value ${d.profit >= 0 ? 'positive' : 'negative'}">$${d.profit.toFixed(2)}</span>
                    </div>
                </div>
            </div>`;
    }).join('');
}

function displayRecentResults(resolvedBets) {
    const container = document.getElementById('recent-results-list');
    const sorted = [...resolvedBets].sort((a, b) => {
        return new Date(b.bet.analysis_timestamp || b.checked_at || 0) -
               new Date(a.bet.analysis_timestamp || a.checked_at || 0);
    });
    container.innerHTML = sorted.slice(0, 20).map(r => {
        const grade = getGrade(r.bet.edge);
        const gc = getGradeClass(grade);
        const icon = r.result === 'won' ? '✅' : '❌';
        const betDate = new Date(r.bet.analysis_timestamp || r.checked_at);
        const dateStr = betDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        return `
            <div class="result-item">
                <div class="result-icon">${icon}</div>
                <div class="result-details">
                    <div class="result-pick">${r.bet.pick}</div>
                    <div class="result-game">${r.bet.game}</div>
                </div>
                <div class="result-date">${dateStr}</div>
                <div class="result-grade ${gc}">${grade}</div>
                <div class="result-profit ${r.profit >= 0 ? 'positive' : 'negative'}">
                    ${r.profit >= 0 ? '+' : ''}$${r.profit.toFixed(2)}
                </div>
            </div>`;
    }).join('');
}

let profitChartInstance = null;
let allSortedBets = []; // Store all bets for range filtering

function getBetDate(r) {
    // Use game_result.date first (actual game date), then analysis_timestamp, then checked_at
    if (r.game_result && r.game_result.date) return new Date(r.game_result.date + 'T12:00:00');
    if (r.bet.analysis_timestamp) return new Date(r.bet.analysis_timestamp);
    return new Date(r.checked_at || 0);
}

function displayProfitChart(resolvedBets) {
    // Sort all bets chronologically by game date
    allSortedBets = [...resolvedBets].sort((a, b) => {
        return getBetDate(a) - getBetDate(b);
    });

    renderProfitChart(allSortedBets);
}

function setChartRange(range) {
    // Update active button
    document.querySelectorAll('.range-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.range-btn[data-range="${range}"]`).classList.add('active');

    if (range === 'all' || allSortedBets.length === 0) {
        renderProfitChart(allSortedBets);
        return;
    }

    const now = new Date();
    let cutoff;
    if (range === 'day') {
        cutoff = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    } else if (range === 'week') {
        cutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    } else if (range === 'month') {
        cutoff = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    }

    // For filtered views, we need cumulative profit UP TO the cutoff as the starting point
    // Then show only bets within the range
    let priorProfit = 0;
    let priorExpected = 0;
    const filtered = [];

    allSortedBets.forEach(r => {
        const betDate = getBetDate(r);
        if (betDate < cutoff) {
            priorProfit += r.profit;
            priorExpected += r.bet.ev;
        } else {
            filtered.push(r);
        }
    });

    renderProfitChart(filtered, priorProfit, priorExpected);
}

function renderProfitChart(bets, startingProfit = 0, startingExpected = 0) {
    const canvas = document.getElementById('profit-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    if (bets.length === 0) {
        if (profitChartInstance) profitChartInstance.destroy();
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#6B7A8D';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No bets in this time range', canvas.width / 2, canvas.height / 2);
        return;
    }

    let cumProfit = startingProfit;
    let cumExpected = startingExpected;
    const labels = [];
    const profitData = [];
    const expectedData = [];
    const colors = [];

    bets.forEach((r, i) => {
        cumProfit += r.profit;
        cumExpected += (r.bet.stake || 0.5) * r.bet.edge;
        const date = getBetDate(r);
        // Show date for context
        const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        labels.push(label);
        profitData.push(parseFloat(cumProfit.toFixed(2)));
        expectedData.push(parseFloat(cumExpected.toFixed(2)));
        colors.push(r.result === 'won' ? '#00C896' : '#FF4D6A');
    });

    // Destroy previous chart if exists
    if (profitChartInstance) {
        profitChartInstance.destroy();
    }

    const ctx = canvas.getContext('2d');
    // Store bets reference for tooltip
    const chartBets = bets;
    profitChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Actual Profit',
                    data: profitData,
                    borderColor: '#007C85',
                    backgroundColor: 'rgba(0, 124, 133, 0.1)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointBackgroundColor: colors,
                    pointBorderColor: colors,
                    pointBorderWidth: 0,
                },
                {
                    label: 'Expected (EV)',
                    data: expectedData,
                    borderColor: '#F4901E',
                    borderDash: [6, 3],
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.3,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#B8C4D0',
                        font: { size: 12 },
                        usePointStyle: true,
                        padding: 16,
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(20, 25, 35, 0.95)',
                    titleColor: '#E8EDF2',
                    bodyColor: '#B8C4D0',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 10,
                    callbacks: {
                        afterBody: function(context) {
                            const idx = context[0].dataIndex;
                            const bet = chartBets[idx];
                            if (!bet) return '';
                            const icon = bet.result === 'won' ? 'W' : 'L';
                            return `${icon}: ${bet.bet.pick} (${bet.bet.game})\nP/L: ${bet.profit >= 0 ? '+' : ''}$${bet.profit.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#6B7A8D', font: { size: 10 }, maxRotation: 45 },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    ticks: {
                        color: '#6B7A8D',
                        callback: (v) => `$${v.toFixed(2)}`,
                    },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    title: {
                        display: true,
                        text: 'Cumulative Profit ($)',
                        color: '#6B7A8D',
                    }
                }
            }
        }
    });
}

function displayNoPerformanceData() {
    ['grade-performance-list', 'recent-results-list'].forEach(id => {
        document.getElementById(id).innerHTML = `
            <div class="no-data">
                <div class="no-data-icon">📊</div>
                <p>No performance data yet.</p>
                <p style="font-size:0.82rem;margin-top:6px;">
                    Run <code>python bet_tracker.py --check</code> to check bet results.
                </p>
            </div>`;
    });
    document.getElementById('perf-total-bets').textContent = '0';
    document.getElementById('perf-win-rate').textContent = '-';
    document.getElementById('perf-roi').textContent = '-';
    document.getElementById('perf-profit').textContent = '$0.00';
    document.getElementById('expected-gain').textContent = '$0.00';
    document.getElementById('actual-gain').textContent = '$0.00';
    document.getElementById('gain-difference').textContent = '$0.00';
}

function displayAnalysis(data) {
    const timestamp = new Date(data.timestamp);
    document.getElementById('timestamp').textContent = timestamp.toLocaleString('en-US', {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
    });
    document.getElementById('games-analyzed').textContent = data.games_analyzed.length;
    document.getElementById('bets-found').textContent = data.recommendations.length;

    if (data.recommendations.length > 0) {
        const totalStake = data.recommendations.length * data.stake;
        const totalEV = data.recommendations.reduce((sum, bet) => sum + bet.ev, 0);
        document.getElementById('expected-roi').textContent = `${(totalEV / totalStake * 100).toFixed(1)}%`;
    } else {
        document.getElementById('expected-roi').textContent = 'N/A';
    }

    // Store globals
    allRecommendations = data.recommendations;
    currentStake = data.stake || 1.0;
    allOddsData = data.all_odds || {};

    // Populate book filter with available books
    populateBookFilter(allRecommendations);

    // Setup filter listeners
    setupFilters();
    displayRecommendations(allRecommendations, currentStake);
    displayGames(data.games_analyzed);
}

function setupFilters() {
    if (filtersSetUp) return;
    filtersSetUp = true;
    document.getElementById('filter-grade').addEventListener('change', (e) => {
        currentFilters.grade = e.target.value;
        applyFilters();
    });
    document.getElementById('filter-type').addEventListener('change', (e) => {
        currentFilters.type = e.target.value;
        applyFilters();
    });

    document.getElementById('filter-book').addEventListener('change', (e) => {
        currentFilters.book = e.target.value;
        applyFilters();
    });

    document.getElementById('sort-by').addEventListener('change', (e) => {
        currentFilters.sortBy = e.target.value;
        applyFilters();
    });
}

function applyFilters() {
    let filtered = [...allRecommendations];
    if (currentFilters.grade !== 'all') {
        filtered = filtered.filter(bet => getGrade(bet.edge) === currentFilters.grade);
    }
    if (currentFilters.type !== 'all') {
        filtered = filtered.filter(bet => bet.bet_type === currentFilters.type);
    }

    // Filter by book
    if (currentFilters.book !== 'all') {
        filtered = filtered.filter(bet => bet.book === currentFilters.book);
    }

    // Sort
    if (currentFilters.sortBy === 'edge') {
        filtered.sort((a, b) => b.edge - a.edge);
    } else if (currentFilters.sortBy === 'roi') {
        filtered.sort((a, b) => b.roi - a.roi);
    } else if (currentFilters.sortBy === 'confidence') {
        filtered.sort((a, b) => b.confidence - a.confidence);
    } else if (currentFilters.sortBy === 'book') {
        // Sort by book name alphabetically, with theScore first
        filtered.sort((a, b) => {
            if (a.book === 'thescore') return -1;
            if (b.book === 'thescore') return 1;
            return a.book.localeCompare(b.book);
        });
    }
    displayRecommendations(filtered, currentStake);
}

function populateBookFilter(recommendations) {
    const bookSelect = document.getElementById('filter-book');
    const books = [...new Set(recommendations.map(bet => bet.book))].sort();

    // Clear existing options except "All Books"
    bookSelect.innerHTML = '<option value="all">All Books</option>';

    // Add theScore first if it exists
    if (books.includes('thescore')) {
        const option = document.createElement('option');
        option.value = 'thescore';
        option.textContent = 'theScore Bet';
        bookSelect.appendChild(option);
    }

    // Add other books
    books.filter(book => book !== 'thescore').forEach(book => {
        const option = document.createElement('option');
        option.value = book;
        option.textContent = formatBookName(book);
        bookSelect.appendChild(option);
    });
}

function formatBookName(book) {
    const names = {
        'fanduel': 'FanDuel',
        'draftkings': 'DraftKings',
        'betmgm': 'BetMGM',
        'caesars': 'Caesars',
        'pointsbet': 'PointsBet',
        'bet365': 'Bet365',
        'pinnacle': 'Pinnacle',
        'betrivers': 'BetRivers',
        'thescore': 'theScore',
        'williamhill': 'William Hill',
        'unibet': 'Unibet',
        'superbook': 'SuperBook',
        'bovada': 'Bovada',
        'betonlineag': 'BetOnline',
        'lowvig': 'LowVig',
        'mybookieag': 'MyBookie',
        'betus': 'BetUS',
        'wynnbet': 'WynnBet',
        'betfred': 'BetFred',
        'espnbet': 'ESPN Bet',
        'fanatics': 'Fanatics',
        'fliff': 'Fliff',
        'hardrock': 'Hard Rock',
        'ballybet': 'Bally Bet',
        'hardrockbet': 'Hard Rock Bet',
    };
    return names[book.toLowerCase()] || book.charAt(0).toUpperCase() + book.slice(1);
}

function displayRecommendations(recommendations, stake) {
    const container = document.getElementById('recommendations-list');

    if (recommendations.length === 0) {
        container.innerHTML = `<div class="no-data" style="padding:24px;">
            <p style="color:var(--text-muted);">No +EV bets match your criteria.</p>
        </div>`;
        return;
    }

    const isCompact = document.getElementById('view-toggle')?.dataset.view === 'compact';
    container.innerHTML = recommendations.map((bet) => {
        const grade = getGrade(bet.edge);
        const gradeClass = getGradeClass(grade);
        const lineShoppingHtml = isCompact ? '' : renderLineShopping(bet);

        if (isCompact) {
            return `
            <div class="bet-card-compact">
                <div class="compact-left">
                    <span class="grade ${gradeClass}">${grade}</span>
                    <span class="bet-pick">${bet.pick}</span>
                    <span class="compact-game">${bet.game}</span>
                </div>
                <div class="compact-stats">
                    <div class="compact-stat"><span class="compact-stat-label">Edge</span><span class="compact-stat-value edge-val">${(bet.edge * 100).toFixed(1)}%</span></div>
                    <div class="compact-stat"><span class="compact-stat-label">ROI</span><span class="compact-stat-value roi-val">${(bet.roi * 100).toFixed(1)}%</span></div>
                    <div class="compact-stat"><span class="compact-stat-label">Odds</span><span class="compact-stat-value odds-val">${bet.odds > 0 ? '+' : ''}${bet.odds}</span></div>
                    <div class="compact-stat"><span class="compact-stat-label">Book</span><span class="compact-stat-value">${formatBookName(bet.book)}</span></div>
                    <div class="compact-stat"><span class="compact-stat-label">Model</span><span class="compact-stat-value">${(bet.true_prob * 100).toFixed(1)}%</span></div>
                    <div class="compact-stat"><span class="compact-stat-label">Implied</span><span class="compact-stat-value">${(bet.implied_prob * 100).toFixed(1)}%</span></div>
                    <div class="compact-stat"><span class="compact-stat-label">Conf</span><span class="compact-stat-value">${(bet.confidence * 100).toFixed(0)}%</span></div>
                </div>
            </div>`;
        }

        return `
            <div class="bet-card">
                <div class="bet-header">
                    <div>
                        <span class="grade ${gradeClass}">${grade}</span>
                        <span class="bet-pick">${bet.pick}</span>
                    </div>
                    <span style="font-size:0.78rem;color:var(--text-muted);font-weight:500;">${bet.game}</span>
                </div>
                <div class="bet-key-metrics">
                    <div class="key-metric">
                        <div class="key-metric-label">Edge</div>
                        <div class="key-metric-value edge-val">${(bet.edge * 100).toFixed(1)}%</div>
                    </div>
                    <div class="key-metric">
                        <div class="key-metric-label">ROI</div>
                        <div class="key-metric-value roi-val">${(bet.roi * 100).toFixed(1)}%</div>
                    </div>
                    <div class="key-metric">
                        <div class="key-metric-label">EV / $${stake.toFixed(2)}</div>
                        <div class="key-metric-value ev-val">$${(bet.stake * bet.roi).toFixed(2)}</div>
                    </div>
                    <div class="key-metric">
                        <div class="key-metric-label">Best Odds</div>
                        <div class="key-metric-value odds-val">${bet.odds > 0 ? '+' : ''}${bet.odds}</div>
                    </div>
                </div>

                <div class="bet-details-inline">
                    <div class="detail-item-inline">
                        <span class="detail-label">Type</span>
                        <span class="detail-value">${bet.bet_type}</span>
                    </div>
                    <div class="detail-item-inline">
                        <span class="detail-label">Best Book</span>
                        <span class="detail-value">${formatBookName(bet.book)}</span>
                    </div>
                    <div class="detail-item-inline">
                        <span class="detail-label">Model Prob</span>
                        <span class="detail-value">${(bet.true_prob * 100).toFixed(1)}%</span>
                    </div>
                    <div class="detail-item-inline">
                        <span class="detail-label">Implied Prob</span>
                        <span class="detail-value">${(bet.implied_prob * 100).toFixed(1)}%</span>
                    </div>
                    <div class="detail-item-inline">
                        <span class="detail-label">Confidence</span>
                        <span class="detail-value">${(bet.confidence * 100).toFixed(0)}%</span>
                    </div>
                </div>
                ${lineShoppingHtml}
            </div>`;
    }).join('');
}

function renderLineShopping(bet) {
    // Build line shopping from all_book_odds attached by main.py
    const bookOddsList = bet.all_book_odds || [];

    if (bookOddsList.length <= 1) {
        return ''; // No line shopping to show with only 1 book
    }

    // bookOddsList is already sorted best-first by main.py
    const bestOdds = bookOddsList[0].odds;

    return `
        <div class="line-shopping">
            <div class="line-shopping-header">
                <span class="line-shopping-title">Line Shopping</span>
            </div>
            <div class="line-shopping-grid">
                ${bookOddsList.map(item => {
                    const isBest = item.odds === bestOdds;
                    const displayBook = formatBookName(item.book);
                    const oddsDisplay = typeof item.odds === 'number'
                        ? `${item.odds > 0 ? '+' : ''}${item.odds}`
                        : item.odds;
                    const pointDisplay = item.point !== undefined ? ` (${item.point})` : '';
                    return `
                        <div class="line-shop-item ${isBest ? 'best-odds' : ''}">
                            <span class="line-shop-book">${displayBook}</span>
                            <span>
                                <span class="line-shop-odds">${oddsDisplay}${pointDisplay}</span>
                                ${isBest ? '<span class="line-shop-best-tag">Best</span>' : ''}
                            </span>
                        </div>`;
                }).join('')}
            </div>
        </div>`;
}

function displayGames(games) {
    const container = document.getElementById('games-list');

    container.innerHTML = games.map((game, index) => {
        const modelProbs = game.model_probs;
        const marketProbs = game.market_probs || null;
        const blendedProbs = game.blended_probs || modelProbs;
        const contextIndicators = game.context_indicators || {};

        return `
            <div class="game-card" onclick="toggleGameDetails(${index})">
                <div class="game-header">
                    ${game.game}
                    ${(game.n_bets || 0) > 0 ? `<span style="color:var(--sharks-orange);font-size:0.82rem;font-weight:600;"> · ${game.n_bets} +EV bet${game.n_bets > 1 ? 's' : ''}</span>` : ''}
                </div>

                ${renderContextIndicators(contextIndicators)}

                <div class="game-stats">
                    <div class="game-stat">
                        <div class="game-stat-label">Model Prediction</div>
                        <div class="game-stat-value">
                            ${game.home}: ${(modelProbs.home_win_prob * 100).toFixed(1)}%<br>
                            ${game.away}: ${(modelProbs.away_win_prob * 100).toFixed(1)}%
                        </div>
                    </div>
                    ${marketProbs ? `
                    <div class="game-stat">
                        <div class="game-stat-label">Market Odds</div>
                        <div class="game-stat-value">
                            ${game.home}: ${(marketProbs.home_win_prob * 100).toFixed(1)}%<br>
                            ${game.away}: ${(marketProbs.away_win_prob * 100).toFixed(1)}%
                        </div>
                    </div>
                    <div class="game-stat">
                        <div class="game-stat-label">Blended</div>
                        <div class="game-stat-value">
                            ${game.home}: ${(blendedProbs.home_win_prob * 100).toFixed(1)}%<br>
                            ${game.away}: ${(blendedProbs.away_win_prob * 100).toFixed(1)}%
                        </div>
                    </div>` : ''}
                    <div class="game-stat">
                        <div class="game-stat-label">Expected Total</div>
                        <div class="game-stat-value">
                            ${modelProbs.expected_total ? modelProbs.expected_total.toFixed(1) : '-'} goals
                            ${modelProbs.total_line ? `<br><span style="font-size:0.78rem;color:var(--text-muted);">Line: ${modelProbs.total_line}</span>` : ''}
                        </div>
                    </div>
                    <div class="game-stat">
                        <div class="game-stat-label">Model Confidence</div>
                        <div class="game-stat-value">
                            ${((modelProbs.confidence || 0) * 100).toFixed(0)}%
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width:${(modelProbs.confidence || 0) * 100}%"></div>
                            </div>
                        </div>
                    </div>
                    <div class="game-stat">
                        <div class="game-stat-label">Similar Games</div>
                        <div class="game-stat-value">${game.n_similar || modelProbs.n_games || '-'} games</div>
                    </div>
                </div>

                <div class="game-details-expanded" id="game-details-${index}">
                    ${renderGameDetails(game)}
                </div>
            </div>`;
    }).join('');
}

function renderContextIndicators(indicators) {
    if (!indicators || Object.keys(indicators).length === 0) return '';
    let badges = [];

    if (indicators.fatigue && indicators.fatigue.length > 0) {
        indicators.fatigue.forEach(item => {
            const icon = item.type === 'B2B' ? '😴' : '💪';
            const text = item.type === 'B2B' ? `${item.team} B2B` : `${item.team} Rested`;
            badges.push(`<span class="context-badge ${item.severity}"><span class="context-icon">${icon}</span>${text}</span>`);
        });
    }
    if (indicators.goalie && indicators.goalie.length > 0) {
        indicators.goalie.forEach(item => {
            if (item.type === 'hot') badges.push(`<span class="context-badge positive"><span class="context-icon">🔥</span>${item.team} G Hot (.${(item.value * 1000).toFixed(0)})</span>`);
            else if (item.type === 'cold') badges.push(`<span class="context-badge negative"><span class="context-icon">🧊</span>${item.team} G Cold (.${(item.value * 1000).toFixed(0)})</span>`);
            else if (item.type === 'advantage') badges.push(`<span class="context-badge positive"><span class="context-icon">🥅</span>${item.team} Goalie +${item.value.toFixed(0)}</span>`);
        });
    }
    if (indicators.injuries && indicators.injuries.length > 0) {
        indicators.injuries.forEach(item => {
            badges.push(`<span class="context-badge negative"><span class="context-icon">🏥</span>${item.team} Injuries -${item.impact.toFixed(0)}</span>`);
        });
    }
    if (indicators.splits && indicators.splits.length > 0) {
        indicators.splits.forEach(item => {
            const icon = item.severity === 'positive' ? '🏠' : '🛣️';
            let text = '';
            if (item.type === 'strong_home') text = `${item.team} Strong Home`;
            else if (item.type === 'weak_home') text = `${item.team} Weak Home`;
            else if (item.type === 'strong_road') text = `${item.team} Strong Road`;
            else if (item.type === 'weak_road') text = `${item.team} Weak Road`;
            badges.push(`<span class="context-badge ${item.severity}"><span class="context-icon">${icon}</span>${text}</span>`);
        });
    }
    if (badges.length === 0) return '';
    return `<div class="context-indicators">${badges.join('')}</div>`;
}

function renderGameDetails(game) {
    let html = '';

    // Goalie Matchup
    if (game.goalie_matchup && game.goalie_matchup.home && game.goalie_matchup.away) {
        html += `
            <div class="details-section">
                <h3>Goalie Matchup</h3>
                <div class="goalie-comparison">
                    <div class="goalie-card">
                        <div class="goalie-name">${game.home}: ${game.goalie_matchup.home.name}</div>
                        <div class="goalie-stats">
                            <div class="goalie-stat-row"><span class="goalie-stat-label">Recent SV% (L10)</span><span class="goalie-stat-value">.${(game.goalie_matchup.home.recent_save_pct * 1000).toFixed(0)}</span></div>
                            <div class="goalie-stat-row"><span class="goalie-stat-label">Recent GAA (L10)</span><span class="goalie-stat-value">${game.goalie_matchup.home.recent_gaa.toFixed(2)}</span></div>
                            <div class="goalie-stat-row"><span class="goalie-stat-label">Quality Starts</span><span class="goalie-stat-value">${game.goalie_matchup.home.recent_quality_starts}/10</span></div>
                        </div>
                        <div class="quality-score">${game.goalie_matchup.home.quality_score.toFixed(0)}</div>
                    </div>
                    <div class="goalie-card">
                        <div class="goalie-name">${game.away}: ${game.goalie_matchup.away.name}</div>
                        <div class="goalie-stats">
                            <div class="goalie-stat-row"><span class="goalie-stat-label">Recent SV% (L10)</span><span class="goalie-stat-value">.${(game.goalie_matchup.away.recent_save_pct * 1000).toFixed(0)}</span></div>
                            <div class="goalie-stat-row"><span class="goalie-stat-label">Recent GAA (L10)</span><span class="goalie-stat-value">${game.goalie_matchup.away.recent_gaa.toFixed(2)}</span></div>
                            <div class="goalie-stat-row"><span class="goalie-stat-label">Quality Starts</span><span class="goalie-stat-value">${game.goalie_matchup.away.recent_quality_starts}/10</span></div>
                        </div>
                        <div class="quality-score">${game.goalie_matchup.away.quality_score.toFixed(0)}</div>
                    </div>
                </div>
            </div>`;
    }

    // Home/Road Splits
    if (game.team_splits && game.team_splits.home && game.team_splits.away) {
        html += `
            <div class="details-section">
                <h3>Home/Road Splits (Last 10)</h3>
                <div class="splits-comparison">
                    <div class="split-card">
                        <div class="split-title">${game.home} at Home</div>
                        <div class="split-stats">
                            <div class="split-stat-row"><span class="split-stat-label">Win %</span><span class="split-stat-value">${(game.team_splits.home.win_pct * 100).toFixed(1)}%</span></div>
                            <div class="split-stat-row"><span class="split-stat-label">GF/G</span><span class="split-stat-value">${game.team_splits.home.gf_pg.toFixed(2)}</span></div>
                            <div class="split-stat-row"><span class="split-stat-label">GA/G</span><span class="split-stat-value">${game.team_splits.home.ga_pg.toFixed(2)}</span></div>
                            <div class="split-stat-row"><span class="split-stat-label">Goal Diff</span><span class="split-stat-value">${game.team_splits.home.goal_diff > 0 ? '+' : ''}${game.team_splits.home.goal_diff.toFixed(2)}</span></div>
                        </div>
                    </div>
                    <div class="split-card">
                        <div class="split-title">${game.away} on Road</div>
                        <div class="split-stats">
                            <div class="split-stat-row"><span class="split-stat-label">Win %</span><span class="split-stat-value">${(game.team_splits.away.win_pct * 100).toFixed(1)}%</span></div>
                            <div class="split-stat-row"><span class="split-stat-label">GF/G</span><span class="split-stat-value">${game.team_splits.away.gf_pg.toFixed(2)}</span></div>
                            <div class="split-stat-row"><span class="split-stat-label">GA/G</span><span class="split-stat-value">${game.team_splits.away.ga_pg.toFixed(2)}</span></div>
                            <div class="split-stat-row"><span class="split-stat-label">Goal Diff</span><span class="split-stat-value">${game.team_splits.away.goal_diff > 0 ? '+' : ''}${game.team_splits.away.goal_diff.toFixed(2)}</span></div>
                        </div>
                    </div>
                </div>
            </div>`;
    }

    // Injuries
    if (game.injuries && (game.injuries.home.impact_score > 0 || game.injuries.away.impact_score > 0)) {
        html += `
            <div class="details-section">
                <h3>Injury Impact</h3>
                <div class="injury-list">
                    ${game.injuries.home.impact_score > 0 ? `<div class="injury-item"><span class="injury-team">${game.home}</span><span class="injury-impact">-${game.injuries.home.impact_score.toFixed(1)} impact</span></div>` : ''}
                    ${game.injuries.away.impact_score > 0 ? `<div class="injury-item"><span class="injury-team">${game.away}</span><span class="injury-impact">-${game.injuries.away.impact_score.toFixed(1)} impact</span></div>` : ''}
                </div>
            </div>`;
    }

    // Advanced Stats
    if (game.advanced_stats && game.advanced_stats.home && game.advanced_stats.away) {
        html += `
            <div class="details-section">
                <h3>Advanced Stats</h3>
                <div class="advanced-stats-grid">
                    <div class="advanced-stat-card"><div class="advanced-stat-label">${game.home} xGF%</div><div class="advanced-stat-value">${game.advanced_stats.home.xGF_pct.toFixed(1)}%</div></div>
                    <div class="advanced-stat-card"><div class="advanced-stat-label">${game.away} xGF%</div><div class="advanced-stat-value">${game.advanced_stats.away.xGF_pct.toFixed(1)}%</div></div>
                    <div class="advanced-stat-card"><div class="advanced-stat-label">${game.home} Corsi%</div><div class="advanced-stat-value">${game.advanced_stats.home.corsi_pct.toFixed(1)}%</div></div>
                    <div class="advanced-stat-card"><div class="advanced-stat-label">${game.away} Corsi%</div><div class="advanced-stat-value">${game.advanced_stats.away.corsi_pct.toFixed(1)}%</div></div>
                    <div class="advanced-stat-card"><div class="advanced-stat-label">${game.home} PDO</div><div class="advanced-stat-value">${game.advanced_stats.home.pdo.toFixed(1)}</div></div>
                    <div class="advanced-stat-card"><div class="advanced-stat-label">${game.away} PDO</div><div class="advanced-stat-value">${game.advanced_stats.away.pdo.toFixed(1)}</div></div>
                </div>
            </div>`;
    }

    return html;
}

function toggleGameDetails(index) {
    document.querySelectorAll('.game-card')[index].classList.toggle('expanded');
}

function getGrade(edge) {
    if (edge >= 0.07) return 'A';
    if (edge >= 0.04) return 'B+';
    if (edge >= 0.03) return 'B';
    return 'C+';
}

function getGradeClass(grade) {
    return { 'A': 'grade-a', 'B+': 'grade-b-plus', 'B': 'grade-b', 'C+': 'grade-c-plus' }[grade] || 'grade-c-plus';
}

function toggleView() {
    const btn = document.getElementById('view-toggle');
    const current = btn.dataset.view || 'full';
    const next = current === 'full' ? 'compact' : 'full';
    btn.dataset.view = next;
    btn.textContent = next === 'compact' ? 'Full View' : 'Compact View';
    applyFilters();
}

// Load on page load
loadAnalysis();

// Auto-refresh every 5 minutes
setInterval(loadAnalysis, 5 * 60 * 1000);
