#!/bin/bash
set -e

echo "==============================================="
echo "  Stock Analyst App Local Kubernetes Deployer   "
echo "==============================================="

# Load .env variables
if [ ! -f .env ]; then
    echo "Error: .env file not found."
    exit 1
fi

echo "[1/5] Loading environment variables from .env..."
# Read .env file lines, skip comments/empty, export
while IFS= read -r line || [[ -n "$line" ]]; do
    # Strip carriage returns and leading/trailing whitespace
    line=$(echo "$line" | tr -d '\r' | xargs)
    if [[ ! -z "$line" && ! "$line" =~ ^# ]]; then
        key=$(echo "$line" | cut -d'=' -f1 | xargs)
        val=$(echo "$line" | cut -d'=' -f2- | xargs)
        # Strip outer single or double quotes
        val="${val%\"}"
        val="${val#\"}"
        val="${val%\'}"
        val="${val#\'}"
        export "$key"="$val"
    fi
done < .env

if [ -z "$SNOWFLAKE_USER" ] || [ -z "$SNOWFLAKE_PASSWORD" ] || [ -z "$SNOWFLAKE_ACCOUNT" ]; then
    echo "Error: Missing Snowflake credentials in .env"
    exit 1
fi

echo "[2/5] Base64 encoding Snowflake credentials..."
# Convert values to base64, stripping extra newlines or spaces
USER_B64=$(echo -n "$SNOWFLAKE_USER" | base64)
PASS_B64=$(echo -n "$SNOWFLAKE_PASSWORD" | base64)
ACCT_B64=$(echo -n "$SNOWFLAKE_ACCOUNT" | base64)

echo "[3/5] Generating k8s/secrets_generated.yaml..."
sed -e "s|YOUR_BASE64_USER|$USER_B64|g" \
    -e "s|YOUR_BASE64_PASSWORD|$PASS_B64|g" \
    -e "s|YOUR_BASE64_ACCOUNT|$ACCT_B64|g" \
    k8s/secrets.yaml > k8s/secrets_generated.yaml

echo "[4/5] Building Docker image 'stocks-analyst:latest'..."
docker build -t stocks-analyst:latest .

echo "[5/5] Deploying resources to local Kubernetes cluster..."
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets_generated.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

echo ""
echo "==============================================="
echo " Deployment Completed Successfully! "
echo "==============================================="
echo "To monitor deployment, run:"
echo "  kubectl get pods -l app=stocks-analyst"
echo "  kubectl logs -f deployment/stocks-analyst-deployment"
echo ""
echo "Access the application in your browser at:"
echo "  http://localhost:30501"
echo "==============================================="
