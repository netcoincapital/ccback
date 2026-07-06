"""Provision Firebase to GCP project and create service account key."""
import urllib.request
import urllib.error
import json
import os
import subprocess
import sys

PROJECT = "omega-bearing-446811-p5"
KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "firebase-admin-key.json")

def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"$ {' '.join(cmd)}")
    out = (result.stdout or "")[:2000]
    err = (result.stderr or "")[:500]
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print(f"  exit: {result.returncode}")
    return result.stdout.strip() if result.returncode == 0 else None

# Get access token
print("=== Getting access token ===")
token = run(["gcloud", "auth", "print-access-token"])
if not token:
    sys.exit(1)

# Check Firebase status
print("\n=== Checking Firebase status ===")
req = urllib.request.Request(
    f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}",
    headers={"Authorization": f"Bearer {token}"}
)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        print("Status:", json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body[:500]}")

# Provision Firebase
print(f"\n=== Provisioning Firebase for {PROJECT} ===")
req2 = urllib.request.Request(
    f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}:addFirebase",
    data=b"{}",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    method="POST"
)
try:
    with urllib.request.urlopen(req2) as resp:
        data = json.loads(resp.read())
        print("Provision result:", json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    body = e.read().decode()[:500]
    print(f"HTTP {e.code}: {body}")
    if "already" in body.lower() or "exists" in body.lower():
        print("Firebase already provisioned!")
    else:
        print("Provision failed. Trying alternative...")

# After provisioning, list all service accounts
print(f"\n=== Listing all service accounts ===")
all_sa = run(["gcloud", "iam", "service-accounts", "list", "--project", PROJECT, "--format=json"])
if all_sa:
    try:
        accounts = json.loads(all_sa)
        for sa in accounts:
            print(f"  - {sa['email']} ({sa.get('displayName', 'N/A')})")
    except:
        print(all_sa)

# Try creating key for Firebase admin SA
print("\n=== Trying to create key ===")
for sa_suffix in [
    "firebase-adminsdk-fbsvc",
    "firebase-adminsdk",
    "firebase-storage",
]:
    email = f"{sa_suffix}@{PROJECT}.iam.gserviceaccount.com"
    result = run([
        "gcloud", "iam", "service-accounts", "keys", "create", KEY_PATH,
        "--iam-account", email, "--project", PROJECT
    ])
    if result:
        print(f"SUCCESS! Key created for {email}")
        break
    print(f"  Failed for {email}")

print("\n=== Done ===")
