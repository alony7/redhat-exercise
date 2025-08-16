# API Probe 🔍

A lightweight command-line tool for measuring API endpoint latency with controlled request rates. Perfect for performance testing, SLA verification, and API health monitoring.

## Features

- **Simple & Focused**: Send non-streaming HTTP requests at precisely 1 RPS
- **Accurate Measurements**: Track end-to-end latency in milliseconds
- **Real-time Feedback**: See results as requests complete
- **CSV Export**: Save detailed metrics for further analysis
- **Error Handling**: Gracefully handles timeouts, SSL issues, and connection errors
- **Performance Monitoring**: Tracks target vs actual RPS with warnings for slow endpoints

## Installation

```bash
# Install dependencies
pip install requests
```

## Quick Start

```bash
# Basic usage - test a local endpoint
python probe-script.py \
  --api-url http://localhost:8000/v1/chat/completions \
  --prompt "Hello world" \
  --requests 5

# With authentication token
python probe-script.py \
  --api-url https://api.example.com/v1/chat/completions \
  --api-token your-api-key-here \
  --prompt "Test prompt" \
  --requests 10
```

## Command-Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--api-url` | Yes | - | Full endpoint URL (e.g., `http://localhost:8000/v1/chat/completions`) |
| `--api-token` | No | None | Authentication token/key (optional) |
| `--prompt` | Yes | - | A single text prompt to send in the request body |
| `--requests` | Yes | - | Number of requests to send |
| `--rps` | No | 1 | Requests per second (default: 1). In the core version, this must always be 1. Higher values are bonus only. |

## Output

### Console Output
Real-time results displayed as requests complete:
```
API Probe Starting
================
API URL: http://localhost:8000/v1/chat/completions
Requests to send: 5
RPS: 1.0
Prompt: Hello world

Request 1: 850 ms, status 200
Request 2: 920 ms, status 200
Request 3: 1250 ms, status 200
Request 4: 780 ms, status 200
Request 5: 890 ms, status 200

Summary Statistics
==================
Successful requests: 5/5
Average latency: 938 ms
Min latency: 780 ms
Max latency: 1250 ms
Target RPS: 1.0
Actual RPS: 0.98
```

### CSV Export (`metrics.csv`)
Detailed metrics saved automatically:
```csv
request_number,start_time,total_time_ms,status
1,2024-03-15 14:30:45.123,850,200
2,2024-03-15 14:30:46.125,920,200
3,2024-03-15 14:30:47.127,1250,200
4,2024-03-15 14:30:48.380,780,200
5,2024-03-15 14:30:49.382,890,200
```

## Request Format

The script sends requests in OpenAI-compatible chat completions format:
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Your prompt here"
    }
  ],
  "stream": false
}
```

To customize the request format for your API, modify the `create_request_body()` function in the script.

## Error Handling

The script handles various error scenarios gracefully:

- **Connection Errors**: Reports when the endpoint is unreachable
- **SSL Errors**: Provides hints for localhost vs production endpoints
- **Timeouts**: 30-second timeout per request with clear reporting
- **HTTP Errors**: Records status codes for all responses

Failed requests are marked with status `-1` in the CSV and excluded from latency statistics.

## Performance Considerations

### RPS Behavior
- **Target RPS = 1**: Requests are scheduled to start at 1-second intervals
- **Fast requests** (< 1s): Script waits to maintain exact 1 RPS
- **Slow requests** (> 1s): Next request starts immediately after completion
- **Mixed performance**: Script adapts dynamically and reports actual RPS achieved

### When Requests Take > 1 Second
If your API endpoint takes longer than 1 second to respond:
1. The script continues sending requests as fast as possible
2. Actual RPS will be lower than target RPS
3. A warning appears in the summary statistics
4. All timing data is still accurately recorded

## Common Use Cases

### 1. Local Development Testing
```bash
python probe-script.py \
  --api-url http://localhost:8000/api/endpoint \
  --prompt "test" \
  --requests 10
```

### 2. Production API Monitoring
```bash
python probe-script.py \
  --api-url https://api.production.com/v1/endpoint \
  --api-token $PROD_API_KEY \
  --prompt "health check" \
  --requests 100
```

### 3. Baseline Performance Testing
```bash
# Run multiple tests with different prompts
for prompt in "short" "medium length prompt here" "very long prompt..."; do
    python probe-script.py \
      --api-url $API_URL \
      --api-token $API_KEY \
      --prompt "$prompt" \
      --requests 20
    mv metrics.csv "metrics_${#prompt}_chars.csv"
done
```

## Troubleshooting

### SSL Certificate Errors
**Problem**: `SSL: WRONG_VERSION_NUMBER` or certificate verification failed

**Solutions**:
- For localhost: Use `http://` instead of `https://`
- The script automatically disables SSL verification for development convenience
- For production: Be aware that SSL verification is disabled by default

### Connection Refused
**Problem**: `Connection refused` or `Cannot reach API`

**Solutions**:
- Verify the server is running
- Check the port number is correct
- Ensure firewall rules allow the connection

### Slow Response Times
**Problem**: Requests taking longer than expected

**Solutions**:
- Check server load and resources
- Monitor network latency
- Review API endpoint optimization
- Consider implementing caching

## Output Files

| File | Description |
|------|-------------|
| `metrics.csv` | Detailed per-request metrics with timestamps |
| Console output | Real-time progress and summary statistics |

## Requirements

- Python 3.6+
- `requests` library (`pip install requests`)
- Network access to target API endpoint

## Limitations

- Core version supports only 1 RPS (no concurrency)
- Non-streaming requests only
- Single prompt per test run
- CSV file is overwritten on each run

## Future Enhancements (Bonus Features)

The script architecture supports these optional extensions:
- **Streaming Mode**: Measure Time-to-First-Token (TTFT)
- **Higher RPS**: Parallel requests with configurable concurrency
- **Prompt Variety**: Random selection from prompt file
- **Advanced Metrics**: Percentiles, jitter, throughput analysis

## License

MIT License - Feel free to modify and distribute as needed.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

For issues, questions, or suggestions, please open an issue on GitHub or contact the maintainers.