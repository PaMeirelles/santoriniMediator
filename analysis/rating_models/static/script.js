document.addEventListener('DOMContentLoaded', () => {
    const playerSelect = document.getElementById('player-select');
    const resultsBody = document.getElementById('results-body');
    const resultsHeader = document.getElementById('results-header');
    const loadingDiv = document.getElementById('loading');
    const resultsTable = document.getElementById('results-table');

    playerSelect.addEventListener('change', async (event) => {
        const selectedValue = event.target.value;
        if (!selectedValue) {
            resultsBody.innerHTML = '';
            resultsHeader.textContent = '';
            resultsTable.classList.add('hidden');
            return;
        }

        loadingDiv.classList.remove('hidden');
        resultsTable.classList.add('hidden');
        resultsBody.innerHTML = '';

        const [god, engine] = selectedValue.split('|');
        const url = `/api/player_analysis?god=${encodeURIComponent(god)}&engine=${encodeURIComponent(engine)}`;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            resultsHeader.textContent = `Performance Analysis for ${god} - ${engine}`;

            if (data.length === 0) {
                 resultsBody.innerHTML = '<tr><td colspan="4">No match data found for this player.</td></tr>';
            } else {
                data.forEach(item => {
                    const row = document.createElement('tr');

                    const opponentName = `${item.opponent_god} - ${item.opponent_engine}`;
                    const winRate = item.win_rate.toFixed(2);
                    // CHANGED KEY from h2h_elo to hypothetical_elo
                    const hypotheticalElo = item.hypothetical_elo.toFixed(2);

                    row.innerHTML = `
                        <td>${opponentName}</td>
                        <td>${item.matches}</td>
                        <td>${winRate}%</td>
                        <td>${hypotheticalElo}</td> `;
                    resultsBody.appendChild(row);
                });
            }

        } catch (error) {
            console.error('Error fetching player analysis:', error);
            resultsHeader.textContent = 'Error';
            resultsBody.innerHTML = '<tr><td colspan="4">Could not load data. Please check the console for errors.</td></tr>';
        } finally {
            loadingDiv.classList.add('hidden');
            resultsTable.classList.remove('hidden');
        }
    });

    resultsTable.classList.add('hidden');
});