import streamlit as st
import os
import json
import random
import copy
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Auslosung - 45-Loch Challenge",
    page_icon="🎲",
    layout="wide"
)

import re

# Get and sanitize draw ID from query parameters
draw_id = st.query_params.get("draw", "45_Loch_Challenge")
draw_id = re.sub(r'[^a-zA-Z0-9_-]', '', draw_id)
if not draw_id:
    draw_id = "45_Loch_Challenge"

st.markdown(f"<h1 style='text-align: center; color: #f1cf6d;'>🎲 Auslosung: {draw_id.replace('_', ' ')}</h1>", unsafe_allow_html=True)

# Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
config_file = os.path.join(current_dir, f"{draw_id}.json")
results_file = os.path.join(current_dir, f"results_{draw_id}.json")
index_file = os.path.join(current_dir, "index.html")
css_file = os.path.join(current_dir, "style.css")
js_file = os.path.join(current_dir, "app.js")

if not os.path.exists(config_file):
    st.error(f"Auslosungs-Konfiguration nicht gefunden unter: {config_file}")
else:
    with open(config_file, "r", encoding="utf-8") as f:
        draw_config = json.load(f)

    # Check for existing results
    existing_results = None
    if os.path.exists(results_file):
        try:
            with open(results_file, "r", encoding="utf-8") as f:
                existing_results = json.load(f)
        except Exception as e:
            st.error(f"Fehler beim Laden der Ergebnisse: {e}")

    # Draw triggering logic
    autoplay = st.session_state.get('trigger_autoplay', False)
    if autoplay:
        st.session_state['trigger_autoplay'] = False
        
    if not existing_results:
        scheduled_time = datetime.fromisoformat(draw_config["scheduled_time"])
        now = datetime.now()
        
        force_draw = st.session_state.get('force_draw_trigger', False)
        if force_draw:
            st.session_state['force_draw_trigger'] = False

        if force_draw or (now >= scheduled_time and not st.session_state.get('results_deleted', False)):
            pots = copy.deepcopy(draw_config.get("pots", []))
            teams = draw_config.get("teams", [])
            draw_sequence = []
            
            for pot_idx, pot in enumerate(pots):
                players = pot.get("players", [])
                random.shuffle(players)
                ordered_teams = list(teams)
                
                for i, player in enumerate(players):
                    draw_sequence.append({
                        "pot": { "id": pot["id"], "name": pot["name"] },
                        "player": player,
                        "team": ordered_teams[i],
                        "isLastInPot": (i == len(players) - 1),
                        "potDrawIndex": pot_idx + 1
                    })
            
            # Save results
            results_data = {
                "drawId": draw_id,
                "sequence": draw_sequence,
                "generated_at": datetime.now().isoformat()
            }
            
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(results_data, f, indent=2, ensure_ascii=False)
                
            # Apply results to golf_scoring tournament configuration if it is in the parent workspace
            parent_dir = os.path.dirname(current_dir)
            scoring_filename = f"{draw_id.lower()}_tournament.json"
            scoring_tournament_file = os.path.join(parent_dir, "golf_scoring", "data", scoring_filename)
            if os.path.exists(scoring_tournament_file):
                try:
                    with open(scoring_tournament_file, "r", encoding="utf-8") as sf:
                        score_data = json.load(sf)
                    
                    player_team_map = {step["player"]["id"]: step["team"]["id"] for step in draw_sequence}
                    for player in score_data.get("players", []):
                        pid = player["id"]
                        if pid in player_team_map:
                            player["team_id"] = player_team_map[pid]
                            
                    with open(scoring_tournament_file, "w", encoding="utf-8") as sf:
                        json.dump(score_data, sf, indent=2, ensure_ascii=False)
                except Exception as e:
                    st.warning(f"Konnte Teams nicht automatisch ins Scoring übertragen: {e}")
            
            existing_results = results_data
            st.session_state['trigger_autoplay'] = True
            st.success("Auslosung erfolgreich generiert!")
            st.rerun()
    else:
        # No extra block here; we will put the Admin options at the bottom for both cases
        pass

    # Build and render the HTML page inside iframe
    if os.path.exists(index_file) and os.path.exists(css_file) and os.path.exists(js_file):
        with open(index_file, "r", encoding="utf-8") as f:
            html_content = f.read()
        with open(css_file, "r", encoding="utf-8") as f:
            css_content = f.read()
        with open(js_file, "r", encoding="utf-8") as f:
            js_content = f.read()

        # Embed CSS
        html_content = html_content.replace(
            '<link rel="stylesheet" href="style.css">',
            f'<style>{css_content}</style>'
        )

        # Inject config & results and embed JS
        js_injection = f"""
        <script>
            window.drawConfig = {json.dumps(draw_config, ensure_ascii=False)};
            window.existingResults = {json.dumps(existing_results, ensure_ascii=False) if existing_results else 'null'};
            window.autoplay = {'true' if autoplay else 'false'};
            window.isStreamlit = true;
            {js_content}
        </script>
        """
        html_content = html_content.replace(
            '<script src="app.js"></script>',
            js_injection
        )

        # Render the custom iframe
        st.components.v1.html(html_content, height=1200, scrolling=True)

    # Move Admin Options to the very bottom
    st.markdown("---")
    show_admin = st.checkbox("Admin-Optionen anzeigen")
    if show_admin:
        pwd = st.text_input("Admin-Passwort:", type="password")
        if pwd == "admin":
            col1, col2 = st.columns(2)
            with col1:
                def trigger_draw():
                    st.session_state['force_draw_trigger'] = True
                st.button("Jetzt auslosen 🎲", type="primary", use_container_width=True, on_click=trigger_draw, disabled=bool(existing_results))
            with col2:
                def delete_results():
                    if os.path.exists(results_file):
                        os.remove(results_file)
                    st.session_state['results_deleted'] = True
                st.button("Auslosungsergebnis löschen ⚠️", type="secondary", use_container_width=True, on_click=delete_results, disabled=not bool(existing_results))
        elif pwd:
            st.error("Falsches Passwort!")
