from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
from google import genai
import json
import csv

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Database Setup
# Use DATABASE_URL from Render, otherwise use local SQLite
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///helping_hands.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---

class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    skills = db.Column(db.String(500)) # Stored as pipe-separated string
    location = db.Column(db.String(100))
    availability = db.Column(db.String(100))
    current_availability = db.Column(db.String(10), default='yes')

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100))
    problem_type = db.Column(db.String(100))
    urgency = db.Column(db.String(20))
    description = db.Column(db.Text)
    timestamp = db.Column(db.String(50))
    matched_volunteer = db.Column(db.String(100))

# Create tables
with app.app_context():
    db.create_all()

# Logic Constants
SKILLS_MAP = {
    'medical': ['first aid', 'nurse', 'doctor', 'cpr', 'medical doctor', 'medical nurse'],
    'fire': ['rescue', 'firefighting'],
    'flood': ['rescue', 'swimming', 'water management'],
    'water': ['water management', 'logistics'],
    'food': ['food distribution', 'logistics']
}

MUMBAI_ADJACENCY = {
    'andheri': ['juhu', 'bandra', 'borivali', 'powai'],
    'juhu': ['andheri', 'bandra'],
    'bandra': ['andheri', 'juhu', 'dadar', 'kurla'],
    'kurla': ['bandra', 'sion', 'dadar', 'powai'],
    'dadar': ['bandra', 'kurla', 'sion', 'colaba'],
    'colaba': ['dadar'],
    'borivali': ['kandivali', 'andheri'],
    'kandivali': ['borivali', 'andheri'],
    'powai': ['andheri', 'kurla'],
    'sion': ['kurla', 'dadar']
}

# --- Helper Logic ---

def clean_problem_type(pt):
    return pt.strip().lower() if pt else ""

def match_volunteer(issue_location, problem_type):
    issue_loc_clean = issue_location.strip().lower()
    pt_clean = clean_problem_type(problem_type)
    
    print(f"DEBUG: Matching for Loc: {issue_loc_clean}, Problem: {pt_clean}")
    
    needed_skills = []
    for k, v in SKILLS_MAP.items():
        if k in pt_clean:
            needed_skills.extend(v)
    
    if not needed_skills:
        needed_skills = ['logistics', 'rescue']
        
    print(f"DEBUG: Needed skills identified: {needed_skills}")
        
    # Query only available volunteers
    available_vols = Volunteer.query.filter_by(current_availability='yes').all()
    print(f"DEBUG: Total available volunteers found in DB: {len(available_vols)}")
    
    valid_vols = []
    for v in available_vols:
        # Broad checks: check if any skill words appear in the volunteer's skill list
        vol_skills_full = (v.skills or "").lower()
        vol_skills_list = [s.strip().lower() for s in vol_skills_full.split('|')]
        
        has_skill = False
        for skill in needed_skills:
            if skill in vol_skills_full or any(skill in s for s in vol_skills_list):
                has_skill = True
                break
        
        if has_skill:
            valid_vols.append(v)
                
    print(f"DEBUG: Volunteers with matching skills: {len(valid_vols)}")
    if not valid_vols:
        return None
        
    # 1. Check exact location match
    for v in valid_vols:
        if (v.location or "").strip().lower() == issue_loc_clean:
            print(f"DEBUG: Exact location match found: {v.name}")
            return {'name': v.name, 'location': v.location}
            
    # 2. Check nearby location match
    nearby_locs = MUMBAI_ADJACENCY.get(issue_loc_clean, [])
    print(f"DEBUG: Checking nearby locations for {issue_loc_clean}: {nearby_locs}")
    for v in valid_vols:
        if (v.location or "").strip().lower() in nearby_locs:
            print(f"DEBUG: Nearby location match found: {v.name} at {v.location}")
            return {'name': v.name, 'location': v.location}
            
    print("DEBUG: No location match found.")
    return None

