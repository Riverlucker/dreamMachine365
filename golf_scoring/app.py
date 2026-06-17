import streamlit as st
import os
import json
import importlib

import data_manager
importlib.reload(data_manager)

import scoring
importlib.reload(scoring)

# Set page configuration to wide layout and mobile friendly title
st.set_page_config(
    page_title="GolfScore Live",
    page_icon="⛳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load CSS and inject
def local_css(file_name):
    with open(file_name, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

css_path = os.path.join(os.path.dirname(__file__), "style.css")
if os.path.exists(css_path):
    local_css(css_path)

# Initialize Session State and Cookies
from streamlit_cookies_controller import CookieController
cookie_controller = CookieController()

if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False
if "is_scorer" not in st.session_state:
    st.session_state["is_scorer"] = False

# Try to load from cookies if session state is empty (useful on page reload)
admin_cookie = cookie_controller.get("is_admin") == "true"
if admin_cookie and not st.session_state.get("is_admin"):
    st.session_state["is_admin"] = True

scorer_cookie = cookie_controller.get("is_scorer") == "true"
if scorer_cookie and not st.session_state.get("is_scorer"):
    st.session_state["is_scorer"] = True

scorer_name_cookie = cookie_controller.get("scorer_name")
if scorer_name_cookie and not st.session_state.get("scorer_name"):
    st.session_state["scorer_name"] = scorer_name_cookie

# Get and sanitize event ID from query parameters
import re
event_id = st.query_params.get("event", "45_loch_challenge")
event_id = re.sub(r'[^a-zA-Z0-9_-]', '', event_id)
if not event_id:
    event_id = "45_loch_challenge"

# Load Tournament Config
tournament = data_manager.load_tournament(event_id)
if not tournament:
    st.error(f"Turnier '{event_id}' existiert nicht.")
    st.stop()
    
admin_pwd_correct = tournament.get("admin_password", "admin")
score_pwd_correct = tournament.get("score_password", "golf")

# Top Navigation
# Top Navigation

col1, col2 = st.columns([0.8, 0.2])
with col1:
    page = st.radio(
        "Navigation",
        ["🏆 Leaderboard", "✍️ Scores eingeben", "⚙️ Admin"],
        horizontal=True,
        label_visibility="collapsed"
    )
with col2:
    if st.session_state["is_admin"] or st.session_state["is_scorer"]:
        if st.button("Abmelden", use_container_width=True):
            st.session_state["is_admin"] = False
            st.session_state["is_scorer"] = False
            cookie_controller.remove("is_admin")
            cookie_controller.remove("is_scorer")
            cookie_controller.remove("scorer_name")
            st.rerun()

# Fix for Scorecard persisting when switching tabs
if page != "🏆 Leaderboard":
    if 'v_player' in st.query_params: del st.query_params['v_player']
    if 'v_round' in st.query_params: del st.query_params['v_round']

st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'/>", unsafe_allow_html=True)

# ----------------- AUTHENTICATION HELPER -----------------
def check_password(role="scorer"):
    """Returns True if the user has entered the correct password."""
    if role == "admin" and st.session_state["is_admin"]:
        return True
    if role == "scorer" and (st.session_state["is_scorer"] or st.session_state["is_admin"]):
        return True

    st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
    st.subheader(f"🔒 Passwortgeschützter Bereich ({'Admin' if role == 'admin' else 'Scoring'})")
    
    if role == "scorer":
        entered_username = st.text_input("Dein Name (min. 4 Zeichen):", key=f"usr_{role}")
    
    entered_password = st.text_input("Geben Sie das Passwort ein:", type="password", key=f"pwd_{role}")
    
    if st.button("Anmelden", key=f"btn_{role}"):
        if role == "scorer" and len(entered_username.strip()) < 4:
            st.error("Bitte gib einen Namen mit mindestens 4 Zeichen ein.")
            st.stop()
            
        if role == "admin" and entered_password == admin_pwd_correct:
            st.session_state["is_admin"] = True
            cookie_controller.set("is_admin", "true", max_age=86400*7)
            st.success("Erfolgreich als Admin angemeldet!")
            st.rerun()
        elif role == "scorer" and entered_password == score_pwd_correct:
            st.session_state["is_scorer"] = True
            st.session_state["scorer_name"] = entered_username.strip()
            cookie_controller.set("is_scorer", "true", max_age=86400*7)
            cookie_controller.set("scorer_name", entered_username.strip(), max_age=86400*7)
            st.success("Erfolgreich für Score-Eingabe angemeldet!")
            st.rerun()
        elif role == "scorer" and entered_password == admin_pwd_correct:
            st.session_state["is_admin"] = True
            st.session_state["scorer_name"] = entered_username.strip()
            cookie_controller.set("is_admin", "true", max_age=86400*7)
            cookie_controller.set("scorer_name", entered_username.strip(), max_age=86400*7)
            st.success("Erfolgreich als Admin angemeldet!")
            st.rerun()
        else:
            st.error("Falsches Passwort!")
    st.markdown("</div>", unsafe_allow_html=True)
    return False

def show_scorecard_page(p_id, r_id, tournament_data, scores_data, courses_cache_data, v_type="Netto"):
    player = next((p for p in tournament_data.get("players", []) if p["id"] == p_id), None)
    round_info = next((r for r in tournament_data.get("rounds", []) if r["id"] == r_id), None)
    
    if not player or not round_info:
        st.error("Spieler oder Runde nicht gefunden.")
        return
        
    c_id = round_info.get("course_id")
    course = courses_cache_data.get(c_id)
    if not course:
        st.error("Kurs nicht gefunden.")
        return
        
    whi = player.get("handicap", 0.0)
    playing_hcp = tournament_data.get("playing_handicaps", {}).get(p_id, {}).get(c_id, 0)
    
    # Parse name for the title
    name_parts = player['name'].split()
    if len(name_parts) > 1:
        last_name = name_parts[-1].upper()
        first_name = " ".join(name_parts[:-1]).upper()
        formatted_name = f"{last_name}, {first_name}"
    else:
        formatted_name = player['name'].upper()
        
    type_str = "Brutto-Scorekarte" if str(v_type).lower() == "brutto" else "Netto-Scorekarte"
    st.markdown(f"<h3 style='margin-top: -30px; margin-bottom: 20px;'>{type_str} {formatted_name} ( {whi} / {playing_hcp} ), {course['name']}</h3>", unsafe_allow_html=True)
    
    holes_row = ["Loch"]
    par_row = ["Par"]
    idx_row = ["Index"]
    vorgabe_row = ["Vorgabe"]
    gross_row = ["Schlagzahl"]
    pts_row = ["Punkte"]
    
    total_par = 0
    total_strokes = 0
    total_pts = 0
    
    r_scores = scores_data.get(r_id, {}).get(p_id, {})
    total_holes = 18 if len(course["holes"]) == 9 else len(course["holes"])
    
    for h in course["holes"]:
        hole_num = h["hole"]
        par = h["par"]
        idx = h["index"]
        
        strokes_received = scoring.get_hole_handicap_strokes(playing_hcp, idx, total_holes)
        
        gross = r_scores.get(str(hole_num), 0)
        net_pts, _ = scoring.calculate_stableford_points(gross, par, strokes_received)
        
        # Format Vorgabe as | or ||
        if strokes_received > 0:
            vorgabe_str = "|" * strokes_received
        elif strokes_received < 0:
            vorgabe_str = "-" * abs(strokes_received)
        else:
            vorgabe_str = ""
            
        if gross > 0:
            diff = gross - par
            score_class = ""
            if diff <= -2:
                score_class = "score-eagle"
            elif diff == -1:
                score_class = "score-birdie"
            elif diff == 1:
                score_class = "score-bogey"
            elif diff == 2:
                score_class = "score-double-bogey"
            elif diff >= 3:
                score_class = "score-triple-bogey"
                
            if score_class:
                gross_str = f"<div class='score-box {score_class}'><strong>{gross}</strong></div>"
            else:
                gross_str = f"<strong>{gross}</strong>"
            pts_str = str(net_pts)
        else:
            gross_str = "-"
            pts_str = "-"
        
        holes_row.append(str(hole_num))
        par_row.append(str(par))
        idx_row.append(str(idx))
        vorgabe_row.append(vorgabe_str)
        gross_row.append(gross_str)
        pts_row.append(f"<strong>{pts_str}</strong>")
        
        total_par += par
        if gross > 0:
            total_strokes += gross
            total_pts += net_pts
            
    # Add Gesamt
    holes_row.append("Gesamt")
    par_row.append(str(total_par))
    idx_row.append("")
    vorgabe_row.append("")
    gross_row.append(f"<strong>{total_strokes}</strong>")
    pts_row.append(f"<strong>{total_pts}</strong>")
    
    # Construct transposed HTML table
    html = "<div class='leaderboard-container' style='margin-top: 15px; overflow-x: auto;'><table class='leaderboard-table' style='width: 100%; text-align: center; font-size: 0.9rem;'>"
    
    rows = [holes_row, par_row, idx_row, gross_row, pts_row] if str(v_type).lower() == "brutto" else [holes_row, par_row, idx_row, vorgabe_row, gross_row, pts_row]
    for r_idx, row in enumerate(rows):
        # Add slight background to total column and labels
        bg_color = "rgba(0,0,0,0.06)" if r_idx % 2 == 0 else "rgba(0,0,0,0.01)"
        html += f"<tr style='background-color: {bg_color};'>"
        html += f"<td style='text-align:left; font-weight:bold;'>{row[0]}</td>"
        for val in row[1:-1]:
            html += f"<td>{val}</td>"
        html += f"<td style='background-color: rgba(0,0,0,0.04);'>{row[-1]}</td>"
        html += "</tr>"
        
    html += "</table></div>"
    st.markdown(html, unsafe_allow_html=True)
    
    if st.button("Schließen", use_container_width=True):
        if 'v_player' in st.query_params: del st.query_params['v_player']
        if 'v_round' in st.query_params: del st.query_params['v_round']
        st.rerun()

# ----------------- 🏆 LEADERBOARD PAGE -----------------
if page == "🏆 Leaderboard":
    st.title(f"🏆 {tournament.get('tournament_name', 'GolfScore Live')}")
    
    # Load latest tournament data & scores
    scores = data_manager.load_scores(event_id)
    
    # Load all courses into cache
    courses = data_manager.list_courses()
    courses_cache = {c["id"]: c for c in courses}
    data_manager.apply_course_modifications(courses_cache, event_id)
    
    # Check for scorecard dialog request
    v_player = st.query_params.get("v_player")
    v_round = st.query_params.get("v_round")
    v_type = st.query_params.get("v_type", "Netto")
    if v_player and v_round:
        show_scorecard_page(v_player, v_round, tournament, scores, courses_cache, v_type)
        st.stop()
    
    if not tournament.get("players"):
        st.warning("Das Turnier ist noch nicht konfiguriert. Bitte lade eine Setup-Datei im Admin-Bereich hoch.")
    else:
        # Calculate stats
        stats = scoring.compute_tournament_leaderboards(tournament, scores, courses_cache)
        
        # Round Selector
        rounds_list = sorted(tournament.get("rounds", []), key=lambda x: x.get("sequence", 0))
        round_options = ["Gesamt (Alle Runden)"] + [r["name"] for r in rounds_list]
        selected_round_name = st.selectbox("Runde auswählen:", round_options)
        
        # Determine active round details
        is_overall = selected_round_name == "Gesamt (Alle Runden)"
        active_round = None
        max_holes_player = 0
        
        if is_overall:
            for r in rounds_list:
                c_id = r.get("course_id")
                c_data = courses_cache.get(c_id, {})
                max_holes_player += len(c_data.get("holes", []))
        else:
            active_round = next((r for r in rounds_list if r["name"] == selected_round_name), None)
            if active_round:
                c_id = active_round.get("course_id")
                c_data = courses_cache.get(c_id, {})
                max_holes_player = len(c_data.get("holes", []))

        # Tab Selection via Radio buttons to persist state during page reloads
        has_matchplay = len(tournament.get("matchups", [])) > 0
        is_ryder_cup = tournament.get("is_ryder_cup", False)
        
        tab_options = []
        if is_ryder_cup:
            tab_options = ["🏆 Ryder Cup Scoreboard", "⚔️ Matchplay Duelle"]
        else:
            if event_id != "race_to_boathouse":
                tab_options.append("👥 Team Netto")
                
            tab_options.extend(["👤🏌️ Spieler Netto", "👤🏌️ Spieler Brutto"])
            
            if has_matchplay:
                tab_options.append("⚔️ Matchplay Duelle")
                
            if event_id == "45_loch_challenge":
                tab_options.append("🏆 Previous Winners")
                
        tab_team = tab_player_net = tab_player_gross = tab_matchplay = tab_winners = tab_ryder_cup = None
        
        if tab_options:
            tabs = st.tabs(tab_options)
            for name, tab in zip(tab_options, tabs):
                if name == "🏆 Ryder Cup Scoreboard":
                    tab_ryder_cup = tab
                elif name == "👥 Team Netto":
                    tab_team = tab
                elif name == "👤🏌️ Spieler Netto":
                    tab_player_net = tab
                elif name == "👤🏌️ Spieler Brutto":
                    tab_player_gross = tab
                elif name == "⚔️ Matchplay Duelle":
                    tab_matchplay = tab
                elif name == "🏆 Previous Winners":
                    tab_winners = tab

        # 🏆 Ryder Cup Scoreboard Tab
        if is_ryder_cup and tab_ryder_cup:
            with tab_ryder_cup:
                # Render Ryder Cup Tab
                st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
                st.subheader("🏆 The 2026 Ryder Cup")
                
                eu_score = 0.0
                us_score = 0.0
                
                html = "<div class='leaderboard-container'><table class='leaderboard-table' style='width:100%; border-collapse: collapse;'>"
                html += "<tbody>"
                
                m_list = stats.get("matchplays", [])
                
                for m in m_list:
                    status = m["status"]
                    winner_team_point = status.get("winner_team_point")
                    
                    eu_bg = "#ffffff"
                    us_bg = "#ffffff"
                    eu_color = "#000000"
                    us_color = "#000000"
                    
                    if winner_team_point == "A":
                        eu_score += 1.0
                        eu_bg = "#153075" # Deep blue
                        eu_color = "#ffffff"
                    elif winner_team_point == "B":
                        us_score += 1.0
                        us_bg = "#a81c2e" # Deep red
                        us_color = "#ffffff"
                    elif winner_team_point == "halved":
                        eu_score += 0.5
                        us_score += 0.5
                    
                    res_text = status['result_text']
                    # Style row
                    html += "<tr style='border-bottom: 1px solid #eee;'>"
                    
                    # Europe column
                    html += f"<td style='background-color: {eu_bg}; color: {eu_color}; padding: 10px; font-weight: bold; text-align: right; width: 40%;'>{m['player_a']['name']}</td>"
                    
                    # Middle Score column
                    html += f"<td style='background-color: #888888; color: #ffffff; text-align: center; font-weight: bold; width: 20%;'>{res_text}</td>"
                    
                    # USA column
                    html += f"<td style='background-color: {us_bg}; color: {us_color}; padding: 10px; font-weight: bold; text-align: left; width: 40%;'>{m['player_b']['name']}</td>"
                    
                    html += "</tr>"
                html += "</tbody></table></div>"
                st.markdown(html, unsafe_allow_html=True)
                
                # Bottom total bar
                html_total = "<div style='display: flex; margin-top: 10px; color: white; font-size: 1.2rem; font-weight: bold; border-radius: 5px; overflow: hidden;'>"
                html_total += f"<div style='background-color: #153075; width: 50%; padding: 10px; text-align: right;'>Europe &nbsp;&nbsp;&nbsp; {eu_score:g}</div>"
                html_total += f"<div style='background-color: #a81c2e; width: 50%; padding: 10px; text-align: left;'>{us_score:g} &nbsp;&nbsp;&nbsp; USA</div>"
                html_total += "</div>"
                st.markdown(html_total, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
        
            # 👥 Team Netto Tab
        if not is_ryder_cup and tab_team:
            with tab_team:
                # Render Team Tab
                st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
                st.subheader("👥 Team Netto Leaderboard")
            
                # Aggregate team points based on selection
                team_table_data = []
                for t_id, t in stats["teams"].items():
                    t_points = 0
                    t_holes = 0
                    t_diff = 0
                
                    for p in t["players"]:
                        if is_overall:
                            t_points += p["total_net_points"]
                            t_holes += p["total_holes_played"]
                            t_diff += p["total_net_diff"]
                        else:
                            r_stats = p["rounds"].get(active_round["id"], {})
                            t_points += r_stats.get("net_points", 0)
                            t_holes += r_stats.get("holes_played", 0)
                            t_diff += r_stats.get("net_diff", 0)
                        
                    team_table_data.append({
                        "name": t["name"],
                        "color": t["color"],
                        "points": t_points,
                        "holes": t_holes,
                        "diff": t_diff,
                        "players": t["players"]
                    })
                
                # Sort teams by Par-Diff asc, then points desc
                key_func = lambda x: (x["diff"], -x["points"])
                team_table_data.sort(key=key_func)
            
                ranks = []
                for i, t in enumerate(team_table_data):
                    rank = 1
                    for other in team_table_data:
                        if key_func(other) < key_func(t):
                            rank += 1
                    is_tied = sum(1 for o in team_table_data if key_func(o) == key_func(t)) > 1
                    rank_str = f"T{rank}" if is_tied else str(rank)
                    ranks.append((rank, rank_str))
            
                # Render Team Table
                html = "<div class='leaderboard-container'><table class='leaderboard-table'>"
                html += "<thead><tr><th>Rang</th><th>Team</th><th>Loch</th><th style='background-color:rgba(0,0,0,0.03); text-align:center; color:#0d522c; font-weight:900;'>PAR-DIFF</th></tr></thead><tbody>"
                for i, team_item in enumerate(team_table_data):
                    rank, rank_str = ranks[i]
                    rank_class = f"rank-{rank}" if rank <= 3 else "rank-other"
                
                    diff_val = team_item['diff']
                    diff_str = f"+{diff_val}" if diff_val > 0 else str(diff_val)
                    if diff_val == 0:
                        diff_str = "Even"
                    if team_item['holes'] == 0:
                        diff_str = "-"
                    
                    max_holes_team = max_holes_player * len(team_item['players'])
                    holes_str = f"{team_item['holes']} / {max_holes_team}"
                
                    html += "<tr>"
                    html += f"<td><span class='rank-badge {rank_class}'>{rank_str}</span></td>"
                    html += f"<td><span class='team-tag' style='background-color:{team_item['color']}'>{team_item['name']}</span></td>"
                    html += f"<td>{holes_str}</td>"
                    html += f"<td style='background-color:rgba(0,0,0,0.03); border-left:1px solid rgba(0,0,0,0.05); text-align:center;'><strong style='font-size:1.25rem; font-weight:900; color:#1a2b22;'>{diff_str}</strong> <br><span style='font-size:0.75rem;color:#666'>({team_item['points']} Pkt)</span></td>"
                    html += "</tr>"
                html += "</tbody></table></div>"
                st.markdown(html, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            
                # Detailed breakdown per team
                st.markdown("### Team Details")
                for team_item in team_table_data:
                    diff_val = team_item['diff']
                    diff_str = f"+{diff_val}" if diff_val > 0 else str(diff_val)
                    if diff_val == 0: diff_str = "Even"
                    if team_item['holes'] == 0: diff_str = "-"
                
                    with st.expander(f"Details: {team_item['name']} ({diff_str})"):
                        html_details = "<div class='leaderboard-container'><table class='leaderboard-table'>"
                        html_details += "<thead><tr><th>Spieler</th><th>HCP</th>"
                        if is_overall:
                            for r in rounds_list:
                                html_details += f"<th>{r['name'].split('-')[0].strip()}</th>"
                            html_details += "<th>Gesamt</th>"
                        else:
                            html_details += f"<th>{active_round['name']}</th>"
                        html_details += "</tr></thead><tbody>"
                    
                        for p in team_item["players"]:
                            html_details += f"<tr><td><strong>{p['name']}</strong></td><td>{p['handicap']}</td>"
                            if is_overall:
                                for r in rounds_list:
                                    r_stats = p["rounds"].get(r["id"], {})
                                    pts = r_stats.get("net_points", 0)
                                    holes = r_stats.get("holes_played", 0)
                                    link = f"?event={event_id}&v_player={p['id']}&v_round={r['id']}&v_type=netto"
                                    html_details += f"<td><a href='{link}' target='_self' style='text-decoration:none; color:inherit; display:block;'>{pts} <span style='font-size:0.75rem; color:#888;'>({holes}L)</span></a></td>"
                                html_details += f"<td><strong>{p['total_net_points']}</strong></td>"
                            else:
                                r_stats = p["rounds"].get(active_round["id"], {})
                                pts = r_stats.get("net_points", 0)
                                holes = r_stats.get("holes_played", 0)
                                link = f"?event={event_id}&v_player={p['id']}&v_round={active_round['id']}&v_type=netto"
                                html_details += f"<td><a href='{link}' target='_self' style='text-decoration:none; color:inherit; display:block;'><strong>{pts}</strong> <span style='font-size:0.75rem; color:#888;'>({holes}L)</span></a></td>"
                            html_details += "</tr>"
                        html_details += "</tbody></table></div>"
                        st.markdown(html_details, unsafe_allow_html=True)

            # 🏌️ Spieler Netto Tab
        if not is_ryder_cup and tab_player_net:
            with tab_player_net:
                # Render Player Net Tab
                st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
                st.subheader("🏌️ Einzelspieler Netto Leaderboard")
            
                player_list = list(stats["players"].values())
            
                if is_overall:
                    key_func = lambda x: (x["total_net_diff"], -x["total_net_points"])
                else:
                    key_func = lambda x: (x["rounds"].get(active_round["id"], {}).get("net_diff", 0), -x["rounds"].get(active_round["id"], {}).get("net_points", 0))
                
                player_list.sort(key=key_func)
            
                ranks = []
                for i, p in enumerate(player_list):
                    rank = 1
                    for other in player_list:
                        if key_func(other) < key_func(p):
                            rank += 1
                    is_tied = sum(1 for o in player_list if key_func(o) == key_func(p)) > 1
                    rank_str = f"T{rank}" if is_tied else str(rank)
                    ranks.append((rank, rank_str))
                
                # Render Player Net Table
                html = "<div class='leaderboard-container'><table class='leaderboard-table'>"
                html += f"<thead><tr><th>Rang</th><th>Spieler</th><th>HCP</th>"
                if is_overall:
                    for r in rounds_list:
                        html_details_name = r['name'].replace("Runde ", "R").split(" - ")[0]
                        html += f"<th>{html_details_name}</th>"
                    html += "<th>GES</th><th>Loch</th><th style='background-color:rgba(0,0,0,0.03); text-align:center; color:#0d522c; font-weight:900;'>PAR-DIFF</th></tr></thead><tbody>"
                else:
                    html += f"<th>Punkte</th><th>Loch</th><th style='background-color:rgba(0,0,0,0.03); text-align:center; color:#0d522c; font-weight:900;'>PAR-DIFF</th></tr></thead><tbody>"
                
                for i, p in enumerate(player_list):
                    rank, rank_str = ranks[i]
                    rank_class = f"rank-{rank}" if rank <= 3 else "rank-other"
                    team_tag = f"<span class='team-tag' style='background-color:{p['team_color']}'>{p['team_name']}</span>"
                
                    if is_overall:
                        total_pts = p["total_net_points"]
                        diff = p["total_net_diff"]
                        holes_played = p["total_holes_played"]
                    else:
                        r_stats = p["rounds"].get(active_round["id"], {})
                        total_pts = r_stats.get("net_points", 0)
                        diff = r_stats.get("net_diff", 0)
                        holes_played = r_stats.get("holes_played", 0)
                    
                    diff_str = f"+{diff}" if diff > 0 else str(diff)
                    if diff == 0:
                        diff_str = "Even"
                    if holes_played == 0:
                        diff_str = "-"
                    
                    html += "<tr>"
                    html += f"<td><span class='rank-badge {rank_class}'>{rank_str}</span></td>"
                    p_active_r_id = rounds_list[-1]['id'] if rounds_list else ""
                    for r in rounds_list:
                        c_id = r.get("course_id")
                        c_data = courses_cache.get(c_id, {})
                        max_h = len(c_data.get("holes", []))
                        r_stats = p["rounds"].get(r["id"], {})
                        if r_stats.get("holes_played", 0) < max_h:
                            p_active_r_id = r["id"]
                            break
                    
                    team_color = p.get('team_color', '#ffffff')
                    
                    # Calculate contrast color for text
                    text_color = "#1a2b22"
                    if team_color.startswith("#") and len(team_color) >= 7:
                        try:
                            h = team_color.lstrip('#')
                            r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                            if luminance < 0.5:
                                text_color = "#ffffff"
                        except: pass
                        
                    name_display = p['name'].replace(' ', '<br>', 1)
                    
                    # Use the team color as a background for the player name
                    name_html = f"<span style='background-color:{team_color}; color:{text_color}; display:block; text-align:center; padding:4px 6px; border-radius:6px; border:1px solid rgba(0,0,0,0.1); font-weight:bold; line-height:1.2;'>{name_display}</span>"
                    name_link = f"?event={event_id}&v_player={p['id']}&v_round={p_active_r_id}&v_type=netto"
                    
                    html += f"<td><a href='{name_link}' target='_self' style='text-decoration:none;'>{name_html}</a></td>"
                    html += f"<td>{p['handicap']}</td>"
                
                    if is_overall:
                        for r in rounds_list:
                            r_stats = p["rounds"].get(r["id"], {})
                            pts = r_stats.get("net_points", 0)
                            h = r_stats.get("holes_played", 0)
                            link = f"?event={event_id}&v_player={p['id']}&v_round={r['id']}&v_type=netto"
                            html += f"<td><a href='{link}' target='_self' style='text-decoration:none; color:inherit; display:block;'>{pts} <span style='font-size:0.75rem; color:#888;'>({h}L)</span></a></td>"
                        html += f"<td><strong>{total_pts}</strong></td>"
                    else:
                        link = f"?event={event_id}&v_player={p['id']}&v_round={active_round['id']}&v_type=netto"
                        html += f"<td><a href='{link}' target='_self' style='text-decoration:none; color:inherit; display:block;'><strong>{total_pts}</strong></a></td>"
                    
                    holes_str = f"{holes_played} / {max_holes_player}"
                    html += f"<td>{holes_str}</td>"
                    html += f"<td style='background-color:rgba(0,0,0,0.03); border-left:1px solid rgba(0,0,0,0.05); text-align:center;'><strong style='font-size:1.25rem; font-weight:900; color:#1a2b22;'>{diff_str}</strong></td>"
                    html += "</tr>"
                
                html += "</tbody></table></div>"
                st.markdown(html, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # 🏌️ Spieler Brutto Tab
        if not is_ryder_cup and tab_player_gross:
            with tab_player_gross:
                # Render Player Gross Tab
                st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
                st.subheader("🏌️ Einzelspieler Brutto Leaderboard")
            
                player_list = list(stats["players"].values())
            
                if is_overall:
                    key_func = lambda x: (x["total_gross_diff"], -x["total_gross_points"])
                else:
                    key_func = lambda x: (x["rounds"].get(active_round["id"], {}).get("gross_diff", 0), -x["rounds"].get(active_round["id"], {}).get("gross_points", 0))
                
                player_list.sort(key=key_func)
            
                ranks = []
                for i, p in enumerate(player_list):
                    rank = 1
                    for other in player_list:
                        if key_func(other) < key_func(p):
                            rank += 1
                    is_tied = sum(1 for o in player_list if key_func(o) == key_func(p)) > 1
                    rank_str = f"T{rank}" if is_tied else str(rank)
                    ranks.append((rank, rank_str))
                
                # Render Player Gross Table
                html = "<div class='leaderboard-container'><table class='leaderboard-table'>"
                html += f"<thead><tr><th>Rang</th><th>Spieler</th><th>HCP</th>"
                if is_overall:
                    for r in rounds_list:
                        html_details_name = r['name'].replace("Runde ", "R").split(" - ")[0]
                        html += f"<th>{html_details_name}</th>"
                    html += "<th>GES</th><th>Loch</th><th style='background-color:rgba(0,0,0,0.03); text-align:center; color:#0d522c; font-weight:900;'>PAR-DIFF</th></tr></thead><tbody>"
                else:
                    html += f"<th>Punkte</th><th>Loch</th><th style='background-color:rgba(0,0,0,0.03); text-align:center; color:#0d522c; font-weight:900;'>PAR-DIFF</th></tr></thead><tbody>"
                
                for i, p in enumerate(player_list):
                    rank, rank_str = ranks[i]
                    rank_class = f"rank-{rank}" if rank <= 3 else "rank-other"
                    team_tag = f"<span class='team-tag' style='background-color:{p['team_color']}'>{p['team_name']}</span>"
                
                    if is_overall:
                        total_pts = p["total_gross_points"]
                        diff = p["total_gross_diff"]
                        holes_played = p["total_holes_played"]
                    else:
                        r_stats = p["rounds"].get(active_round["id"], {})
                        total_pts = r_stats.get("gross_points", 0)
                        diff = r_stats.get("gross_diff", 0)
                        holes_played = r_stats.get("holes_played", 0)
                    
                    diff_str = f"+{diff}" if diff > 0 else str(diff)
                    if diff == 0:
                        diff_str = "Even"
                    if holes_played == 0:
                        diff_str = "-"
                    
                    html += "<tr>"
                    html += f"<td><span class='rank-badge {rank_class}'>{rank_str}</span></td>"
                    p_active_r_id = rounds_list[-1]['id'] if rounds_list else ""
                    for r in rounds_list:
                        c_id = r.get("course_id")
                        c_data = courses_cache.get(c_id, {})
                        max_h = len(c_data.get("holes", []))
                        r_stats = p["rounds"].get(r["id"], {})
                        if r_stats.get("holes_played", 0) < max_h:
                            p_active_r_id = r["id"]
                            break
                    
                    team_color = p.get('team_color', '#ffffff')
                    
                    # Calculate contrast color for text
                    text_color = "#1a2b22"
                    if team_color.startswith("#") and len(team_color) >= 7:
                        try:
                            h = team_color.lstrip('#')
                            r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                            if luminance < 0.5:
                                text_color = "#ffffff"
                        except: pass
                        
                    name_display = p['name'].replace(' ', '<br>', 1)
                    
                    name_html = f"<span style='background-color:{team_color}; color:{text_color}; display:block; text-align:center; padding:4px 6px; border-radius:6px; border:1px solid rgba(0,0,0,0.1); font-weight:bold; line-height:1.2;'>{name_display}</span>"
                    name_link = f"?event={event_id}&v_player={p['id']}&v_round={p_active_r_id}&v_type=brutto"
                    
                    html += f"<td><a href='{name_link}' target='_self' style='text-decoration:none;'>{name_html}</a></td>"
                    html += f"<td>{p['handicap']}</td>"
                
                    if is_overall:
                        for r in rounds_list:
                            r_stats = p["rounds"].get(r["id"], {})
                            pts = r_stats.get("gross_points", 0)
                            h = r_stats.get("holes_played", 0)
                            link = f"?event={event_id}&v_player={p['id']}&v_round={r['id']}&v_type=brutto"
                            html += f"<td><a href='{link}' target='_self' style='text-decoration:none; color:inherit; display:block;'>{pts} <span style='font-size:0.75rem; color:#888;'>({h}L)</span></a></td>"
                        html += f"<td><strong>{total_pts}</strong></td>"
                    else:
                        link = f"?event={event_id}&v_player={p['id']}&v_round={active_round['id']}&v_type=brutto"
                        html += f"<td><a href='{link}' target='_self' style='text-decoration:none; color:inherit; display:block;'><strong>{total_pts}</strong></a></td>"
                    
                    holes_str = f"{holes_played} / {max_holes_player}"
                    html += f"<td>{holes_str}</td>"
                    html += f"<td style='background-color:rgba(0,0,0,0.03); border-left:1px solid rgba(0,0,0,0.05); text-align:center;'><strong style='font-size:1.25rem; font-weight:900; color:#1a2b22;'>{diff_str}</strong></td>"
                    html += "</tr>"
                
                html += "</tbody></table></div>"
                st.markdown(html, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # ⚔️ Matchplay Duelle Tab
    if has_matchplay and tab_matchplay:
        with tab_matchplay:
            # Render Matchplay Tab
            st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
            st.subheader("⚔️ Matchplay Duelle (Lochspiel)")
            
            # Filter matchups
            m_list = stats["matchplays"]
            if not is_overall:
                m_list = [m for m in m_list if m["round_id"] == active_round["id"]]
                
            if not m_list:
                st.info("Keine Matchplay-Duelle für diese Auswahl konfiguriert.")
            else:
                html = "<div class='leaderboard-container'><table class='leaderboard-table'>"
                html += "<thead><tr><th>Duell</th><th>Runde</th><th>Aktueller Stand</th><th>Löcher</th></tr></thead><tbody>"
                for m in m_list:
                    status = m["status"]
                    status_color = "#f1cf6d" if not status["is_finished"] else "#2ecc71"
                    
                    html += "<tr>"
                    html += f"<td><strong>{m['name']}</strong></td>"
                    html += f"<td>{m['round_name']}</td>"
                    html += f"<td><span style='color:{status_color}; font-weight:bold;'>{status['result_text']}</span></td>"
                    html += f"<td>{status['holes_played']} / {status['holes_played'] + status['holes_remaining']}</td>"
                    html += "</tr>"
                html += "</tbody></table></div>"
                st.markdown(html, unsafe_allow_html=True)
                
                # Detailed Matchplay Hole Card expanders
                st.markdown("### Duell Lochkarten (Netto Vergleiche)")
                for m in m_list:
                    status = m["status"]
                    with st.expander(f"Lochkarte: {m['name']} ({status['result_text']})"):
                        html_card = "<div class='leaderboard-container'><table class='leaderboard-table'>"
                        html_card += f"<thead><tr><th>Loch</th><th>Par</th><th>Index</th><th>Sieger</th></tr></thead><tbody>"
                        for hd in status["hole_details"]:
                            winner_name = "-"
                            winner_style = ""
                            if hd["winner"] == "A":
                                winner_name = m['player_a']['name']
                                winner_style = "color: #2ecc71; font-weight: bold;"
                            elif hd["winner"] == "B":
                                winner_name = m['player_b']['name']
                                winner_style = "color: #2ecc71; font-weight: bold;"
                            elif hd["winner"] == "halved":
                                winner_name = "Geteilt"
                                winner_style = "color: #92a498;"
                                
                            html_card += "<tr>"
                            html_card += f"<td>Loch {hd['hole']}</td>"
                            html_card += f"<td>{hd['par']}</td>"
                            html_card += f"<td>{hd['index']}</td>"
                            html_card += f"<td style='{winner_style}'>{winner_name}</td>"
                            html_card += "</tr>"
                        # Transposed table
                        html_card = "<div class='leaderboard-container'><table class='leaderboard-table' style='width:auto;'>"
                        html_card += "<tr><th>Loch</th>" + "".join([f"<td>{hd['hole']}</td>" for hd in status["hole_details"]]) + "</tr>"
                        html_card += "<tr><th>Par</th>" + "".join([f"<td>{hd['par']}</td>" for hd in status["hole_details"]]) + "</tr>"
                        html_card += "<tr><th>Index</th>" + "".join([f"<td>{hd['index']}</td>" for hd in status["hole_details"]]) + "</tr>"
                        html_card += "<tr><th>Sieger</th>" + "".join([f"<td style='font-weight:bold; color: #2ecc71;'>{hd['winner'] if hd['winner'] != 'halved' else '-'}</td>" for hd in status["hole_details"]]) + "</tr>"
                        html_card += "</table></div>"
                        st.markdown(html_card, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        # 🏆 Previous Winners Tab
    if tab_winners:
        with tab_winners:
            with tab_winners:
                # Render Winners Tab
                st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
                st.subheader("🏆 Previous Winners (45 Loch Challenge)")
            
                import os
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
                c1_txt, c2_txt = st.columns(2)
                with c1_txt:
                    st.markdown("#### 🏆 2025")
                    st.markdown("**11.06.2025**<br>Mondsee > Altentann > Klessheim", unsafe_allow_html=True)
                    st.markdown("**Team Blue (+90/18):** Baumi, Gustel, Enzo, Markus, Alex")
                    st.markdown("**Netto:** Christoph (E)")
                    st.markdown("**Brutto:** Lee (+7)")
                    
                with c2_txt:
                    st.markdown("#### 🏆 2024")
                    st.markdown("**17.06.2024**<br>Altentann > Eugendorf > Klessheim", unsafe_allow_html=True)
                    st.markdown("**Team White:** David, Gustavo, Christoph")
                    st.markdown("**Netto:** David, Tim")
                    st.markdown("**Brutto:** Christoph")
                
                c1_img, c2_img = st.columns(2)
                with c1_img:
                    img_path_2025 = os.path.join(base_dir, "assets", "winners", "2025.png")
                    if os.path.exists(img_path_2025):
                        st.image(img_path_2025)
                with c2_img:
                    img_path_2024 = os.path.join(base_dir, "assets", "winners", "2024.png")
                    if os.path.exists(img_path_2024):
                        st.image(img_path_2024)
                    
                st.markdown("</div>", unsafe_allow_html=True)

elif page == "✍️ Scores eingeben":
        if check_password():
            st.title("✍️ Scores eintragen")
        
            # Load courses list
            courses = data_manager.list_courses()
            courses_cache = {c["id"]: c for c in courses}
            data_manager.apply_course_modifications(courses_cache, event_id)
        
            if not tournament.get("rounds"):
                st.warning("Keine Runden konfiguriert. Bitte im Admin-Bereich einrichten.")
            else:
                rounds_list = sorted(tournament["rounds"], key=lambda x: x.get("sequence", 0))
                round_options = [r["name"] for r in rounds_list]
                selected_round_name = st.selectbox("Runde auswählen:", round_options)
            
                players = tournament.get("players", [])
                is_ryder_cup = tournament.get("is_ryder_cup", False)
            
                if not is_ryder_cup:
                    player_names = [p["name"] for p in players]
                    if "persisted_selected_players" not in st.session_state:
                        st.session_state.persisted_selected_players = player_names
                    
                    def update_selected_players():
                        st.session_state.persisted_selected_players = st.session_state.selected_players_widget
                    
                    selected_player_names = st.multiselect(
                        "Welche Spieler möchtest du erfassen?", 
                        options=player_names, 
                        default=st.session_state.persisted_selected_players,
                        key="selected_players_widget",
                        on_change=update_selected_players
                    )

                    filtered_players = [p for p in players if p["name"] in selected_player_names]
                else:
                    filtered_players = players # Not used, but kept to avoid undefined vars
                
                # Find selected round object
                active_round = next((r for r in rounds_list if r["name"] == selected_round_name), None)
                course = courses_cache.get(active_round["course_id"]) if active_round else None
            
                if not course:
                    st.error("Zugehöriger Golfplatz nicht gefunden!")
                else:
                    # Hole Selection
                    hole_numbers = [h["hole"] for h in course["holes"]]
                    if "current_hole" not in st.session_state or st.session_state.current_hole not in hole_numbers:
                        st.session_state.current_hole = hole_numbers[0]
                    
                    selected_hole_ui = st.selectbox("Loch direkt auswählen:", hole_numbers, index=hole_numbers.index(st.session_state.current_hole))
                    if selected_hole_ui != st.session_state.current_hole:
                        st.session_state.current_hole = selected_hole_ui
                        st.rerun()
                
                    selected_hole = st.session_state.current_hole
                
                    # Fetch hole stats
                    hole_info = next((h for h in course["holes"] if h["hole"] == selected_hole), None)
                
                    st.markdown("<hr style='border-color: #f1cf6d; margin: 10px 0;'>", unsafe_allow_html=True)
                    col_prev, col_curr, col_next = st.columns([1, 2, 1])
                    with col_prev:
                        if st.button("⬅️ Vorheriges", use_container_width=True):
                            curr_idx = hole_numbers.index(st.session_state.current_hole)
                            if curr_idx > 0:
                                st.session_state.current_hole = hole_numbers[curr_idx - 1]
                                st.rerun()
                    with col_curr:
                        header_html = (
                            f"<div style='text-align: center; line-height: 1.1;'>"
                            f"<h3 style='margin: 0; padding: 0; color: #0d522c;'>Loch {selected_hole} &mdash; Par {hole_info['par']}</h3>"
                            f"<p style='color: #4a5c50; margin: 0; padding: 0; font-size: 0.9rem;'>Index {hole_info['index']}</p>"
                            f"</div>"
                        )
                        st.markdown(header_html, unsafe_allow_html=True)
                    with col_next:
                        if st.button("Nächstes ➡️", use_container_width=True):
                            curr_idx = hole_numbers.index(st.session_state.current_hole)
                            if curr_idx < len(hole_numbers) - 1:
                                st.session_state.current_hole = hole_numbers[curr_idx + 1]
                                st.rerun()
                    st.markdown("<hr style='border-color: #f1cf6d; margin: 10px 0;'>", unsafe_allow_html=True)
                
                    # Load current scores
                    scores = data_manager.load_scores(event_id)
                    rnd_scores = scores.get(active_round["id"], {})
                
                    if is_ryder_cup:
                        matchups = [m for m in tournament.get("matchups", []) if m["round_id"] == active_round["id"]]
                        st.markdown("<div style='margin-bottom: 20px;'>", unsafe_allow_html=True)
                        for m in matchups:
                            m_id = m["id"]
                            p_a_id = m["player_a_id"]
                            p_b_id = m["player_b_id"]
                            name_a = next((p["name"] for p in players if p["id"] == p_a_id), "A")
                            name_b = next((p["name"] for p in players if p["id"] == p_b_id), "B")
                        
                            existing_val_a = rnd_scores.get(p_a_id, {}).get(str(selected_hole), 0)
                            existing_val_b = rnd_scores.get(p_b_id, {}).get(str(selected_hole), 0)
                        
                            status_text = "-"
                            if existing_val_a == 1 and existing_val_b == 2: status_text = f"<span style='color:#2ecc71;'>{name_a} gewinnt</span>"
                            elif existing_val_a == 2 and existing_val_b == 1: status_text = f"<span style='color:#e74c3c;'>{name_b} gewinnt</span>"
                            elif existing_val_a == 1 and existing_val_b == 1: status_text = "<span style='color:#f1c40f;'>Geteilt</span>"
                        
                            st.markdown("<hr style='margin: 10px 0; border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
                            st.markdown(f"**{name_a} vs {name_b}** <br/> Aktueller Stand dieses Lochs: {status_text}", unsafe_allow_html=True)
                        
                            c1, c2, c3, c4 = st.columns(4)
                            with c1:
                                if st.button(f"{name_a} gewinnt", key=f"win_a_{m_id}_{selected_hole}", use_container_width=True):
                                    data_manager.update_scores_bulk(event_id, active_round["id"], selected_hole, {p_a_id: 1, p_b_id: 2}, username=st.session_state.get("scorer_name", "Admin"))
                                    st.rerun()
                            with c2:
                                if st.button("Geteilt", key=f"tie_{m_id}_{selected_hole}", use_container_width=True):
                                    data_manager.update_scores_bulk(event_id, active_round["id"], selected_hole, {p_a_id: 1, p_b_id: 1}, username=st.session_state.get("scorer_name", "Admin"))
                                    st.rerun()
                            with c3:
                                if st.button(f"{name_b} gewinnt", key=f"win_b_{m_id}_{selected_hole}", use_container_width=True):
                                    data_manager.update_scores_bulk(event_id, active_round["id"], selected_hole, {p_a_id: 2, p_b_id: 1}, username=st.session_state.get("scorer_name", "Admin"))
                                    st.rerun()
                            with c4:
                                if st.button("Löschen", key=f"clear_{m_id}_{selected_hole}", use_container_width=True):
                                    data_manager.update_scores_bulk(event_id, active_round["id"], selected_hole, {p_a_id: 0, p_b_id: 0}, username=st.session_state.get("scorer_name", "Admin"))
                                    st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    else:
                        if not filtered_players:
                            st.info("Bitte wähle Spieler aus, für die du Scores eingeben möchtest.")
                        else:
                            teams = {t["id"]: t for t in tournament.get("teams", [])}
                        
                            st.markdown("<div style='margin-bottom: 20px;'>", unsafe_allow_html=True)
                            for p in filtered_players:
                                p_id = p["id"]
                                p_team = teams.get(p["team_id"], {"name": "No Team", "color": "#888"})
                            
                                # Calculate playing handicap strokes for this hole
                                playing_hcp = tournament.get("playing_handicaps", {}).get(p_id, {}).get(active_round["course_id"])
                                if playing_hcp is None:
                                    total_par = sum(h["par"] for h in course["holes"])
                                    playing_hcp = scoring.calculate_playing_handicap(p["handicap"], course.get("cr"), course.get("slope"), total_par)
                            
                                hcp_strokes = scoring.get_hole_handicap_strokes(playing_hcp, hole_info["index"], 18)
                            
                                # Get existing score
                                existing_val = rnd_scores.get(p_id, {}).get(str(selected_hole), 0)
                            
                                # UI Columns for alignment
                                st.markdown("<hr style='margin: 10px 0; border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
                                c_name, c_minus, c_score, c_plus = st.columns([3, 1, 1, 1])
                                with c_name:
                                     badge_color = "#c97b63" if hcp_strokes > 0 else "#92a498"
                                     badge_text = f"+{hcp_strokes}" if hcp_strokes >= 0 else str(hcp_strokes)
                                     badge = f"<span style='background-color:{badge_color}; color:white; padding:2px 8px; border-radius:12px; font-weight:bold; font-size: 0.9rem;'>{badge_text} Schläge</span>" if hcp_strokes != 0 else ""
                                 
                                     label_html = (
                                         f"<div style='margin-top: 5px; display: flex; justify-content: space-between; align-items: center;'>"
                                         f"<div>"
                                         f"<strong style='font-size: 1.1rem; color: #0d522c;'>{p['name']}</strong><br/>"
                                         f"<span class='team-tag' style='background-color: {p_team['color']}'>{p_team['name']}</span>"
                                         f"<span style='font-size: 0.8rem; color: #92a498;'>Spielvorgabe: {playing_hcp}</span>"
                                         f"</div>"
                                         f"<div>{badge}</div>"
                                         f"</div>"
                                     )
                                     st.markdown(label_html, unsafe_allow_html=True)
                                 
                                par = hole_info['par']
                                with c_minus:
                                    if st.button("➖", key=f"minus_{p_id}_{selected_hole}", use_container_width=True):
                                        new_val = par - 1 if existing_val == 0 else max(0, existing_val - 1)
                                        data_manager.update_scores_bulk(event_id, active_round["id"], selected_hole, {p_id: new_val}, username=st.session_state.get("scorer_name", "Admin"))
                                        st.rerun()
                                with c_score:
                                    if existing_val > 0:
                                        net_pts, _ = scoring.calculate_stableford_points(existing_val, par, hcp_strokes)
                                        diff = existing_val - par
                                        score_class = ""
                                        if diff <= -2:
                                            score_class = "score-eagle"
                                        elif diff == -1:
                                            score_class = "score-birdie"
                                        elif diff == 1:
                                            score_class = "score-bogey"
                                        elif diff == 2:
                                            score_class = "score-double-bogey"
                                        elif diff >= 3:
                                            score_class = "score-triple-bogey"

                                        if score_class:
                                            base_val = f"<div class='score-box {score_class}' style='width: 32px; height: 32px;'>{existing_val}</div>"
                                        else:
                                            base_val = f"{existing_val}"

                                        display_val = f"{base_val} <span style='font-size:1rem; color:#c62828;'>/</span>" if net_pts == 0 else base_val
                                    else:
                                        display_val = "-"
                                    st.markdown(f"<div style='text-align:center; font-size:1.5rem; font-weight:bold; margin-top:5px; display:flex; justify-content:center; align-items:center;'>{display_val}</div>", unsafe_allow_html=True)
                                with c_plus:
                                    if st.button("➕", key=f"plus_{p_id}_{selected_hole}", use_container_width=True):
                                        new_val = par if existing_val == 0 else existing_val + 1
                                        data_manager.update_scores_bulk(event_id, active_round["id"], selected_hole, {p_id: new_val}, username=st.session_state.get("scorer_name", "Admin"))
                                        st.rerun()
                                    
                            st.markdown("</div>", unsafe_allow_html=True)

    # ----------------- ⚙️ ADMIN PAGE -----------------
elif page == "⚙️ Admin":
    if check_password("admin"):
        st.title("⚙️ Admin & Setup")
    
        # Tabs for administration actions
        admin_tab_backup, admin_tab_config, admin_tab_audit = st.tabs([
            "💾 Datensicherung & Backup",
            "🛠️ Turnier Setup",
            "📋 Audit Log"
        ])
    
        with admin_tab_backup:
            st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
            st.subheader("💾 Backup herunterladen")
            st.write("Laden Sie den aktuellen Stand des Turniers (inkl. aller Spielstände und Konfigurationen) als JSON herunter.")
        
            backup_str = data_manager.export_backup(event_id)
        
            st.download_button(
                label="📥 Backup JSON herunterladen",
                data=backup_str,
                file_name="golfscore_backup.json",
                mime="application/json"
            )
            st.markdown("</div>", unsafe_allow_html=True)
        
            st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
            st.subheader("📤 Backup wiederherstellen / Setup einspielen")
            st.write("Wählen Sie eine zuvor exportierte JSON-Backup-Datei oder eine neue Turnier-Setup-Datei aus, um das System zu konfigurieren.")
        
            uploaded_file = st.file_uploader("JSON-Setup-Datei auswählen:", type=["json"])
            if uploaded_file is not None:
                try:
                    file_content = uploaded_file.read().decode("utf-8")
                    if st.button("Backup einspielen (Aktuelle Daten werden überschrieben!)"):
                        success = data_manager.import_backup(event_id, file_content)
                        if success:
                            st.success("Backup erfolgreich eingespielt!")
                            st.rerun()
                        else:
                            st.error("Ungültiges Backup-Format.")
                except Exception as e:
                    st.error(f"Fehler beim Lesen der Datei: {e}")
            st.markdown("</div>", unsafe_allow_html=True)
        
            st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
            st.subheader("⚠️ Spielstände zurücksetzen")
            st.write("Wähle aus, ob du alle Spielstände oder nur eine bestimmte Runde löschen möchtest.")
        
            # Use rounds from tournament if available
            tourn_rounds = sorted(tournament.get("rounds", []), key=lambda x: x.get("sequence", 0))
            round_options = {"all": "Alle Runden"}
            for r in tourn_rounds:
                round_options[r["id"]] = r["name"]
            
            selected_reset_round = st.selectbox("Welche Spielstände sollen gelöscht werden?", list(round_options.values()))
            selected_round_id = next((k for k, v in round_options.items() if v == selected_reset_round), "all")
        
            confirm_reset = st.checkbox("Ja, ich bin mir sicher. (Aktion kann nicht rückgängig gemacht werden)")
        
            if st.button("❌ Spielstände löschen"):
                if not confirm_reset:
                    st.error("Bitte bestätige zuerst mit dem Häkchen, dass du dir sicher bist.")
                else:
                    if selected_round_id == "all":
                        success = data_manager.reset_scores(event_id)
                        data_manager.reset_audit_log(event_id)
                    else:
                        scores_data = data_manager.load_scores(event_id)
                        if selected_round_id in scores_data:
                            del scores_data[selected_round_id]
                        success = data_manager.save_scores(scores_data, event_id)
                    
                        # Also delete from audit log
                        audit_log = data_manager.load_audit_log(event_id)
                        audit_log = [entry for entry in audit_log if entry.get("round_id") != selected_round_id]
                        data_manager.save_audit_log(audit_log, event_id)
                    
                    if success:
                        st.success("Spielstände erfolgreich gelöscht!")
                        st.rerun()
                    else:
                        st.error("Fehler beim Zurücksetzen.")
            st.markdown("</div>", unsafe_allow_html=True)
        
        with admin_tab_config:
            st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
            st.subheader("🛠️ Turnier-Konfiguration einsehen")
            st.write("Aktueller Name des Turniers:")
            st.markdown(f"**{tournament.get('tournament_name', 'Kein Turniername')}**")
        
            # Passwords update
            st.markdown("### Passwörter")
            c1, c2 = st.columns(2)
            with c1:
                new_admin_password = st.text_input("Admin-Passwort:", value=admin_pwd_correct)
            with c2:
                new_score_password = st.text_input("Score-Eingabe Passwort:", value=score_pwd_correct)
            
            if st.button("Passwörter speichern"):
                tournament["admin_password"] = new_admin_password
                tournament["score_password"] = new_score_password
                if data_manager.save_tournament(tournament, event_id):
                    st.success("Passwörter erfolgreich geändert!")
                    st.rerun()
                else:
                    st.error("Fehler beim Speichern.")
                
            st.markdown("</div>", unsafe_allow_html=True)
        
            # JSON Editor
            st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
            st.subheader("🛠️ Turnier-Daten Editor (JSON)")
            st.info("Hier kannst du direkt die Turnier-Daten editieren (z.B. Handicaps anpassen, Teams ändern). Änderungen am Handicap berechnen automatisch die Course-Handicaps für alle Plätze neu!")
        
            current_json = json.dumps(tournament, indent=2, ensure_ascii=False)
            edited_json = st.text_area("tournament.json", value=current_json, height=400)
        
            if st.button("JSON Änderungen speichern"):
                try:
                    new_data = json.loads(edited_json)
                
                    # Auto-recalculate playing handicaps if players exist
                    if "players" in new_data:
                        courses = data_manager.list_courses()
                        ph = {}
                        for p in new_data["players"]:
                            ph[p["id"]] = {}
                            for c in courses:
                                total_par = sum(h["par"] for h in c["holes"])
                                ph[p["id"]][c["id"]] = scoring.calculate_playing_handicap(p["handicap"], c.get("cr"), c.get("slope"), total_par)
                        new_data["playing_handicaps"] = ph
                
                    if data_manager.save_tournament(new_data, event_id):
                        st.success("Erfolgreich gespeichert & Handicaps neu berechnet!")
                        st.rerun()
                    else:
                        st.error("Fehler beim Speichern.")
                except Exception as e:
                    st.error(f"Fehlerhaftes JSON: {e}")
            st.markdown("</div>", unsafe_allow_html=True)
        
            st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
            st.subheader("⛳ Plätze verwalten")
            courses = data_manager.list_courses()
            st.write("Installierte Golfplätze:")
            for c in courses:
                st.write(f"- **{c['name']}** ({c['id']}, {len(c['holes'])} Löcher)")
            
            st.write("Neuen Golfplatz hochladen (JSON):")
            uploaded_course = st.file_uploader("Platz JSON hochladen:", type=["json"], key="course_uploader")
            if uploaded_course is not None:
                try:
                    course_data = json.loads(uploaded_course.read().decode("utf-8"))
                    if st.button("Golfplatz speichern"):
                        if data_manager.save_course(course_data):
                            st.success(f"Golfplatz {course_data.get('name')} erfolgreich gespeichert!")
                            st.rerun()
                        else:
                            st.error("Ungültiges Golfplatz-Format (muss ID, Name und Löcher-Array enthalten).")
                except Exception as e:
                    st.error(f"Fehler beim Verarbeiten: {e}")
            st.markdown("</div>", unsafe_allow_html=True)

        with admin_tab_audit:
            st.markdown("<div class='golf-card'>", unsafe_allow_html=True)
            st.subheader("📋 Audit Log")
            st.write("Hier siehst du alle protokollierten Score-Eingaben, absteigend sortiert nach Zeit.")
        
            audit_data = data_manager.load_audit_log(event_id)
            if not audit_data:
                st.info("Das Audit Log ist leer.")
            else:
                # Sort descending by timestamp
                audit_data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
                # Resolve IDs to readable names
                players = {p["id"]: p["name"] for p in tournament.get("players", [])}
                rounds = {r["id"]: r["name"] for r in tournament.get("rounds", [])}
            
                html = "<div class='leaderboard-container'><table class='leaderboard-table' style='width: 100%; font-size: 0.9rem;'>"
                html += "<thead><tr><th>Zeit</th><th>User</th><th>Spieler</th><th>Runde/Platz</th><th>Loch</th><th>Neuer Score</th></tr></thead><tbody>"
            
                for entry in audit_data:
                    # Parse timestamp (e.g., 2026-06-14T20:05:00) -> 14.06.2026 20:05
                    ts_raw = entry.get("timestamp", "")
                    ts_formatted = ts_raw
                    try:
                        import datetime
                        # Replace Z with +00:00 for strict ISO format parsing
                        dt = datetime.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=datetime.timezone.utc)
                        try:
                            import zoneinfo
                            dt = dt.astimezone(zoneinfo.ZoneInfo("Europe/Berlin"))
                        except:
                            # Fallback if zoneinfo is missing (CEST offset)
                            dt = dt + datetime.timedelta(hours=2)
                        ts_formatted = dt.strftime("%d.%m.%y %H:%M")
                    except Exception as e:
                        pass
                
                    user = entry.get("username", "Unbekannt")
                    p_name = players.get(entry.get("player_id"), entry.get("player_id"))
                    r_name = rounds.get(entry.get("round_id"), entry.get("round_id"))
                    hole = entry.get("hole_number", "")
                
                    score = entry.get("score", 0)
                    score_str = str(score) if score > 0 else "Gestichen (/)"
                
                    html += "<tr>"
                    html += f"<td>{ts_formatted}</td>"
                    html += f"<td><strong>{user}</strong></td>"
                    html += f"<td>{p_name}</td>"
                    html += f"<td>{r_name}</td>"
                    html += f"<td>{hole}</td>"
                    html += f"<td><strong>{score_str}</strong></td>"
                    html += "</tr>"
            
                html += "</tbody></table></div>"
                st.markdown(html, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
