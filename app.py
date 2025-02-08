from flask import Flask, jsonify
import requests
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tournament Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            background: linear-gradient(135deg, #0f172a 0%, #020617 100%);
            color: #e2e8f0;
            font-family: system-ui, -apple-system, sans-serif;
        }
        .card {
            background-color: rgba(30, 41, 59, 0.7);
            border: 1px solid #334155;
            backdrop-filter: blur(10px);
        }
    </style>
</head>
<body class="min-h-screen p-4">
    <div class="max-w-lg mx-auto space-y-4">
        <div class="card rounded-lg p-4">
            <h2 class="text-xl font-bold mb-3 text-white">Leaderboard</h2>
            <div id="leaderboard" class="space-y-2"></div>
        </div>

        <div class="card rounded-lg p-4">
            <h2 class="text-xl font-bold mb-3 text-white">Recent Results</h2>
            <div id="recentResults" class="space-y-2"></div>
        </div>

        <div class="text-center text-sm text-slate-400">
            Last Updated: <span id="lastUpdate"></span>
        </div>
    </div>

    <script>
        function updateDashboard() {
            fetch('/api/tournament-data')
                .then(response => response.json())
                .then(data => {
                    // Leaderboard
                    const leaderboard = document.getElementById('leaderboard');
                    leaderboard.innerHTML = data.players
                        .map((player, index) => {
                            const totalGames = player.wins + player.losses + player.ties;
                            return `
                                <div class="flex items-center justify-between bg-slate-700 p-2 rounded">
                                    <div class="flex items-center gap-2">
                                        <span class="text-slate-400 text-sm">#${index + 1}</span>
                                        <span class="font-medium">${player.name}</span>
                                    </div>
                                    <div class="text-sm">
                                        ${player.wins}/${player.losses}/${player.ties} (${totalGames}) ${player.points}pts
                                    </div>
                                </div>
                            `;
                        })
                        .join('');

                    // Recent Results
                    const recentResults = document.getElementById('recentResults');
                    recentResults.innerHTML = data.recentGames
                        .map(game => `
                            <div class="bg-slate-700 p-2 rounded">
                                <div class="flex justify-between text-sm">
                                    <span>${game.winner}</span>
                                    <span class="text-slate-400">defeated</span>
                                    <span>${game.loser}</span>
                                </div>
                                <div class="text-xs text-slate-400 mt-1">${game.machine}</div>
                            </div>
                        `)
                        .join('');

                    document.getElementById('lastUpdate').textContent = data.lastUpdate;
                })
                .catch(error => console.error('Error:', error));
        }

        updateDashboard();
        setInterval(updateDashboard, 30000);
    </script>
</body>
</html>
"""

def get_all_tournament_data():
    headers = {
        "Authorization": "Bearer 398|iF8fDvhExm4SCqqL0332CQ0mNM4pUvtLjGTsLqWx166917ab",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    games_response = requests.get(
        "https://app.matchplay.events/api/tournaments/177974/games",
        headers=headers
    )
    games_data = games_response.json()
    
    tournament_response = requests.get(
        "https://app.matchplay.events/api/tournaments/177974?includePlayers=1&includeArenas=1",
        headers=headers
    )
    tournament_data = tournament_response.json()
    
    return games_data, tournament_data

def convert_to_points(point_str):
    if point_str == "1.00":
        return 1
    elif point_str == "0.00":
        return -1
    return 0

@app.route('/api/tournament-data')
def get_tournament_stats():
    try:
        games_data, tournament_data = get_all_tournament_data()
        
        player_stats = defaultdict(lambda: {
            "name": "", 
            "wins": 0, 
            "losses": 0, 
            "ties": 0,
            "points": 0
        })
        
        machine_names = {arena['arenaId']: arena['name'] 
                        for arena in tournament_data['data']['arenas'] 
                        if arena['status'] == 'active'}
        
        # Build player name lookup
        for player in tournament_data['data']['players']:
            player_stats[player['playerId']]["name"] = player['name']
        
        recent_games = []  # Will store games in reverse chronological order
        
        # Process games
        for game in games_data['data']:
            machine_name = machine_names.get(game['arenaId'], f"Machine {game['arenaId']}")
            
            if game['resultPoints'] and any(point is not None for point in game['resultPoints']):
                winner = None
                loser = None
                
                for player_id, points in zip(game['playerIds'], game['resultPoints']):
                    if points is not None:
                        point_value = convert_to_points(points)
                        player_stats[player_id]["points"] += point_value
                        
                        if point_value == 1:
                            player_stats[player_id]["wins"] += 1
                            winner = player_stats[player_id]["name"]
                        elif point_value == -1:
                            player_stats[player_id]["losses"] += 1
                            loser = player_stats[player_id]["name"]
                        else:
                            player_stats[player_id]["ties"] += 1
                
                if winner and loser:
                    recent_games.insert(0, {
                        "winner": winner,
                        "loser": loser,
                        "machine": machine_name
                    })
        
        # Format player data for leaderboard
        players = [
            {
                "name": stats["name"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "ties": stats["ties"],
                "points": stats["points"],
                "total_games": stats["wins"] + stats["losses"] + stats["ties"]
            }
            for player_id, stats in player_stats.items()
            if stats["wins"] + stats["losses"] + stats["ties"] > 0
        ]
        
        # Sort players by points then by total games
        players.sort(key=lambda x: (-x["points"], -x["total_games"]))
        
        return jsonify({
            "players": players,
            "recentGames": recent_games[:20],
            "lastUpdate": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return HTML_TEMPLATE

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)