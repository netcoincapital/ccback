"""Verify Tron broadcast deployment by checking health endpoint."""
import json
import urllib.request

try:
    resp = urllib.request.urlopen(
        'http://127.0.0.1:5000/api/v2/proxy-health',
        timeout=5
    )
    data = json.loads(resp.read())
    providers = data.get('providers', {})
    
    print('=== Tron Broadcast Provider ===')
    tron_broadcast = providers.get('tron_broadcast', {})
    print(json.dumps(tron_broadcast, indent=2))
    
    print()
    print('=== TronGrid Provider ===')
    trongrid = providers.get('trongrid', {})
    print(json.dumps(trongrid, indent=2))
    
    if tron_broadcast.get('status') == 'active':
        print()
        print('SUCCESS: Tron broadcast provider is active')
    else:
        print()
        print('WARNING: Tron broadcast provider status:', tron_broadcast.get('status'))
        
except Exception as e:
    print(f'ERROR: {e}')
