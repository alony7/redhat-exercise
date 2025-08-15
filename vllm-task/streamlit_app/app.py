import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
import re
from collections import defaultdict
import os
from typing import Dict, Tuple

# Page config
st.set_page_config(
    page_title="vLLM Metrics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .stMetric > div {
        background-color: white;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

class PrometheusMetricsParser:
    """Parse Prometheus metrics from vLLM /metrics endpoint"""
    
    def __init__(self, metrics_text: str):
        self.metrics_text = metrics_text
        self.metrics = defaultdict(dict)
        self.parse()
    
    def parse(self):
        """Parse Prometheus format metrics"""
        lines = self.metrics_text.split('\n')
        
        for line in lines:
            if line.startswith('#') or not line.strip():
                continue
            
            # Parse metric line with labels
            match = re.match(r'([a-zA-Z_:][a-zA-Z0-9_:]*){([^}]*)}?\s+([0-9.eE+-]+)', line)
            if match:
                metric_name = match.group(1)
                labels_str = match.group(2) if match.group(2) else ""
                value = float(match.group(3))
                
                # Parse labels
                labels = {}
                if labels_str:
                    label_pairs = re.findall(r'([^=]+)="([^"]*)"', labels_str)
                    labels = dict(label_pairs)
                
                # Store metric with labels as key
                label_key = str(labels) if labels else "no_labels"
                if metric_name not in self.metrics:
                    self.metrics[metric_name] = {}
                self.metrics[metric_name][label_key] = {
                    'value': value,
                    'labels': labels
                }
            else:
                # Try simple metric without labels
                match = re.match(r'([a-zA-Z_:][a-zA-Z0-9_:]*)\s+([0-9.eE+-]+)', line)
                if match:
                    metric_name = match.group(1)
                    value = float(match.group(2))
                    self.metrics[metric_name]["no_labels"] = {
                        'value': value,
                        'labels': {}
                    }
    
    def get_metric(self, name: str, labels: Dict = None) -> float:
        """Get specific metric value"""
        if name not in self.metrics:
            return None
        
        if labels:
            for key, data in self.metrics[name].items():
                if all(data['labels'].get(k) == v for k, v in labels.items()):
                    return data['value']
        else:
            if "no_labels" in self.metrics[name]:
                return self.metrics[name]["no_labels"]['value']
        
        # Return first value if no specific match
        if self.metrics[name]:
            return list(self.metrics[name].values())[0]['value']
        return None
    
    def get_histogram_percentiles(self, base_name: str) -> Dict[str, float]:
        """Extract percentiles from histogram metrics"""
        percentiles = {}
        
        # Check for direct quantile metrics
        for metric_name in self.metrics:
            if base_name in metric_name:
                for key, data in self.metrics[metric_name].items():
                    if 'quantile' in data['labels']:
                        q = float(data['labels']['quantile'])
                        percentiles[f"p{int(q*100)}"] = data['value']
        
        # If no quantiles, calculate from buckets
        if not percentiles and f"{base_name}_bucket" in self.metrics:
            buckets = []
            total_count = 0
            
            for key, data in self.metrics[f"{base_name}_bucket"].items():
                if 'le' in data['labels']:
                    le = data['labels']['le']
                    count = data['value']
                    if le == '+Inf':
                        total_count = count
                    else:
                        buckets.append((float(le), count))
            
            if buckets and total_count > 0:
                buckets.sort()
                
                # Calculate percentiles
                for p in [50, 95, 99]:
                    target = total_count * (p / 100)
                    for le, cumulative_count in buckets:
                        if cumulative_count >= target:
                            percentiles[f"p{p}"] = le
                            break
                    if f"p{p}" not in percentiles and buckets:
                        percentiles[f"p{p}"] = buckets[-1][0]
        
        return percentiles

def fetch_metrics(endpoint: str) -> Tuple[bool, Dict]:
    """Fetch and parse metrics from vLLM endpoint"""
    try:
        response = requests.get(endpoint, timeout=5)
        response.raise_for_status()
        
        parser = PrometheusMetricsParser(response.text)
        
        metrics = {
            'latency': {
                'ttft': {},
                'e2e': {}
            },
            'throughput': {
                'requests_per_sec': 0,
                'tokens_per_sec': 0
            },
            'queue': {
                'time': 0,
                'size': 0
            },
            'cache': {
                'hit_rate': 0,
                'usage': 0
            },
            'raw_text': response.text[:1000]  # Store first 1000 chars for debugging
        }
        
        # TTFT metrics - vLLM specific metric names
        ttft_names = [
            'vllm:time_to_first_token_seconds',
            'vllm:ttft_seconds',
            'vllm_request_time_to_first_token_seconds'
        ]
        
        for name in ttft_names:
            percentiles = parser.get_histogram_percentiles(name)
            if percentiles:
                metrics['latency']['ttft'] = percentiles
                break
        
        # E2E latency metrics
        e2e_names = [
            'vllm:e2e_request_latency_seconds',
            'vllm:request_latency_seconds',
            'vllm_request_latency_seconds',
            'vllm_e2e_latency_seconds'
        ]
        
        for name in e2e_names:
            percentiles = parser.get_histogram_percentiles(name)
            if percentiles:
                metrics['latency']['e2e'] = percentiles
                break
        
        # Throughput - check various possible metric names
        req_throughput_names = [
            'vllm:request_throughput',
            'vllm_request_throughput',
            'vllm:avg_request_throughput',
            'vllm_num_requests_total'  # Can calculate rate from total
        ]
        
        for name in req_throughput_names:
            val = parser.get_metric(name)
            if val is not None:
                metrics['throughput']['requests_per_sec'] = val
                break
        
        token_throughput_names = [
            'vllm:avg_generation_throughput_toks_per_s',
            'vllm:avg_prompt_throughput_toks_per_s',
            'vllm_avg_generation_throughput_toks_per_s',
            'vllm_generation_tokens_total'  # Can calculate rate from total
        ]
        
        for name in token_throughput_names:
            val = parser.get_metric(name)
            if val is not None:
                metrics['throughput']['tokens_per_sec'] = val
                break
        
        # Queue metrics
        queue_time_names = [
            'vllm:time_in_queue_seconds',
            'vllm_time_in_queue_seconds',
            'vllm:queue_time'
        ]
        
        for name in queue_time_names:
            val = parser.get_metric(name)
            if val is not None:
                metrics['queue']['time'] = val
                break
        
        queue_size_names = [
            'vllm:num_requests_waiting',
            'vllm_num_requests_waiting',
            'vllm:pending_requests',
            'vllm_pending_requests'
        ]
        
        for name in queue_size_names:
            val = parser.get_metric(name)
            if val is not None:
                metrics['queue']['size'] = val
                break
        
        # Cache metrics
        cache_hit = parser.get_metric('vllm:cache_hit_rate') or \
                   parser.get_metric('vllm_cache_hit_rate') or \
                   parser.get_metric('vllm:kv_cache_hit_rate') or 0
        
        cache_usage = parser.get_metric('vllm:gpu_cache_usage_perc') or \
                     parser.get_metric('vllm_gpu_cache_usage_perc') or \
                     parser.get_metric('vllm:cache_usage') or 0
        
        metrics['cache']['hit_rate'] = cache_hit
        metrics['cache']['usage'] = cache_usage
        
        # Additional metrics
        metrics['additional'] = {
            'running': parser.get_metric('vllm:num_requests_running') or 
                      parser.get_metric('vllm_num_requests_running') or 0,
            'swapped': parser.get_metric('vllm:num_requests_swapped') or 
                      parser.get_metric('vllm_num_requests_swapped') or 0,
            'finished': parser.get_metric('vllm:num_requests_finished') or 
                       parser.get_metric('vllm_num_requests_finished') or 0
        }
        
        return True, metrics
        
    except requests.RequestException as e:
        return False, {'error': str(e)}
    except Exception as e:
        return False, {'error': f"Parsing error: {str(e)}"}

def main():
    """Main Streamlit application"""
    
    # Get configuration from environment
    endpoint = os.getenv("VLLM_METRICS_URL", "http://vllm:8000/metrics")
    refresh_ms = int(os.getenv("REFRESH_MS", "5000"))
    refresh_sec = refresh_ms / 1000
    
    # Title and header
    st.title("🚀 vLLM Metrics Dashboard")
    
    # Connection info bar
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        st.info(f"📡 Endpoint: `{endpoint.split('://')[1] if '://' in endpoint else endpoint}`")
    with col2:
        placeholder = st.empty()
    with col3:
        st.info(f"🔄 Refresh: {refresh_sec}s")
    with col4:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    st.markdown("---")
    
    # Fetch metrics
    success, metrics = fetch_metrics(endpoint)
    
    if success:
        # Update status
        with placeholder:
            st.success(f"✅ Connected • {datetime.now().strftime('%H:%M:%S')}")
        
        # LATENCY SECTION
        st.header("📊 Latency Metrics")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("⏱️ Time to First Token (TTFT)")
            if metrics['latency']['ttft']:
                c1, c2, c3 = st.columns(3)
                with c1:
                    val = metrics['latency']['ttft'].get('p50', 0)
                    st.metric("P50", f"{val:.3f}s" if val else "N/A")
                with c2:
                    val = metrics['latency']['ttft'].get('p95', 0)
                    st.metric("P95", f"{val:.3f}s" if val else "N/A")
                with c3:
                    val = metrics['latency']['ttft'].get('p99', 0)
                    st.metric("P99", f"{val:.3f}s" if val else "N/A")
            else:
                st.info("⚠️ TTFT metrics not available")
        
        with col2:
            st.subheader("🔚 End-to-End Latency")
            if metrics['latency']['e2e']:
                c1, c2, c3 = st.columns(3)
                with c1:
                    val = metrics['latency']['e2e'].get('p50', 0)
                    st.metric("P50", f"{val:.3f}s" if val else "N/A")
                with c2:
                    val = metrics['latency']['e2e'].get('p95', 0)
                    st.metric("P95", f"{val:.3f}s" if val else "N/A")
                with c3:
                    val = metrics['latency']['e2e'].get('p99', 0)
                    st.metric("P99", f"{val:.3f}s" if val else "N/A")
            else:
                st.info("⚠️ E2E metrics not available")
        
        # THROUGHPUT SECTION
        st.header("🚄 Throughput Metrics")
        col1, col2 = st.columns(2)
        
        with col1:
            val = metrics['throughput']['requests_per_sec']
            st.metric(
                "Requests per Second",
                f"{val:.2f}" if val else "0",
                help="Number of requests processed per second"
            )
        
        with col2:
            val = metrics['throughput']['tokens_per_sec']
            st.metric(
                "Tokens per Second",
                f"{val:.2f}" if val else "0",
                help="Number of tokens generated per second"
            )
        
        # QUEUE & CACHE SECTION
        st.header("📈 Queue & Cache Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            val = metrics['queue']['time']
            st.metric(
                "Queue Time",
                f"{val:.3f}s" if val else "0s",
                help="Average time requests spend in queue"
            )
        
        with col2:
            val = metrics['queue']['size']
            st.metric(
                "Queue Size",
                f"{int(val)}" if val else "0",
                help="Number of requests currently in queue"
            )
        
        with col3:
            val = metrics['cache']['hit_rate']
            if val and val > 0:
                display_val = f"{val*100:.1f}%" if val <= 1 else f"{val:.1f}%"
            else:
                display_val = "N/A"
            st.metric(
                "Cache Hit Rate",
                display_val,
                help="Percentage of cache hits"
            )
        
        with col4:
            val = metrics['cache']['usage']
            if val and val > 0:
                display_val = f"{val:.1f}%"
            else:
                display_val = "N/A"
            st.metric(
                "Cache Usage",
                display_val,
                help="Percentage of cache being used"
            )
        
        # ADDITIONAL METRICS
        if any(metrics.get('additional', {}).values()):
            st.header("🔍 Request Status")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                val = metrics['additional'].get('running', 0)
                st.metric("🏃 Running", int(val))
            with col2:
                val = metrics['additional'].get('swapped', 0)
                st.metric("💾 Swapped", int(val))
            with col3:
                val = metrics['additional'].get('finished', 0)
                st.metric("✅ Finished", int(val))
        
        # Debug section (collapsible)
        with st.expander("🔧 Debug Info"):
            st.text("Raw metrics sample (first 1000 chars):")
            if 'raw_text' in metrics:
                st.code(metrics['raw_text'], language='text')
        
        # Auto-refresh
        time.sleep(refresh_sec)
        st.rerun()
        
    else:
        # Error state
        with placeholder:
            st.error("❌ Disconnected")
        
        st.error(f"Failed to fetch metrics: {metrics.get('error', 'Unknown error')}")
        st.warning("Please ensure:")
        st.markdown("""
        1. vLLM is running and accessible
        2. The metrics endpoint is correct: `{}`
        3. vLLM was started with `--enable-metrics` flag
        """.format(endpoint))
        
        # Show error details
        with st.expander("Error Details"):
            st.json(metrics)
        
        # Retry
        if st.button("🔄 Retry Connection"):
            st.rerun()
        
        # Wait before retry
        time.sleep(5)
        st.rerun()

if __name__ == "__main__":
    main()