# --- API Endpoints ---

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/report_issue', methods=['POST'])
def report_issue():
    data = request.json
    if not data: return jsonify({'error': 'No data'}), 400
        
    location = data.get('location', '')
    problem_type = data.get('problem_type', '')
    urgency = data.get('urgency', 'low')
    description = data.get('description', '')
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Match Volunteer
    matched = match_volunteer(location, problem_type)
    vol_name = matched['name'] if matched else ""

    # Save to DB
    new_report = Report(
        location=location,
        problem_type=problem_type,
        urgency=urgency,
        description=description,
        timestamp=timestamp,
        matched_volunteer=vol_name
    )
    db.session.add(new_report)
    
    # Update volunteer if matched
    if matched:
        vol = Volunteer.query.filter_by(name=vol_name).first()
        if vol:
            vol.current_availability = 'no'
    
    db.session.commit()
    
    return jsonify({
        'status': 'success', 
        'message': 'Issue reported and processed successfully.',
        'matched_volunteer': matched
    }), 200

@app.route('/api/get_reports', methods=['GET'])
def get_reports():
    # Fetch all reports
    reports = Report.query.all()
    
    result = []
    for r in reports:
        # Check if matched_volunteer has a real name (not just an empty string)
        has_volunteer = r.matched_volunteer and len(r.matched_volunteer.strip()) > 0
        
        result.append({
            'location': r.location,
            'problem_type': r.problem_type,
            'urgency': r.urgency,
            'timestamp': r.timestamp,
            'matched_volunteer': {'name': r.matched_volunteer} if has_volunteer else None
        })
    return jsonify(result), 200

@app.route('/api/register_volunteer', methods=['POST'])
def register_volunteer():
    data = request.json
    if not data: return jsonify({'error': 'No data'}), 400
        
    new_v = Volunteer(
        name=data.get('name', ''),
        skills=data.get('skills', ''),
        location=data.get('location', ''),
        availability=data.get('availability', ''),
        current_availability='yes'
    )
    db.session.add(new_v)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Volunteer registered successfully.'}), 200

@app.route('/api/ai_summary', methods=['GET'])
def ai_summary():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return jsonify({'error': 'No API Key'}), 500

    reports = Report.query.all()
    if not reports: return jsonify({'error': 'No reports'}), 404

    report_data = []
    for r in reports:
        report_data.append(f"Location: {r.location}, Issue: {r.problem_type}, Urgency: {r.urgency}, Description: {r.description}")
    
    report_text = "\n".join(report_data)

    prompt = f"""
Here is the reported issue data from our platform:
{report_text}

Based on this data, please summarize the situation. DO NOT repeat the questions in your output. Only provide the answers directly, numbered 1 to 4. Each answer must be short and clear (1-2 lines each):
1. What is the most affected area and by what it is affected?
2. What is the most common issue and where is it commonly suffered?
3. Which area needs immediate attention?
4. Provide a short actionable suggestion (if any).

Format your response exactly like this:
1. [Your answer here]
2. [Your answer here]
3. [Your answer here]
4. [Your answer here]
"""
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
        )
        return jsonify({'summary': response.text}), 200
    except Exception as e:
        return jsonify({'error': f"Failed to generate summary: {str(e)}"}), 500

@app.route('/api/validate_issue', methods=['POST'])
def validate_issue():
    data = request.json
    problem_type = data.get('problem_type', '')
    urgency = data.get('urgency', '')
    description = data.get('description', '')

    prompt = f"""
    You are an AI assistant helping to triage emergency reports.
    A user has reported an issue.
    Description: "{description}"
    Problem Type selected: "{problem_type}"
    Urgency selected: "{urgency}"

    Validate if the Problem Type and Urgency match the severity and nature of the description. 
    Respond with ONLY a strict JSON object (isValid, suggestion, reason).
    """
    try:
        client = genai.Client()
        response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
        content = response.text.replace('```json', '').replace('```', '').strip()
        result = json.loads(content)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"isValid": True}), 200

