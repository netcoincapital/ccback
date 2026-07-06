#!/usr/bin/env python3
"""Fix Nginx config: add /uploads/ location if missing, remove duplicates."""
config_path = "/etc/nginx/sites-available/coinceeper"

with open(config_path, "r") as f:
    content = f.read()

# Remove any existing /uploads/ location blocks
import re
content = re.sub(
    r'\n\s*location \^\~ /uploads/ \{[^}]+\}\n',
    '\n',
    content
)

# Now add clean uploads block to both server blocks
uploads_block = """
    location ^~ /uploads/ {
        alias /opt/coinceeper/CC/uploads/;
        access_log off;
        expires 1d;
        add_header Cache-Control "public, max-age=86400";
        try_files $uri =404;
    }
"""

# Find the pattern: after "try_files $uri =404;\n    }\n\n    location / {"
# in each server block
count = 0
result = []
for part in content.split("    location / {"):
    if count == 0:
        result.append(part)
        count += 1
    else:
        # This part starts with the "location / {" and rest of the server block
        # Insert uploads block before this location
        if count <= 2:  # Only for first 2 server blocks
            result.append(uploads_block + "\n    location / {")
        else:
            result.append("    location / {")
        result.append(part)
        count += 1

content = "".join(result)

with open(config_path, "w") as f:
    f.write(content)

print("Nginx config updated")
