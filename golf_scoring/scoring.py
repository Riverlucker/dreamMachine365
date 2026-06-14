"""
Scoring calculations for the Golf Tournament Live Scoring App.
Defines golf rules for Stableford and Matchplay.
"""

def calculate_playing_handicap(whi: float, cr: float = None, slope: int = None, par: int = None, extra_strokes: int = 2) -> int:
    """
    Calculates the Course Handicap dynamically based on WHI, CR, Slope, and Par.
    Formula: Playing Handicap = round(WHI * (Slope / 113) + (CR - Par)) + extra_strokes
    """
    if cr is None or slope is None or par is None:
        # Fallback if course data is missing
        return round(whi) + extra_strokes
        
    ch = whi * (slope / 113.0) + (cr - par)
    return round(ch) + extra_strokes

def get_hole_handicap_strokes(playing_handicap: int, stroke_index: int, total_holes: int = 18) -> int:
    """
    Calculates the number of handicap strokes a player receives on a specific hole.
    Supports negative handicaps (plus handicaps) and values greater than the number of holes.
    """
    if playing_handicap is None:
        return 0
        
    if playing_handicap >= 0:
        # Regular handicap (extra strokes received)
        base = playing_handicap // total_holes
        rem = playing_handicap % total_holes
        if stroke_index <= rem:
            return base + 1
        else:
            return base
    else:
        # Plus handicap (strokes given back on the easiest holes)
        abs_hcp = abs(playing_handicap)
        base = abs_hcp // total_holes
        rem = abs_hcp % total_holes
        # The easiest holes have the highest stroke index (e.g. 18 is easiest, 1 is hardest)
        cutoff = total_holes - rem + 1
        if stroke_index >= cutoff:
            strokes_given_back = base + 1
        else:
            strokes_given_back = base
        return -strokes_given_back

def calculate_stableford_points(gross_score: int, par: int, handicap_strokes: int) -> tuple[int, int]:
    """
    Calculates Net and Gross Stableford points for a single hole.
    Returns (net_points, gross_points).
    If gross_score is None, 0, or negative (ball picked up), points are 0.
    """
    if gross_score is None or gross_score <= 0:
        return 0, 0
        
    # Net score = gross strokes minus handicap strokes received
    net_score = gross_score - handicap_strokes
    
    # Stableford points:
    # Net Double Bogey or worse (+2 or more over par) = 0 pts
    # Net Bogey (+1) = 1 pt
    # Net Par (0) = 2 pts
    # Net Birdie (-1) = 3 pts
    # Net Eagle (-2) = 4 pts
    # Net Albatross (-3) = 5 pts
    net_points = max(0, par + 2 - net_score)
    gross_points = max(0, par + 2 - gross_score)
    
    return int(net_points), int(gross_points)

def calculate_matchplay_status(
    player_a_scores: dict[int, int],  # {hole_number: gross_score}
    player_b_scores: dict[int, int],  # {hole_number: gross_score}
    course_holes: list[dict],         # list of {"hole": X, "par": Y, "index": Z}
    player_a_hcp: int,
    player_b_hcp: int,
    name_a: str = "Player A",
    name_b: str = "Player B"
) -> dict:
    """
    Calculates the status of a Matchplay matchup between two players.
    Compares net scores hole-by-hole.
    Returns a dict with status details.
    """
    total_holes = len(course_holes)
    holes_lookup = {h["hole"]: h for h in course_holes}
    
    a_wins = 0
    b_wins = 0
    halves = 0
    holes_played = 0
    
    hole_details = []
    
    for h_num in sorted(holes_lookup.keys()):
        hole = holes_lookup[h_num]
        si = hole["index"]
        par = hole["par"]
        
        strokes_a = get_hole_handicap_strokes(player_a_hcp, si, 18)
        strokes_b = get_hole_handicap_strokes(player_b_hcp, si, 18)
        
        score_a = player_a_scores.get(h_num)
        score_b = player_b_scores.get(h_num)
        
        # We can only compute a hole if both have entered scores
        if score_a is not None and score_a > 0 and score_b is not None and score_b > 0:
            net_a = score_a - strokes_a
            net_b = score_b - strokes_b
            holes_played += 1
            
            winner = None
            if net_a < net_b:
                a_wins += 1
                winner = "A"
            elif net_b < net_a:
                b_wins += 1
                winner = "B"
            else:
                halves += 1
                winner = "halved"
                
            hole_details.append({
                "hole": h_num,
                "par": par,
                "index": si,
                "score_a": score_a,
                "net_a": net_a,
                "score_b": score_b,
                "net_b": net_b,
                "winner": winner
            })
        else:
            hole_details.append({
                "hole": h_num,
                "par": par,
                "index": si,
                "score_a": score_a,
                "score_b": score_b,
                "winner": None
            })
            
    score_diff = a_wins - b_wins
    holes_remaining = total_holes - holes_played
    
    # Determine match state
    is_finished = False
    result_text = ""
    winner_team_point = None  # "A" for Player A win, "B" for Player B win, "halved" for tie
    
    # Check if a player is up by more holes than remaining
    if abs(score_diff) > holes_remaining:
        is_finished = True
        winner_team_point = "A" if score_diff > 0 else "B"
        result_text = f"{abs(score_diff)}&{holes_remaining}"
    elif holes_remaining == 0:
        is_finished = True
        if score_diff > 0:
            result_text = "1 Up"
            winner_team_point = "A"
        elif score_diff < 0:
            result_text = "1 Up"
            winner_team_point = "B"
        else:
            result_text = "Tied"
            winner_team_point = "halved"
    else:
        # Match is active
        if score_diff > 0:
            result_text = f"{name_a} {score_diff} up nach {holes_played}"
        elif score_diff < 0:
            result_text = f"{name_b} {abs(score_diff)} up nach {holes_played}"
        else:
            result_text = f"A/S nach {holes_played}" if holes_played > 0 else "Not Started"
            
    return {
        "is_finished": is_finished,
        "result_text": result_text,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "halves": halves,
        "holes_played": holes_played,
        "holes_remaining": holes_remaining,
        "score_diff": score_diff,
        "winner_team_point": winner_team_point,
        "hole_details": hole_details
    }