# --- DATA SEEDING (Robust transfer for Render) ---
def seed_data():
    with app.app_context():
        # Clean Seed Volunteers
        vol_csv = 'Volunteer.csv'
        if os.path.exists(vol_csv):
            with open(vol_csv, 'r', encoding='utf-8-sig') as f: # -sig handles BOM
                reader = csv.DictReader(f)
                # Clean headers (remove spaces/quotes)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                
                for row in reader:
                    name = row.get('Name')
                    if name and not Volunteer.query.filter_by(name=name).first():
                        db.session.add(Volunteer(
                            name=name,
                            skills=row.get('Skills'),
                            location=row.get('Location'),
                            availability=row.get('Availability'),
                            current_availability='yes'
                        ))
            db.session.commit()
        
        # Clean Seed Reports
        rep_csv = 'Report.csv'
        if os.path.exists(rep_csv):
            with open(rep_csv, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                
                for row in reader:
                    desc = row.get('description')
                    # Use description + timestamp as a unique check
                    if desc and not Report.query.filter_by(description=desc, timestamp=row.get('Timestamp')).first():
                        db.session.add(Report(
                            location=row.get('Location'),
                            problem_type=row.get('Problem type'),
                            urgency=row.get('Urgency'),
                            description=desc,
                            timestamp=row.get('Timestamp'),
                            matched_volunteer=row.get('Matched Volunteer', '')
                        ))
            db.session.commit()

# --- MANUAL DATABASE SEEDING (FORCED) ---
@app.route('/api/manual_seed')
def manual_seed():
    volunteers_to_add = [
        {"name": "Rahul Sharma", "skills": "First Aid | Rescue", "location": "Andheri"},
        {"name": "Anish Patel", "skills": "Doctor", "location": "Bandra"},
        {"name": "Priya Mehta", "skills": "Transport | Logistics", "location": "Bandra"},
        {"name": "Amit Kumar", "skills": "Medical Doctor", "location": "Kurla"},
        {"name": "Sneha Desai", "skills": "Water Management", "location": "Dadar"},
        {"name": "Vikas Singh", "skills": "Heavy Machinery | Rescue", "location": "Borivali"},
        {"name": "Neha Gupta", "skills": "Food Distribution", "location": "Juhu"},
        {"name": "Rohan Patil", "skills": "First Aid", "location": "Kandivali"},
        {"name": "Vikram Joshi", "skills": "Rescue | Swimming", "location": "Colaba"},
        {"name": "Pooja Nair", "skills": "Medical Nurse", "location": "Powai"},
        {"name": "Sanjay Verma", "skills": "Logistics", "location": "Sion"},
        {"name": "Shraddha Pawar", "skills": "Water Department Official", "location": "Dadar"}
    ]
    
    count = 0
    for v_data in volunteers_to_add:
        if not Volunteer.query.filter_by(name=v_data['name']).first():
            new_v = Volunteer(
                name=v_data['name'],
                skills=v_data['skills'],
                location=v_data['location'],
                availability="Anytime",
                current_availability="yes"
            )
            db.session.add(new_v)
            count += 1
    
    db.session.commit()
    return f"Successfully added {count} volunteers to the database!"

@app.route('/api/reset_db')
def reset_db():
    try:
        # Delete all reports
        Report.query.delete()
        # Reset all volunteers to available
        volunteers = Volunteer.query.all()
        for v in volunteers:
            v.current_availability = 'yes'
        db.session.commit()
        return "Database Reset! All reports cleared and volunteers are now available."
    except Exception as e:
        return f"Error resetting database: {str(e)}"

@app.route('/api/debug_db')
def debug_db():
    v_count = Volunteer.query.count()
    r_count = Report.query.count()
    return jsonify({
        'volunteers': v_count,
        'reports': r_count,
        'database_url_exists': bool(os.environ.get("DATABASE_URL")),
        'manual_seed_url': '/api/manual_seed',
        'reset_db_url': '/api/reset_db'
    })

if __name__ == '__main__':
    seed_data()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
