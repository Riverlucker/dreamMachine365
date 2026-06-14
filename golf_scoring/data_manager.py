"""
Data manager for the Golf Tournament Live Scoring App.
Handles thread-safe reading and writing of JSON data files.
"""
import os
import json
import threading
from typing import Any, Optional

# Threading lock to ensure concurrent requests to Streamlit don't cause file corruption
LOCK = threading.Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
COURSES_DIR = os.path.join(DATA_DIR, "courses")
TOURNAMENT_FILE = os.path.join(DATA_DIR, "tournament.json")
TEMPLATE_FILE = os.path.join(DATA_DIR, "tournament_template.json")
SCORES_FILE = os.path.join(DATA_DIR, "scores.json")

def get_audit_file(event_id: str) -> str:
    """Returns the file path for the audit log."""
    return os.path.join(DATA_DIR, f"{event_id}_audit.json")

def load_audit_log(event_id: str = "45_loch_challenge") -> list:
    """Loads the audit log entries."""
    with LOCK:
        path = get_audit_file(event_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading audit file for {event_id}: {e}")
        return []

def save_audit_log(log_data: list, event_id: str = "45_loch_challenge") -> bool:
    """Saves the audit log entries."""
    with LOCK:
        try:
            with open(get_audit_file(event_id), "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving audit file for {event_id}: {e}")
            return False

def reset_audit_log(event_id: str = "45_loch_challenge") -> bool:
    """Clears the audit log."""
    return save_audit_log([], event_id)

# Ensure directories exist
os.makedirs(COURSES_DIR, exist_ok=True)

def list_courses() -> list[dict]:
    """Lists all available golf courses by reading JSON files in data/courses/."""
    courses = []
    with LOCK:
        if os.path.exists(COURSES_DIR):
            for filename in os.listdir(COURSES_DIR):
                if filename.endswith(".json"):
                    path = os.path.join(COURSES_DIR, filename)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            # Ensure required keys exist
                            if "id" in data and "name" in data and "holes" in data:
                                courses.append(data)
                    except Exception as e:
                        print(f"Error loading course {filename}: {e}")
    return sorted(courses, key=lambda x: x["name"])

def load_course(course_id: str) -> Optional[dict]:
    """Loads a specific golf course JSON."""
    with LOCK:
        path = os.path.join(COURSES_DIR, f"{course_id}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading course file {course_id}: {e}")
        # Fallback search in directory if ID is slightly different
        for course in list_courses():
            if course["id"] == course_id:
                return course
    return None

def save_course(course_data: dict) -> bool:
    """Saves a course configuration to courses directory."""
    if "id" not in course_data or "name" not in course_data or "holes" not in course_data:
        return False
    with LOCK:
        path = os.path.join(COURSES_DIR, f"{course_data['id']}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(course_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving course: {e}")
            return False

def get_tournament_file(event_id: str) -> str:
    """Returns the file path for a tournament configuration."""
    return os.path.join(DATA_DIR, f"{event_id}_tournament.json")

def get_scores_file(event_id: str) -> str:
    """Returns the file path for scores."""
    return os.path.join(DATA_DIR, f"{event_id}_scores.json")

def load_tournament(event_id: str = "45_loch_challenge") -> dict:
    """
    Loads the tournament configuration for a specific event.
    Returns None if the file does not exist.
    """
    with LOCK:
        target_path = get_tournament_file(event_id)
        if not os.path.exists(target_path):
            return None
        
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading tournament file for {event_id}: {e}")
            return None

def save_tournament(data: dict, event_id: str = "45_loch_challenge") -> bool:
    """Saves tournament configuration for a specific event."""
    with LOCK:
        try:
            with open(get_tournament_file(event_id), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving tournament file for {event_id}: {e}")
            return False

def load_scores(event_id: str = "45_loch_challenge") -> dict:
    """Loads all entered scores for a specific event from scores JSON."""
    with LOCK:
        path = get_scores_file(event_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading scores file for {event_id}: {e}")
        return {}

def save_scores(scores: dict, event_id: str = "45_loch_challenge") -> bool:
    """Saves all scores for a specific event to scores JSON."""
    with LOCK:
        try:
            with open(get_scores_file(event_id), "w", encoding="utf-8") as f:
                json.dump(scores, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving scores file for {event_id}: {e}")
            return False

import datetime

def update_scores_bulk(event_id: str, round_id: str, hole_number: int, player_scores: dict[str, int], username: str = "System") -> bool:
    """
    Safely updates gross scores for multiple players on a specific hole.
    player_scores is a dict mapping player_id -> gross_score (int).
    Appends the change to the audit log.
    """
    scores = load_scores(event_id)
    audit_log = load_audit_log(event_id)
    
    if round_id not in scores:
        scores[round_id] = {}
        
    hole_str = str(hole_number)
    now_iso = datetime.datetime.now().isoformat()
    
    for player_id, score in player_scores.items():
        if player_id not in scores[round_id]:
            scores[round_id][player_id] = {}
            
        old_score = scores[round_id][player_id].get(hole_str)
            
        if score is None or score <= 0:
            # Clear score if 0 or None
            if hole_str in scores[round_id][player_id]:
                del scores[round_id][player_id][hole_str]
        else:
            scores[round_id][player_id][hole_str] = int(score)
            
        # Add to audit log if score changed
        if old_score != score:
            now_dt = datetime.datetime.fromisoformat(now_iso)
            updated_existing = False
            
            # Look backwards in the log to find a recent entry to update
            for i in range(len(audit_log) - 1, -1, -1):
                entry = audit_log[i]
                if (entry.get("username") == username and
                    entry.get("round_id") == round_id and
                    entry.get("player_id") == player_id and
                    entry.get("hole_number") == hole_number):
                    
                    try:
                        entry_dt = datetime.datetime.fromisoformat(entry.get("timestamp", ""))
                        if (now_dt - entry_dt).total_seconds() <= 60:
                            # Update existing entry instead of creating a new one
                            entry["score"] = score if score is not None and score > 0 else 0
                            entry["timestamp"] = now_iso
                            updated_existing = True
                        break # Found the most recent entry for this user/hole, no need to look further
                    except ValueError:
                        pass
                        
            if not updated_existing:
                audit_log.append({
                    "timestamp": now_iso,
                    "username": username,
                    "round_id": round_id,
                    "hole_number": hole_number,
                    "player_id": player_id,
                    "score": score if score is not None and score > 0 else 0
                })
            
    save_audit_log(audit_log, event_id)
    return save_scores(scores, event_id)

def reset_scores(event_id: str = "45_loch_challenge") -> bool:
    """Clears all scores for a specific event."""
    return save_scores({}, event_id)

def export_backup(event_id: str = "45_loch_challenge") -> str:
    """Exports all configurations and scores for a specific event as a single JSON string."""
    tournament = load_tournament(event_id)
    scores = load_scores(event_id)
    courses = list_courses()
    
    backup_data = {
        "tournament": tournament,
        "scores": scores,
        "courses": courses
    }
    return json.dumps(backup_data, indent=2, ensure_ascii=False)

def import_backup(event_id: str, backup_str: str) -> bool:
    """
    Imports a backup JSON string. Restores courses, tournament configurations,
    and all entered scores for the current event.
    """
    try:
        data = json.loads(backup_str)
        if "tournament" not in data or "scores" not in data:
            return False
            
        # Save tournament
        save_tournament(data["tournament"], event_id)
        
        # Save scores
        save_scores(data["scores"], event_id)
        
        # Save courses if included
        if "courses" in data:
            for course_data in data["courses"]:
                save_course(course_data)
                
        return True
    except Exception as e:
        print(f"Error importing backup for {event_id}: {e}")
        return False