def compute_tournament_leaderboards(tournament: dict, scores: dict, courses_cache: dict) -> dict:
    """
    Computes player, team, and matchplay leaderboards.
    Returns aggregated stats for displays.
    """
    players = tournament.get("players", [])
    teams = {t["id"]: t for t in tournament.get("teams", [])}
    rounds = sorted(tournament.get("rounds", []), key=lambda x: x.get("sequence", 0))
    matchups = tournament.get("matchups", [])
    
    player_stats = {}
    for p in players:
        p_id = p["id"]
        t_id = p["team_id"]
        team = teams.get(t_id, {"name": "No Team", "color": "#7f8c8d"})
        
        player_stats[p_id] = {
            "id": p_id,
            "name": p["name"],
            "team_id": t_id,
            "team_name": team["name"],
            "team_color": team["color"],
            "handicap": p["handicap"],
            "rounds": {},  # round_id -> {net_points, gross_points, net_strokes, gross_strokes, holes_played, total_par}
            "total_net_points": 0,
            "total_gross_points": 0,
            "total_net_strokes": 0,
            "total_gross_strokes": 0,
            "total_holes_played": 0,
            "total_par_played": 0,
            "total_net_diff": 0,
            "total_gross_diff": 0
        }
        
    # Calculate player stats per round
    for rnd in rounds:
        rnd_id = rnd["id"]
        course_id = rnd["course_id"]
        course = courses_cache.get(course_id)
        
        if not course:
            continue
            
        course_holes = course.get("holes", [])
        total_holes = len(course_holes)
        
        for p_id in player_stats.keys():
            p_stats = player_stats[p_id]
            playing_hcp = tournament.get("playing_handicaps", {}).get(p_id, {}).get(course_id)
            if playing_hcp is None:
                cr = course.get("cr")
                slope = course.get("slope")
                total_par = sum(h["par"] for h in course_holes)
                playing_hcp = calculate_playing_handicap(p_stats["handicap"], cr, slope, total_par)
                
            r_net_points = 0
            r_gross_points = 0
            r_net_strokes = 0
            r_gross_strokes = 0
            r_holes_played = 0
            r_par_played = 0
            
            p_scores = scores.get(rnd_id, {}).get(p_id, {})
            
            for hole in course_holes:
                h_num = hole["hole"]
                par = hole["par"]
                si = hole["index"]
                
                h_score = p_scores.get(str(h_num))
                if h_score is not None and h_score > 0:
                    h_hcp_strokes = get_hole_handicap_strokes(playing_hcp, si, 18)
                    net_pts, gross_pts = calculate_stableford_points(h_score, par, h_hcp_strokes)
                    
                    r_net_points += net_pts
                    r_gross_points += gross_pts
                    
                    # Cap scores at Double Bogey (+2) for stats based on Stableford rules
                    gross_score_capped = min(h_score, par + 2)
                    net_score_capped = min(h_score - h_hcp_strokes, par + 2)
                    
                    r_gross_strokes += gross_score_capped
                    r_net_strokes += net_score_capped
                    r_holes_played += 1
                    r_par_played += par
                    
            p_stats["rounds"][rnd_id] = {
                "net_points": r_net_points,
                "gross_points": r_gross_points,
                "net_strokes": r_net_strokes,
                "gross_strokes": r_gross_strokes,
                "holes_played": r_holes_played,
                "total_par": r_par_played,
                "net_diff": r_net_strokes - r_par_played if r_holes_played > 0 else 0,
                "gross_diff": r_gross_strokes - r_par_played if r_holes_played > 0 else 0
            }
            
            p_stats["total_net_points"] += r_net_points
            p_stats["total_gross_points"] += r_gross_points
            p_stats["total_net_strokes"] += r_net_strokes
            p_stats["total_gross_strokes"] += r_gross_strokes
            p_stats["total_holes_played"] += r_holes_played
            p_stats["total_par_played"] += r_par_played
            p_stats["total_net_diff"] += (r_net_strokes - r_par_played) if r_holes_played > 0 else 0
            p_stats["total_gross_diff"] += (r_gross_strokes - r_par_played) if r_holes_played > 0 else 0

    # Calculate team stats
    team_stats = {}
    for t_id, team in teams.items():
        team_stats[t_id] = {
            "id": t_id,
            "name": team["name"],
            "color": team["color"],
            "total_net_points": 0,
            "total_gross_points": 0,
            "total_holes_played": 0,
            "total_net_diff": 0,
            "total_gross_diff": 0,
            "players": []
        }
        
    for p_id, p_stats in player_stats.items():
        t_id = p_stats["team_id"]
        if t_id in team_stats:
            team_stats[t_id]["total_net_points"] += p_stats["total_net_points"]
            team_stats[t_id]["total_gross_points"] += p_stats["total_gross_points"]
            team_stats[t_id]["total_holes_played"] += p_stats["total_holes_played"]
            team_stats[t_id]["total_net_diff"] += p_stats["total_net_diff"]
            team_stats[t_id]["total_gross_diff"] += p_stats["total_gross_diff"]
            team_stats[t_id]["players"].append(p_stats)
            
    # Sort team players by net points desc
    for t_id in team_stats:
        team_stats[t_id]["players"].sort(key=lambda x: x["total_net_points"], reverse=True)

    # Calculate matchups for Matchplay rounds
    matchplay_results = []
    for m in matchups:
        m_id = m["id"]
        r_id = m["round_id"]
        p_a_id = m["player_a_id"]
        p_b_id = m["player_b_id"]
        
        rnd = next((r for r in rounds if r["id"] == r_id), None)
        p_a = player_stats.get(p_a_id)
        p_b = player_stats.get(p_b_id)
        
        if rnd and p_a and p_b:
            course = courses_cache.get(rnd["course_id"])
            if course:
                # get playing handicap for A and B
                hcp_a = tournament.get("playing_handicaps", {}).get(p_a_id, {}).get(rnd["course_id"])
                if hcp_a is None:
                    total_par = sum(h["par"] for h in course["holes"])
                    hcp_a = calculate_playing_handicap(p_a["handicap"], course.get("cr"), course.get("slope"), total_par)
                hcp_b = tournament.get("playing_handicaps", {}).get(p_b_id, {}).get(rnd["course_id"])
                if hcp_b is None:
                    total_par = sum(h["par"] for h in course["holes"])
                    hcp_b = calculate_playing_handicap(p_b["handicap"], course.get("cr"), course.get("slope"), total_par)
                    
                # Get scores per hole
                scores_a = scores.get(r_id, {}).get(p_a_id, {})
                scores_b = scores.get(r_id, {}).get(p_b_id, {})
                
                # convert scores keys to ints
                scores_a_int = {int(k): v for k, v in scores_a.items()}
                scores_b_int = {int(k): v for k, v in scores_b.items()}
                
                m_status = calculate_matchplay_status(
                    scores_a_int, scores_b_int, course["holes"], hcp_a, hcp_b,
                    name_a=p_a["name"], name_b=p_b["name"]
                )
                
                matchplay_results.append({
                    "id": m_id,
                    "name": m.get("name", f"{p_a['name']} vs {p_b['name']}"),
                    "round_id": r_id,
                    "round_name": rnd["name"],
                    "player_a": p_a,
                    "player_b": p_b,
                    "status": m_status
                })
                
    return {
        "players": player_stats,
        "teams": team_stats,
        "matchplays": matchplay_results
    }

