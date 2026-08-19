import urllib.request

boundary = '----Boundary123'
body = (
    f'--{boundary}\r\n'
    'Content-Disposition: form-data; name="file"; filename="test_proof.jpg"\r\n'
    'Content-Type: image/jpeg\r\n\r\n'
    'SIH 2026 Test Image Binary Content'
    f'\r\n--{boundary}--\r\n'
).encode('utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/payments/upload-direct',
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)

try:
    with urllib.request.urlopen(req) as res:
        print("RESULT:", res.read().decode('utf-8'))
except Exception as e:
    print("ERROR:", e)
