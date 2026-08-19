import urllib.request
import urllib.error
import json
import uuid

def test_api():
    base = "http://127.0.0.1:8000"
    uid = uuid.uuid4().hex[:6]
    
    # 1. Test problems list
    req = urllib.request.urlopen(f"{base}/api/problems")
    probs = json.loads(req.read().decode())
    has_open_inno = any(p.get("is_open_innovation") for p in probs)
    print(f"[TEST 1] Loaded {len(probs)} problems from FastAPI backend. Open Innovation present: {has_open_inno}")
    
    # 2. Test registration with 6 members & 1 female
    team_name = f"Cyber Titans {uid}"
    leader_email = f"aarav_{uid}@gtmc.edu"
    reg_payload = {
        "team_name": team_name,
        "college": "GTMC Nanded",
        "university": "SRTMUN",
        "city": "Nanded",
        "state": "Maharashtra",
        "leader_name": "Aarav Sharma",
        "leader_email": leader_email,
        "leader_phone": "9876543210",
        "leader_gender": "Male",
        "leader_branch": "CSE",
        "leader_year": "3rd Year",
        "selected_problem_id": "OPEN_INNOVATION",
        "is_open_innovation": True,
        "open_innovation_title": "AI Smart Agriculture Drone",
        "members": [
            {"full_name": "Aarav Sharma", "email": leader_email, "phone": "9876543210", "gender": "Male", "branch": "CSE", "year": "3rd Year"},
            {"full_name": "Sneha Patil", "email": f"sneha_{uid}@gtmc.edu", "phone": "9876543211", "gender": "Female", "branch": "CSE", "year": "3rd Year"},
            {"full_name": "Rohan Deshmukh", "email": f"rohan_{uid}@gtmc.edu", "phone": "9876543212", "gender": "Male", "branch": "IT", "year": "3rd Year"},
            {"full_name": "Ananya Kulkarni", "email": f"ananya_{uid}@gtmc.edu", "phone": "9876543213", "gender": "Female", "branch": "CSE", "year": "2nd Year"},
            {"full_name": "Vikram Shinde", "email": f"vikram_{uid}@gtmc.edu", "phone": "9876543214", "gender": "Male", "branch": "AI&DS", "year": "3rd Year"},
            {"full_name": "Aditya Joshi", "email": f"aditya_{uid}@gtmc.edu", "phone": "9876543215", "gender": "Male", "branch": "CSE", "year": "3rd Year"}
        ]
    }
    
    data = json.dumps(reg_payload).encode()
    req = urllib.request.Request(f"{base}/api/register", data=data, headers={"Content-Type": "application/json"}, method="POST")
    res = urllib.request.urlopen(req)
    res_data = json.loads(res.read().decode())
    print(f"[TEST 2] Registration Success: Team ID = {res_data['team_id']}, Reg ID = {res_data['registration_id']}")
    
    # 3. Test Dashboard Lookup by Email + Team Name
    lookup_payload = {"email": leader_email, "team_name": team_name}
    req = urllib.request.Request(f"{base}/api/dashboard/lookup", data=json.dumps(lookup_payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    res = urllib.request.urlopen(req)
    lookup_data = json.loads(res.read().decode())
    print(f"[TEST 3] Dashboard Lookup Success: Found '{lookup_data['team']['team_name']}', Members Count = {len(lookup_data['members'])}")

    # 4. Test UTR Submission
    utr_val = f"SBI{uid.upper()}9988"
    utr_payload = {"team_id": res_data['team_id'], "utr": utr_val}
    req = urllib.request.Request(f"{base}/api/payments/utr", data=json.dumps(utr_payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    res = urllib.request.urlopen(req)
    utr_data = json.loads(res.read().decode())
    print(f"[TEST 4] UTR Submit Success: {utr_data['message']}")

    # 5. Test Duplicate Team Name Rejection
    try:
        req = urllib.request.Request(f"{base}/api/register", data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req)
        print("[TEST 5 ERROR] Duplicate team name was NOT rejected!")
    except urllib.error.HTTPError as e:
        err_msg = json.loads(e.read().decode())
        print(f"[TEST 5 PASS] Duplicate team name properly blocked with 400: {err_msg.get('detail')}")

    # 6. Test Duplicate UTR Rejection & Unique Emails
    team_b_payload = dict(reg_payload)
    team_b_payload["team_name"] = f"Cyber Titans Beta {uid}"
    team_b_payload["leader_email"] = f"leader_beta_{uid}@gtmc.edu"
    team_b_payload["members"] = [
        {"full_name": "Beta Leader", "email": f"leader_beta_{uid}@gtmc.edu", "phone": "9876543900", "gender": "Male", "branch": "CSE", "year": "3rd Year"},
        {"full_name": "Beta Member 2", "email": f"sneha_b_{uid}@gtmc.edu", "phone": "9876543901", "gender": "Female", "branch": "CSE", "year": "3rd Year"},
        {"full_name": "Beta Member 3", "email": f"rohan_b_{uid}@gtmc.edu", "phone": "9876543902", "gender": "Male", "branch": "IT", "year": "3rd Year"},
        {"full_name": "Beta Member 4", "email": f"ananya_b_{uid}@gtmc.edu", "phone": "9876543903", "gender": "Female", "branch": "CSE", "year": "2nd Year"},
        {"full_name": "Beta Member 5", "email": f"vikram_b_{uid}@gtmc.edu", "phone": "9876543904", "gender": "Male", "branch": "AI&DS", "year": "3rd Year"},
        {"full_name": "Beta Member 6", "email": f"aditya_b_{uid}@gtmc.edu", "phone": "9876543905", "gender": "Male", "branch": "CSE", "year": "3rd Year"}
    ]
    
    req_b = urllib.request.Request(f"{base}/api/register", data=json.dumps(team_b_payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    res_b = urllib.request.urlopen(req_b)
    team_b_data = json.loads(res_b.read().decode())
    
    try:
        dup_utr_req = urllib.request.Request(
            f"{base}/api/payments/utr",
            data=json.dumps({"team_id": team_b_data['team_id'], "utr": utr_val}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(dup_utr_req)
        print("[TEST 6 ERROR] Duplicate UTR was NOT rejected!")
    except urllib.error.HTTPError as e:
        err_msg = json.loads(e.read().decode())
        print(f"[TEST 6 PASS] Duplicate UTR properly blocked with 400: {err_msg.get('detail')}")

    # 6B. Test Same Email Allowed (Team Name must still be unique)
    try:
        dup_email_payload = dict(team_b_payload)
        dup_email_payload["team_name"] = f"Cyber Titans Gamma {uid}"
        dup_email_payload["leader_email"] = leader_email # Reuse existing registered leader email!
        dup_email_req = urllib.request.Request(f"{base}/api/register", data=json.dumps(dup_email_payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        res_email = urllib.request.urlopen(dup_email_req)
        res_email_data = json.loads(res_email.read().decode())
        print(f"[TEST 6B PASS] Same email registration allowed as requested! New Team ID: {res_email_data['team_id']}")
    except urllib.error.HTTPError as e:
        err_msg = json.loads(e.read().decode())
        print(f"[TEST 6B FAIL] Duplicate Email was rejected when it should be allowed: {err_msg.get('detail')}")

    # 7. Test Open Innovation Registration
    team_open_payload = dict(reg_payload)
    team_open_payload["team_name"] = f"Open Innovators AI {uid}"
    team_open_payload["leader_email"] = f"innovator_{uid}@gtmc.edu"
    team_open_payload["members"] = [
        {"full_name": "Inno Leader", "email": f"innovator_{uid}@gtmc.edu", "phone": "9876543800", "gender": "Male", "branch": "CSE", "year": "3rd Year"},
        {"full_name": "Inno Member 2", "email": f"sneha_inno_{uid}@gtmc.edu", "phone": "9876543801", "gender": "Female", "branch": "CSE", "year": "3rd Year"},
        {"full_name": "Inno Member 3", "email": f"rohan_inno_{uid}@gtmc.edu", "phone": "9876543802", "gender": "Male", "branch": "IT", "year": "3rd Year"},
        {"full_name": "Inno Member 4", "email": f"ananya_inno_{uid}@gtmc.edu", "phone": "9876543803", "gender": "Female", "branch": "CSE", "year": "2nd Year"},
        {"full_name": "Inno Member 5", "email": f"vikram_inno_{uid}@gtmc.edu", "phone": "9876543804", "gender": "Male", "branch": "AI&DS", "year": "3rd Year"},
        {"full_name": "Inno Member 6", "email": f"aditya_inno_{uid}@gtmc.edu", "phone": "9876543805", "gender": "Male", "branch": "CSE", "year": "3rd Year"}
    ]
    team_open_payload["selected_problem_id"] = "OPEN_INNOVATION"
    team_open_payload["is_open_innovation"] = True
    team_open_payload["open_innovation_title"] = "AI Drone Swarm for Precision Agriculture"
    team_open_payload["open_innovation_description"] = "Real-time edge compute drone swarm using computer vision to detect crop diseases and soil moisture."
    
    req_open = urllib.request.Request(f"{base}/api/register", data=json.dumps(team_open_payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    res_open = urllib.request.urlopen(req_open)
    open_data = json.loads(res_open.read().decode())
    print(f"[TEST 7 PASS] Open Innovation Registration Success: Team '{open_data['team_name']}' created!")

    # 8. Test Offline Cash Payment Submission
    offline_payload = {
        "team_id": open_data["team_id"],
        "payment_mode": "OFFLINE_CASH",
        "collector_name": "Onkar Bhaskar Nagargoje",
        "receipt_no": f"REC-{uid.upper()}"
    }
    req_off = urllib.request.Request(
        f"{base}/api/payments/utr",
        data=json.dumps(offline_payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    res_off = urllib.request.urlopen(req_off)
    off_res_data = json.loads(res_off.read().decode())
    print(f"[TEST 8 PASS] Offline Cash Payment Submitted: Mode={off_res_data['payment_mode']}, Collector={off_res_data['collector_name']}, Receipt={off_res_data['receipt_no']}")

if __name__ == "__main__":
    test_api()
