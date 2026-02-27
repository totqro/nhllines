// Load and display NHL betting analysis
async function loadAnalysis() {
    try {
        const response = await fetch('latest_analysis.json');
        if (!response.ok) throw new Error('Failed to load data');
        
        const data = await response.json();
        displayAnalysis(data);
        
        document.getElementById('loading').style.display = 'none';
        document.getElementById('content').style.display = 'block';
    } catch (error) {
        console.error('Error loading analysis:', error);
        document.getElementById('loading').style.display = 'none';
        document.getElementById('error').style.display = 'block';
    }
}

function displayAnalysis(data) {
    // Update summary stats
    const timestamp = new Date(data.timestamp);
    document.getElementById('timestamp').textContent = timestamp.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
    
    document.getElementById('games-analyzed').textContent = data.games_analyzed.length;
    document.getElementById('bets-found').textContent = data.recommendations.length;
    
    // Calculate expected ROI
    if (data.recommendations.length > 0) {
        const totalStake = data.recommendations.length * data.stake;
        const totalEV = data.recommendations.reduce((sum, bet) => sum + bet.ev, 0);
        const roi = (totalEV / totalStake * 100).toFixed(1);
        document.getElementById('expected-roi').textContent = `${roi}%`;
    } else {
        document.getElementById('expected-roi').textContent = 'N/A';
    }
    
    // Display recommendations
    displayRecommendations(data.recommendations, data.stake);
    
    // Display game analysis
    displayGames(data.games_analyzed);
}

function displayRecommendations(recommendations, stake) {
    const container = document.getElementById('recommendations-list');
    
    if (recommendations.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">No +EV bets found for today\'s games.</p>';
        return;
    }
    
    container.innerHTML = recommendations.map((bet, index) => {
        const grade = getGrade(bet.edge);
        const gradeClass = getGradeClass(grade);
        
        return `
            <div class="bet-card">
                <div class="bet-header">
                    <div>
                        <span class="grade ${gradeClass}">${grade}</span>
                        <span class="bet-pick">${bet.pick}</span>
                    </div>
                </div>
                <div class="bet-details">
                    <div class="detail-item">
                        <span class="detail-label">Game</span>
                        <span class="detail-value">${bet.game}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Type</span>
                        <span class="detail-value">${bet.bet_type}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Book</span>
                        <span class="detail-value">${bet.book}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Odds</span>
                        <span class="detail-value">${bet.odds > 0 ? '+' : ''}${bet.odds}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Edge</span>
                        <span class="detail-value positive">${(bet.edge * 100).toFixed(1)}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Model Prob</span>
                        <span class="detail-value">${(bet.true_prob * 100).toFixed(1)}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Implied Prob</span>
                        <span class="detail-value">${(bet.implied_prob * 100).toFixed(1)}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">EV per $${stake}</span>
                        <span class="detail-value positive">$${bet.ev.toFixed(4)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">ROI</span>
                        <span class="detail-value positive">${(bet.roi * 100).toFixed(1)}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Confidence</span>
                        <span class="detail-value">${(bet.confidence * 100).toFixed(0)}%</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function displayGames(games) {
    const container = document.getElementById('games-list');
    
    container.innerHTML = games.map(game => {
        const modelProbs = game.model_probs;
        const marketProbs = game.market_probs;
        const blendedProbs = game.blended_probs;
        
        return `
            <div class="game-card">
                <div class="game-header">
                    ${game.game}
                    ${game.n_bets > 0 ? `<span style="color: #4caf50; font-size: 0.9rem;"> • ${game.n_bets} +EV bet${game.n_bets > 1 ? 's' : ''}</span>` : ''}
                </div>
                <div class="game-stats">
                    <div class="game-stat">
                        <div class="game-stat-label">Model Prediction</div>
                        <div class="game-stat-value">
                            ${game.home}: ${(modelProbs.home_win_prob * 100).toFixed(1)}%<br>
                            ${game.away}: ${(modelProbs.away_win_prob * 100).toFixed(1)}%
                        </div>
                    </div>
                    <div class="game-stat">
                        <div class="game-stat-label">Market Odds</div>
                        <div class="game-stat-value">
                            ${game.home}: ${(marketProbs.home_win_prob * 100).toFixed(1)}%<br>
                            ${game.away}: ${(marketProbs.away_win_prob * 100).toFixed(1)}%
                        </div>
                    </div>
                    <div class="game-stat">
                        <div class="game-stat-label">Blended Prediction</div>
                        <div class="game-stat-value">
                            ${game.home}: ${(blendedProbs.home_win_prob * 100).toFixed(1)}%<br>
                            ${game.away}: ${(blendedProbs.away_win_prob * 100).toFixed(1)}%
                        </div>
                    </div>
                    <div class="game-stat">
                        <div class="game-stat-label">Expected Total</div>
                        <div class="game-stat-value">
                            ${modelProbs.expected_total.toFixed(1)} goals
                            ${modelProbs.total_line ? `<br><span style="font-size: 0.85rem; color: #666;">Line: ${modelProbs.total_line}</span>` : ''}
                        </div>
                    </div>
                    <div class="game-stat">
                        <div class="game-stat-label">Model Confidence</div>
                        <div class="game-stat-value">
                            ${(modelProbs.confidence * 100).toFixed(0)}%
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${modelProbs.confidence * 100}%"></div>
                            </div>
                        </div>
                    </div>
                    <div class="game-stat">
                        <div class="game-stat-label">Similar Games</div>
                        <div class="game-stat-value">${game.n_similar} games</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function getGrade(edge) {
    if (edge >= 0.07) return 'A';
    if (edge >= 0.04) return 'B+';
    if (edge >= 0.03) return 'B';
    return 'C+';
}

function getGradeClass(grade) {
    const gradeMap = {
        'A': 'grade-a',
        'B+': 'grade-b-plus',
        'B': 'grade-b',
        'C+': 'grade-c-plus'
    };
    return gradeMap[grade] || 'grade-c-plus';
}

// Load analysis on page load
loadAnalysis();

// Auto-refresh every 5 minutes
setInterval(loadAnalysis, 5 * 60 * 1000);
