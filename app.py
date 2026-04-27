from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import os
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
from google import genai
import json

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

@app.route('/')
def index():
    return app.send_static_file('index.html')

REPORT_FILE = 'Report.csv'

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

def match_volunteer(issue_location, problem_type):
    if not os.path.exists('Volunteer.csv'):
        return None
        
    issue_loc_clean = issue_location.strip().lower()
    pt_clean = clean_problem_type(problem_type)
    
    needed_skills = []
    for k, v in SKILLS_MAP.items():
        if k in pt_clean:
            needed_skills.extend(v)
    
    # default skills if none mapped directly
    if not needed_skills:
        needed_skills = ['logistics', 'rescue']
        
    with open('Volunteer.csv', 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        volunteers = list(reader)
        
    # filter by availability and skills
    available_vols = []
    for v in volunteers:
        # Check new "Current Availability" column
        if v.get('Current Availability', '').strip().lower() == 'yes':
            vol_skills = [s.strip().lower() for s in v.get('Skills', '').split('|')]
            # check skill intersection
            if any(skill in vol_skills for skill in needed_skills) or any(req in " ".join(vol_skills) for req in needed_skills):
                available_vols.append(v)
                
    if not available_vols:
        return None
        
    # check exact location match
    for v in available_vols:
        if v.get('Location', '').strip().lower() == issue_loc_clean:
            return {'name': v.get('Name'), 'location': v.get('Location')}
            
    # check nearby location match
    nearby_locs = MUMBAI_ADJACENCY.get(issue_loc_clean, [])
    for v in available_vols:
        if v.get('Location', '').strip().lower() in nearby_locs:
            return {'name': v.get('Name'), 'location': v.get('Location')}
            
    return None

def clean_problem_type(pt):
    # For normalization, ignore case and leading/trailing whitespace
    return pt.strip().lower()

def is_medical(pt):
    pt_clean = clean_problem_type(pt)
    return 'medical' in pt_clean

def sort_reports():
    if not os.path.exists(REPORT_FILE):
        return

    # Read rows
    with open(REPORT_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not rows:
        return

    # Group by urgency
    urgency_groups = {
        'critical': [],
        'medium': [],
        'low': []
    }
    
    # Catch any unexpected urgency values and default them to 'low'
    for row in rows:
        urg = row.get('Urgency', '').strip().lower()
        if urg in urgency_groups:
            urgency_groups[urg].append(row)
        else:
            urgency_groups['low'].append(row)

    sorted_rows = []

    # Desired order of processing urgencies
    for urgency in ['critical', 'medium', 'low']:
        group_rows = urgency_groups[urgency]
        if not group_rows:
            continue

        # Frequency of problem type
        pt_counts = defaultdict(int)
        for r in group_rows:
            pt = clean_problem_type(r.get('Problem type', ''))
            pt_counts[pt] += 1
            
        # Group rows by problem type
        rows_by_pt = defaultdict(list)
        for r in group_rows:
            pt = clean_problem_type(r.get('Problem type', ''))
            rows_by_pt[pt].append(r)

        # Sort problem types based on rules:
        # 1. Is medical? (True first)
        # 2. Count (Descending)
        sorted_pts = sorted(rows_by_pt.keys(), key=lambda pt: (not is_medical(pt), -pt_counts[pt]))

        for pt in sorted_pts:
            pt_rows = rows_by_pt[pt]
            
            # Now sort within this problem type by location frequency
            loc_counts = defaultdict(int)
            for r in pt_rows:
                loc = r.get('Location', '').strip().lower()
                loc_counts[loc] += 1
            
            # Sort the specific rows by their location's frequency (descending)
            pt_rows.sort(key=lambda r: -loc_counts[r.get('Location', '').strip().lower()])
            
            sorted_rows.extend(pt_rows)

    # Write back to CSV
    with open(REPORT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_rows)

def ensure_report_schema():
    if not os.path.exists(REPORT_FILE):
        return
    with open(REPORT_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return
            
    if 'Matched Volunteer' not in headers:
        headers.append('Matched Volunteer')
        with open(REPORT_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        with open(REPORT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                row['Matched Volunteer'] = ''
                writer.writerow(row)

def update_volunteer_availability(name, status):
    vol_file = 'Volunteer.csv'
    if not os.path.exists(vol_file):
        return
        
    with open(vol_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        volunteers = list(reader)
        
    updated = False
    for v in volunteers:
        if v.get('Name') == name:
            v['Current Availability'] = status
            updated = True
            break
            
    if updated:
        with open(vol_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(volunteers)

@app.route('/api/report_issue', methods=['POST'])
def report_issue():
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    location = data.get('location', '')
    problem_type = data.get('problem_type', '')
    urgency = data.get('urgency', 'low')
    description = data.get('description', '')
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Match Volunteer First
    matched_volunteer = match_volunteer(location, problem_type)
    vol_name = matched_volunteer['name'] if matched_volunteer else ""

    ensure_report_schema()
    
    file_exists = os.path.isfile(REPORT_FILE)
    
    if file_exists:
        with open(REPORT_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                fieldnames = next(reader)
            except StopIteration:
                fieldnames = ['Location', 'Problem type', 'Urgency', 'description', 'Timestamp', 'Matched Volunteer']
    else:
        fieldnames = ['Location', 'Problem type', 'Urgency', 'description', 'Timestamp', 'Matched Volunteer']
    
    # Append to CSV
    with open(REPORT_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
            
        writer.writerow({
            'Location': location,
            'Problem type': problem_type,
            'Urgency': urgency,
            'description': description,
            'Timestamp': timestamp,
            'Matched Volunteer': vol_name
        })
        
    # Apply sorting logic
    sort_reports()
    
    if matched_volunteer:
        update_volunteer_availability(vol_name, 'no')
    
    return jsonify({
        'status': 'success', 
        'message': 'Issue reported and processed successfully.',
        'matched_volunteer': matched_volunteer
    }), 200

@app.route('/api/ai_summary', methods=['GET'])
def ai_summary():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        return jsonify({'error': 'Google Gemini API Key not configured. Please set GEMINI_API_KEY in backend .env file.'}), 500

    if not os.path.exists(REPORT_FILE):
        return jsonify({'error': 'No reports available to summarize.'}), 404

    with open(REPORT_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    if not rows:
        return jsonify({'error': 'No reports available to summarize.'}), 404

    report_data = []
    for r in rows:
        report_data.append(f"Location: {r.get('Location', '')}, Issue: {r.get('Problem type', '')}, Urgency: {r.get('Urgency', '')}, Description: {r.get('description', '')}")
    
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
    If they are reasonably accurate, return a JSON object with "isValid": true.
    If there is a clear mismatch (e.g. description is about a papercut but urgency is critical, or description is about a raging fire but problem type is water shortage), return "isValid": false, along with a suggested "problem_type" and "urgency", and a short "reason".
    Respond with ONLY a strict JSON object, no markdown formatting, no code blocks that contain ```json
    Example mismatch response: {{"isValid": false, "suggestion": {{"problem_type": "Fire", "urgency": "critical"}}, "reason": "The description mentions a raging fire, which is a critical fire emergency."}}
    Example valid response: {{"isValid": true}}
    """
    
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
        )
        
        # Parse result safely
        content = response.text.replace('```json', '').replace('```', '').strip()
        result = json.loads(content)
        return jsonify(result), 200
    except Exception as e:
        print(f"Validation error: {e}")
        return jsonify({"isValid": True, "note": "Validation skipped due to AI error"}), 200

@app.route('/api/register_volunteer', methods=['POST'])
def register_volunteer():
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    name = data.get('name', '')
    skills = data.get('skills', '')
    location = data.get('location', '')
    availability = data.get('availability', '')
    
    if not name or not skills or not location or not availability:
        return jsonify({'error': 'Missing required fields'}), 400
        
    file_exists = os.path.isfile('Volunteer.csv')
    
    try:
        with open('Volunteer.csv', 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['Name', 'Skills', 'Location', 'Availability', 'Current Availability']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
                
            writer.writerow({
                'Name': name,
                'Skills': skills,
                'Location': location,
                'Availability': availability,
                'Current Availability': 'yes'
            })
            
        return jsonify({
            'status': 'success', 
            'message': 'Volunteer registered successfully.'
        }), 200
    except Exception as e:
        return jsonify({'error': f"Failed to save volunteer: {str(e)}"}), 500

@app.route('/api/get_reports', methods=['GET'])
def get_reports():
    if not os.path.exists(REPORT_FILE):
        return jsonify([])
        
    try:
        with open(REPORT_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            reports = list(reader)
            
        result = []
        for r in reports:
            loc = r.get('Location', '')
            pt = r.get('Problem type', '')
            urgency = r.get('Urgency', '')
            timestamp = r.get('Timestamp', '')
            vol_name = r.get('Matched Volunteer', '')
            
            mv = {'name': vol_name} if vol_name else None
            
            result.append({
                'location': loc,
                'problem_type': pt,
                'urgency': urgency,
                'timestamp': timestamp,
                'matched_volunteer': mv
            })
            
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
