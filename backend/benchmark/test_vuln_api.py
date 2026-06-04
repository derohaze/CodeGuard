"""Start the vulnerable benchmark API and verify it works."""
import sys, time, subprocess, httpx

sys.path.insert(0, ".")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "benchmark.vuln_api:app",
     "--host", "127.0.0.1", "--port", "9000", "--log-level", "error"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

try:
    for attempt in range(15):
        try:
            r = httpx.get("http://127.0.0.1:9000/health", timeout=3)
            if r.status_code == 200:
                print(f"API ready (attempt {attempt + 1})")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        print("FAILED: API did not start")
        sys.exit(1)

    # Test endpoints
    r = httpx.get("http://127.0.0.1:9000/health")
    print(f"GET /health -> {r.status_code} {r.json()}")

    r = httpx.get("http://127.0.0.1:9000/api/users/1")
    print(f"GET /api/users/1 -> {r.status_code}")

    r = httpx.post("http://127.0.0.1:9000/api/auth/login",
        json={"username": "admin", "password": "password123"})
    print(f"POST /api/auth/login(admin) -> {r.status_code}")

    r = httpx.get("http://127.0.0.1:9000/api/files/readme.txt")
    print(f"GET /api/files/readme.txt -> {r.status_code}")

    # Test SQL injection vector
    r = httpx.get("http://127.0.0.1:9000/api/users?search=admin")
    print(f"GET /api/users?search=admin -> {r.status_code}")

    # Test path traversal vector
    r = httpx.get("http://127.0.0.1:9000/api/files/../../../etc/passwd")
    print(f"GET /api/files/../etc/passwd -> {r.status_code}")

    print("\nAll API tests PASSED")

finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)
    print("API stopped.")
