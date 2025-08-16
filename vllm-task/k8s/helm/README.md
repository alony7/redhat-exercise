# vLLM with Streamlit Metrics Dashboard

A Kubernetes Helm chart that deploys vLLM (Vector Language Model) with a real-time Streamlit metrics dashboard for monitoring model performance and throughput.

## 🚀 Features

- **vLLM Server**: High-performance inference server for large language models
- **Real-time Dashboard**: Streamlit-based metrics visualization with auto-refresh
- **Prometheus Metrics**: Built-in metrics endpoint for monitoring
- **CPU Optimized**: Configured for CPU inference with customizable parameters
- **Path-based Routing**: Single ingress endpoint with organized path routing

## 📋 Prerequisites

- Kubernetes cluster (v1.19+)
- Helm 3.x
- NGINX Ingress Controller
- kubectl configured to access your cluster

## 🛠️ Installation

### Step 1: Create Kind Cluster (For Local Development)

If using Kind for local development, create a cluster with port forwarding enabled:

```yaml
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    image: kindest/node:v1.30.0
    extraPortMappings:
      - containerPort: 80 
        hostPort: 8000    
        protocol: TCP
```

Create the cluster:

```bash
# Create Kind cluster with port forwarding
kind create cluster --config kind-config.yaml --name vllm-demo

# Verify cluster is running
kubectl cluster-info --context kind-vllm-demo
```

> **Important**: The `hostPort: 8000` mapping is required to access the services from your localhost. Without this, you won't be able to reach the dashboard or API endpoints.

### Step 2: Install NGINX Ingress Controller

Install NGINX Ingress Controller for your environment:

```bash
# For Kind/local development
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for the controller to be ready
kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller

# Verify the installation
kubectl -n ingress-nginx get svc
```

