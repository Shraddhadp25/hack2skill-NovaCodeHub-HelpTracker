
from app import app, db, Report
with app.app_context():
    reports = Report.query.all()
    print(f"Total reports: {len(reports)}")
    for r in reports:
        print(f"ID: {r.id}, Loc: {r.location}, Prob: {r.problem_type}, Matched: {r.matched_volunteer}")
