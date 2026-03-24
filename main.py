import streamlit as st
import requests
import json
import os
import subprocess
import urllib.parse
from datetime import datetime, timedelta


class OddsFeedClient:
    def __init__(self, config_path='config.json'):
        self.config = self._load_config(config_path)
        auth = self.config['auth']
        self.host = auth['host']
        self.mode = self.config.get('settings', {}).get('output_mode', 'NORMAL').upper()
        self.api_base = f"https://{self.host}/api/v1"
        
        try:
            rapid_key = st.secrets["MY_RAPIDAPI_KEY"]
        except:
            rapid_key = auth['rapid_key']
            
        self.headers = {
            'x-portal-apikey': auth['portal_key'],
            'x-rapidapi-host': self.host,
            'x-rapidapi-key': rapid_key,
            'Content-Type': 'application/json'
        }

    def _load_config(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found at {path}")
        with open(path, 'r') as f:
            return json.load(f)

    def get_scheduled_list(self, sport_id, max_pages=2):
        params = self.config['request_params']
        start_min = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        end_date_obj = datetime.now() + timedelta(days=params['max_days_ahead'])
        start_max = end_date_obj.replace(hour=23, minute=59, second=59).strftime('%Y-%m-%d %H:%M:%S')

        all_events = []
        for page in range(max_pages):
            query = {
                'sport_id': str(sport_id),
                'start_at_min': start_min,
                'start_at_max': start_max,
                'status': params['status_filter'],
                'page': page
            }
            try:
                response = requests.get(f"{self.api_base}/events", params=query, headers=self.headers, timeout=10)
                data = response.json().get('data', [])
                if not data: break
                all_events.extend(data)
            except:
                break
        return all_events

    def get_event_markets(self, event_id):
        try:
            r = requests.get(f"{self.api_base}/events/markets", params={'event_id': str(event_id)},
                             headers=self.headers, timeout=10)
            return r.json()
        except:
            return None

    def get_market_history(self, market_book_id):
        try:
            r = requests.get(f"{self.api_base}/markets/history", params={'market_book_id': str(market_book_id)},
                             headers=self.headers, timeout=10)
            data = r.json().get('data', [])
            if not data: return None
            return max([item.get('change_at', '') for item in data if item.get('change_at')])
        except:
            return None

    def calculate_overround(self, outcomes):
        try:
            margin = sum(1.0 / o for o in outcomes if o and o > 0)
            return (margin - 1) * 100
        except:
            return 999.0

    def get_outcome_label(self, market_name, index, home, away):
        mappings = self.config.get('market_mappings', {})
        labels = mappings.get(market_name, mappings.get('DEFAULT', []))
        if index >= len(labels): return f"OUT_{index}"
        label = labels[index]
        if label == "HOME": return home
        if label == "AWAY": return away
        return label

    def run(self, override_thresholds=None):
        thresholds = override_thresholds if override_thresholds else self.config['golden_thresholds']
        params = self.config['request_params']
        ignored = [m.upper() for m in thresholds.get('ignored_markets', [])]
        results = []

        for sport_id in params.get('sport_ids', ["1"]):
            # Streamlit logic runs in spinner, no need to print
            all_events = self.get_scheduled_list(sport_id, max_pages=params.get('max_pages_per_sport', 2))
            if not all_events: continue
            
            unique_events = {}
            for e in all_events:
                eid = e.get('id')
                if eid: unique_events[eid] = e
            all_events = list(unique_events.values())
            
            all_events.sort(key=lambda x: x.get('main_volume_1') or 0.0, reverse=True)
            passed_events = [e for e in all_events if (e.get('main_volume_1') or 0) >= thresholds['min_main_volume']]

            for event in passed_events[:params.get('event_limit_per_sport', 5)]:
                eid, home, away = event.get('id'), event.get('team_home', {}).get('name', 'N/A'), event.get('team_away',
                                                                                                            {}).get(
                    'name', 'N/A')
                sport_name, date_str = event.get('sport', {}).get('name', 'Sport'), event.get('start_at', 'N/A')

                market_data = self.get_event_markets(eid)
                if not market_data or 'data' not in market_data: continue

                seen_markets = set()
                for market in market_data['data']:
                    raw_m_name = market.get('market_name', 'UNK')
                    m_name = raw_m_name.upper()
                    m_val = market.get('value')

                    m_key = f"{m_name}_{m_val}"
                    if m_key in seen_markets: continue
                    seen_markets.add(m_key)

                    if m_name in ignored: continue
                    if m_name == "ASIAN_HANDICAP":
                        if m_val is None or (abs(m_val) % 1.0 != 0.5): continue
                    elif m_name == "OVER_UNDER" and thresholds.get('require_half_handicap_over_under', True):
                        if m_val is None or (abs(m_val) % 1.0 != 0.5): continue
                    elif m_val is not None:
                        if (abs(m_val) * 100 % 50 != 0): continue

                    books = market.get('market_books', [])
                    if len(books) < thresholds['min_market_books']: continue

                    processed_books = []
                    max_o0, max_o1, max_o2 = 0.0, 0.0, 0.0
                    min_p, max_p = thresholds.get('price_range', [1.3, 5.0])
                    for b in books:
                        if b.get('is_open') is False: continue
                        
                        o0, o1, o2 = b.get('outcome_0'), b.get('outcome_1'), b.get('outcome_2')

                        if o0 and o0 > max_o0: max_o0 = o0
                        if o1 and o1 > max_o1: max_o1 = o1
                        if o2 and o2 > max_o2: max_o2 = o2
                        processed_books.append({'name': b.get('book', 'UNK'), 'o0': o0, 'o1': o1, 'o2': o2, 'id': b.get('market_book_id')})

                    target_bookie = thresholds['required_bookie_best_price'].upper()
                    allowed_drop_pct = thresholds.get('allowed_bookie_odds_drop_pct', 0.0) / 100.0
                    
                    best_details = []
                    best_ovr_list = []
                    latest_change_time = None
                    
                    for b in processed_books:
                        if target_bookie in b['name'].upper():
                            for i, (P, max_P) in enumerate([(b.get('o0'), max_o0), (b.get('o1'), max_o1), (b.get('o2'), max_o2)]):
                                if P is not None and P > 1.0 and max_P is not None and max_P > 1.0:
                                    if not (min_p <= P <= max_p): continue
                                    drop_pct = (max_P - P) / (max_P - 1.0)
                                    if drop_pct <= allowed_drop_pct:
                                        combo = []
                                        if i == 0: combo = [P, max_o1, max_o2]
                                        elif i == 1: combo = [max_o0, P, max_o2]
                                        elif i == 2: combo = [max_o0, max_o1, P]
                                        
                                        combo_ovr = self.calculate_overround([o for o in combo if o is not None and o > 0])
                                        if combo_ovr < thresholds['max_combined_overround']:
                                            best_details.append(f"{self.get_outcome_label(m_name, i, home, away)} @ {P:.2f}")
                                            best_ovr_list.append(combo_ovr)
                                            if not latest_change_time and b.get('id'):
                                                latest_change_time = self.get_market_history(b.get('id'))

                    if len(best_details) > 0:
                        reported_ovr = min(best_ovr_list)
                        market_display = f"{m_name} {m_val if m_val is not None else ''}"
                        
                        allowed_hours = thresholds.get('last_update_hours_ago', 3)
                        is_allowed_time = True
                        if latest_change_time and latest_change_time != "N/A":
                            try:
                                change_dt = datetime.strptime(latest_change_time, "%Y-%m-%d %H:%M:%S")
                                diff_hours_utc = (datetime.utcnow() - change_dt).total_seconds() / 3600.0
                                diff_hours_local = (datetime.now() - change_dt).total_seconds() / 3600.0
                                best_diff = min(abs(diff_hours_utc), abs(diff_hours_local))
                                if best_diff > allowed_hours:
                                    is_allowed_time = False
                            except:
                                pass
                        
                        if is_allowed_time:
                            existing = next((r for r in results if r['id'] == eid and r['market'] == market_display), None)
                            if not existing:
                                results.append({
                                    'id': eid, 'date': date_str, 'sport': sport_name, 'match': f"{home} vs {away}",
                                    'market': market_display,
                                    'raw_market': raw_m_name, 'b365_info': " / ".join(best_details), 'ovr': reported_ovr,
                                    'change_time': latest_change_time or "N/A"
                                })

        # --- OUTPUT GENERATION ---
        results.sort(key=lambda x: x['ovr'])
        st.subheader("Opportunities (Ovr ASC)")

        if not results:
            st.info("No opportunities found matching your criteria.")
            return

        import re
        def extract_search_term(team_name):
            words = [w for w in re.split(r'[\s.,]+', team_name) if w]
            return max(words, key=len) if words else ""

        df_data = []
        for res in results:
            link = f"https://oddsfe.com/events/{res['id']}?mt={res['raw_market']}&live=False"
            parts = res['match'].split(" vs ")
            home_team = parts[0].strip() if len(parts) > 0 else ""
            away_team = parts[1].strip() if len(parts) > 1 else ""
            
            home_term = extract_search_term(home_team)
            away_term = extract_search_term(away_team)
            
            b365_search_home = f"https://www.bet365.com/#/AX/K%5E{urllib.parse.quote(home_term)}/" if home_term else ""
            b365_search_away = f"https://www.bet365.com/#/AX/K%5E{urllib.parse.quote(away_term)}/" if away_term else ""
            
            df_data.append({
                "Date": res['date'],
                "Sport": res['sport'],
                "Match": res['match'],
                "Market": res['market'],
                "Bookie Info": res['b365_info'],
                "Ovr %": f"{res['ovr']:.2f}%",
                "Updated": res['change_time'],
                "Event Link": link,
                "B365 Home": b365_search_home,
                "B365 Away": b365_search_away
            })
            
        if df_data:
            st.dataframe(df_data, use_container_width=True, column_config={
                "Event Link": st.column_config.LinkColumn("Oddsfe", display_text="🔗 Oddsfe"),
                "B365 Home": st.column_config.LinkColumn("B365 Home", display_text="🔗 B365 Home"),
                "B365 Away": st.column_config.LinkColumn("B365 Away", display_text="🔗 B365 Away")
            })

def get_last_update_date():
    try:
        # Versucht das Datum des letzten Git-Commits auszulesen
        result = subprocess.run(['git', 'log', '-1', '--format=%cd', '--date=format:%Y-%m-%d %H:%M'], 
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except:
        try:
            # Fallback auf Datei-Änderungsdatum
            mtime = os.path.getmtime(__file__)
            return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
        except:
            return "Unknown"

def main():
    st.set_page_config(page_title="DreamMachine365", page_icon="⚽", layout="wide")
    
    # Load default golden thresholds
    try:
        with open('config.json', 'r') as f:
            base_config = json.load(f)
        def_thr = base_config.get('golden_thresholds', {})
    except:
        def_thr = {}
        
    st.sidebar.header("🎯 Filter Settings")
    st.sidebar.markdown("Passe hier die Suchkriterien an:")
    
    with st.sidebar.form("thresholds_form"):
        min_main_volume = st.number_input("Min Main Volume", value=float(def_thr.get("min_main_volume", 1000.0)), step=100.0)
        min_market_books = st.number_input("Min Market Books", value=int(def_thr.get("min_market_books", 5)), min_value=1)
        max_combined_overround = st.number_input("Max Combined Overround (%)", value=float(def_thr.get("max_combined_overround", 2.0)), step=0.1)
        required_bookie = st.text_input("Required Bookie", value=def_thr.get("required_bookie_best_price", "BET365"))
        allowed_drop_pct = st.number_input("Allowed Odds Drop %", value=float(def_thr.get("allowed_bookie_odds_drop_pct", 3.0)), step=0.5)
        
        pr_default = def_thr.get("price_range", [1.3, 5.0])
        col1, col2 = st.columns(2)
        with col1: min_price = st.number_input("Min Price", value=float(pr_default[0]), step=0.1)
        with col2: max_price = st.number_input("Max Price", value=float(pr_default[1]), step=0.1)
        
        req_half_hc = st.checkbox("Require Half-Handicap for O/U", value=bool(def_thr.get("require_half_handicap_over_under", True)))
        last_update = st.number_input("Max Update Age (Hours)", value=float(def_thr.get("last_update_hours_ago", 3.0)), step=1.0)
        
        ignored_str = ", ".join(def_thr.get("ignored_markets", []))
        ignored_input = st.text_input("Ignored Markets (kommagetrennt)", value=ignored_str)
        
        st.form_submit_button("Parameter bestätigen")

    dynamic_thresholds = {
        "min_main_volume": min_main_volume,
        "min_market_books": min_market_books,
        "max_combined_overround": max_combined_overround,
        "required_bookie_best_price": required_bookie.strip(),
        "allowed_bookie_odds_drop_pct": allowed_drop_pct,
        "price_range": [min_price, max_price],
        "require_half_handicap_over_under": req_half_hc,
        "last_update_hours_ago": last_update,
        "ignored_markets": [m.strip() for m in ignored_input.split(",") if m.strip()]
    }

    st.title("⚽🎾🏀⚾🏒 DreamMachine365")
    
    version_date = get_last_update_date()
    st.caption(f"Version: {version_date}")
    
    st.markdown("Go big or go home")
    
    if st.button("Start Dreaming", type="primary"):
        st.subheader("Verwendete Parameter (Golden Thresholds):")
        st.json(dynamic_thresholds)
        
        with st.spinner("Fetching data from API..."):
            client = OddsFeedClient()
            client.run(override_thresholds=dynamic_thresholds)

if __name__ == "__main__":
    main()
