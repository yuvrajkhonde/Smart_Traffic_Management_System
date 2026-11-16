import os
import sys
import uuid
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from backend.core.database import supabase
from backend.core.auth_service import hash_password

accounts = [
    {
        "email": "admin@bhopaltraffic.in",
        "password": "admin123",
        "role": "admin",
        "badge_number": "ADMIN01",
        "phone": "+919876500001"
    },
    {
        "email": "officer@bhopaltraffic.in",
        "password": "officer123",
        "role": "officer",
        "badge_number": "BPL101",
        "phone": "+919876500002"
    },
    {
        "email": "citizen@bhopaltraffic.in",
        "password": "citizen123",
        "role": "citizen",
        "badge_number": None,
        "phone": "+919876500003"
    }
]

created = []
for acc in accounts:
    # Check if user already exists
    existing = supabase.table("users").select("id").eq("email", acc["email"]).execute()
    if existing.data:
        user_id = existing.data[0]["id"]
        print(f"User already exists: {acc['email']}")
    else:
        user_res = supabase.table("users").insert({
            "email": acc["email"],
            "password": hash_password(acc["password"]),
            "phone": acc["phone"]
        }).execute()
        user_id = user_res.data[0]["id"]
        
        # Insert user role
        role_payload = {
            "user_id": user_id,
            "role": acc["role"]
        }
        if acc["badge_number"]:
            role_payload["badge_number"] = acc["badge_number"]
        supabase.table("user_roles").insert(role_payload).execute()
        print(f"Successfully created {acc['role']} account: {acc['email']}")
    
    created.append((acc["role"], acc["email"], acc["password"], acc["badge_number"]))

print("\n" + "="*60)
print("ACCOUNTS PROVISIONED SUCCESSFULLY")
print("="*60)
for role, email, pwd, badge in created:
    b_str = f" [Badge: {badge}]" if badge else ""
    print(f"  Role: {role.upper():<8}{b_str:<18} -> Email: {email:<26} Password: {pwd}")
print("="*60)
