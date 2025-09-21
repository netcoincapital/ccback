#!/bin/bash

echo "🔧 Setting up Infura API Key"
echo "============================"

# Add Infura API key to environment
echo "Adding INFURA_API_KEY to .env file..."

# Check if .env exists
if [ -f .env ]; then
    # Check if INFURA_API_KEY already exists
    if grep -q "INFURA_API_KEY" .env; then
        echo "✅ INFURA_API_KEY already exists in .env"
        grep "INFURA_API_KEY" .env
    else
        echo "Adding INFURA_API_KEY to .env..."
        echo "" >> .env
        echo "# Infura API Key for reliable Ethereum broadcasting" >> .env
        echo "INFURA_API_KEY=a8ab43a04ce044de988a838d92f478a7" >> .env
        echo "✅ Added INFURA_API_KEY to .env"
    fi
else
    echo "❌ .env file not found"
    echo "Creating .env with INFURA_API_KEY..."
    echo "INFURA_API_KEY=a8ab43a04ce044de988a838d92f478a7" > .env
    echo "✅ Created .env with INFURA_API_KEY"
fi

echo ""
echo "🔄 Restarting gunicorn to apply changes..."
systemctl restart gunicorn

echo ""
echo "✅ Setup complete!"
echo "Infura will now be used for reliable transaction broadcasting."
