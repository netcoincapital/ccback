#!/usr/bin/env python3
"""Cleanly add /uploads/ location to Nginx config."""
import re

path = "/etc/nginx/sites-available/coinceeper"

with open(path) as f:
    content = f.read()

# Remove any existing /uploads/ location blocks (single-line or multi-line)
content = re.sub(
    r'\n\s+location \^\~ /uploads/ \{[^}]*?\}\n',
    '\n',
    content,
    flags=re.DOTALL
)

# Insert one clean block after each /CC/cryptoicons/ location
# in the two SSL server blocks
uploads_block = '''
    location ^~ /uploads/ {
        alias /opt/coinceeper/CC/uploads/;
        access_log off;
        expires 1d;
        add_header Cache-Control "public, max-age=86400";
        try_files $uri =404;
    }
'''

# Find the end of each cryptoicons block and insert after it
crypto_end = 'try_files $uri =404;\n    }'
content = content.replace(crypto_end, crypto_end + uploads_block, 2)

with open(path, 'w') as f:
    f.write(content)

print("Nginx config cleaned up")