For other environments (cloud providers), refer to the [NGINX Ingress documentation](https://kubernetes.github.io/ingress-nginx/deploy/).

### Step 3: Deploy vLLM with Dashboard

```bash
# Create a namespace for the deployment
kubectl create namespace vllm-demo

# Install the Helm chart
helm install vllm-demo . -n vllm-demo

# Check deployment status
kubectl -n vllm-demo get pods
kubectl -n vllm-demo get ingress
```

## 🌐 Accessing the Services

Once deployed, the services are available at:

| Service | URL | Description |
|---------|-----|-------------|
| **Streamlit Dashboard** | http://dashboard.localhost:8000/ | Real-time metrics visualization |
| **vLLM API** | http://localhost:8000/ | OpenAI-compatible API endpoint |
| **Models Endpoint** | http://localhost:8000/v1/models | List available models |
| **Health Check** | http://localhost:8000/health | Service health status |
| **Metrics** | http://localhost:8000/metrics | Prometheus metrics endpoint |

> **Note for Kind Users**: The port 8000 is mapped from your Kind cluster to localhost via the `extraPortMappings` configuration. If you used a different `hostPort`, adjust the URLs accordingly.

> **Note**: Make sure to include the trailing slash when accessing the dashboard: `/dashboard/`

## ⚙️ Configuration

### Customize Deployment Values

Create a `values.yaml` file to override default settings:

```yaml
vllm:
  model:
    name: "HuggingFaceTB/SmolLM2-360M-Instruct"
  dtype: float32
  replicas: 1
  resources:
      requests:
        memory: "4Gi"
        cpu: "2"
      limits:
        memory: "8Gi"
        cpu: "4"
```

Deploy with custom values:

```bash
helm upgrade --install vllm-demo . -n vllm-demo -f values.yaml
```

### Supported Models

The chart supports any model compatible with vLLM. Popular options include:
- `facebook/opt-125m` (default, lightweight)
- `facebook/opt-350m`
- `facebook/opt-1.3b`
- `meta-llama/Llama-2-7b-hf` (requires GPU)
- `mistralai/Mistral-7B-v0.1` (requires GPU)

## 🔍 Monitoring

### Dashboard Metrics

The Streamlit dashboard displays:
- **Prompt Throughput**: Tokens processed per second for prompts
- **Generation Throughput**: Tokens generated per second
- **Running Requests**: Current active requests
- **Pending Requests**: Queued requests waiting for processing

### Prometheus Integration

The service exposes Prometheus metrics at `/metrics`. To scrape with Prometheus:

```yaml
scrape_configs:
  - job_name: 'vllm'
    static_configs:
      - targets: ['vllm.vllm-demo.svc.cluster.local:8000']
```

## 🧪 Testing the API

Test the vLLM API with curl:

```bash
# List available models
curl http://localhost:8000/v1/models

# Generate completion
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "facebook/opt-125m",
    "prompt": "Hello, world!",
    "max_tokens": 50,
    "temperature": 0.7
  }'

# Chat completion (if model supports it)
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "facebook/opt-125m",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }'
```

## 🔧 Troubleshooting

### Common Issues

1. **Cannot access services from localhost**
   - **For Kind users**: Ensure your `kind-config.yaml` includes the `extraPortMappings` configuration
   - **For other environments**: Use `kubectl port-forward` or configure LoadBalancer/NodePort services
   - Check if NGINX ingress controller is running: `kubectl -n ingress-nginx get pods`

2. **Dashboard shows 404 errors for static assets**
   - Ensure you're accessing with the correct hostname: `http://dashboard.localhost:8000/`
   - Check ingress controller logs: `kubectl -n ingress-nginx logs deploy/ingress-nginx-controller`

3. **vLLM pod crashes or restarts**
   - Check resource limits: `kubectl -n vllm-demo describe pod -l component=vllm`
   - View logs: `kubectl -n vllm-demo logs -l component=vllm`
   - Increase memory limits if needed

4. **Slow response times**
   - CPU inference is slower than GPU
   - Consider using smaller models or adding GPU support
   - Scale replicas: `kubectl -n vllm-demo scale deploy/vllm-demo-vllm --replicas=2`

5. **Ingress not working**
   - Verify ingress controller is running: `kubectl -n ingress-nginx get pods`
   - Check ingress resource: `kubectl -n vllm-demo describe ingress`
   - For Kind: Ensure port mapping is configured correctly in cluster config

### Alternative Access Methods

If ingress is not working, you can access services directly:

```bash
# Port forward vLLM service
kubectl -n vllm-demo port-forward svc/vllm-demo-vllm 8000:8000

# Port forward Streamlit dashboard
kubectl -n vllm-demo port-forward svc/vllm-demo-streamlit 8501:8501
```

### View Logs

```bash
# vLLM logs
kubectl -n vllm-demo logs -f -l component=vllm

# Streamlit logs
kubectl -n vllm-demo logs -f -l component=streamlit

# Ingress controller logs
kubectl -n ingress-nginx logs -f deploy/ingress-nginx-controller
```

## 🗑️ Uninstallation

```bash
# Remove the Helm release
helm uninstall vllm-demo -n vllm-demo

# Delete the namespace
kubectl delete namespace vllm-demo

# Delete Kind cluster (if using Kind)
kind delete cluster --name vllm-demo
```

## 📁 Project Structure

```
.
├── Chart.yaml              # Helm chart metadata
├── values.yaml             # Default configuration values
├── kind-config.yaml        # Kind cluster configuration (for local dev)
├── templates/
│   ├── ingress.yaml        # Ingress routing configuration
│   ├── vllm-deployment.yaml    # vLLM server deployment
│   ├── vllm-service.yaml       # vLLM service
│   ├── streamlit-deployment.yaml   # Dashboard deployment
│   ├── streamlit-service.yaml      # Dashboard service
│   ├── streamlit-configmap.yaml    # Dashboard application code
│   └── _helpers.tpl        # Helm template helpers
└── files/
    └── app.py             # Streamlit dashboard application
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Links

- [vLLM Documentation](https://docs.vllm.ai/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [Helm Documentation](https://helm.sh/docs/)
- [Kind Documentation](https://kind.sigs.k8s.io/)