from fastapi import APIRouter, Response
import json
import psutil
import time
from datetime import datetime

router = APIRouter()

@router.get("/metrics")
async def get_metrics():
    """
    Endpoint to expose system metrics.
    
    Returns basic system metrics like CPU, memory, and disk usage.
    In a production environment, this would be replaced with
    Prometheus metrics or a similar monitoring solution.
    
    Returns:
        dict: System metrics
    """
    # Get CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Get memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    
    # Get disk usage
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    
    # Get process info
    process = psutil.Process()
    process_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Get uptime
    uptime = time.time() - process.create_time()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
        },
        "process": {
            "memory_mb": round(process_memory, 2),
            "uptime_seconds": round(uptime, 2),
        }
    }

@router.get("/metrics/prometheus", response_class=Response)
async def prometheus_metrics():
    """
    Endpoint to expose metrics in Prometheus format.
    
    This is a simplified example. In a real application, you would use
    the prometheus_client library to generate proper Prometheus metrics.
    
    Returns:
        Response: Metrics in Prometheus text format
    """
    # Get CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Get memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    
    # Get disk usage
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    
    # Get process info
    process = psutil.Process()
    process_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Format metrics in Prometheus text format
    metrics = [
        "# HELP cpu_percent CPU usage percent",
        "# TYPE cpu_percent gauge",
        f"cpu_percent {cpu_percent}",
        "# HELP memory_percent Memory usage percent",
        "# TYPE memory_percent gauge",
        f"memory_percent {memory_percent}",
        "# HELP disk_percent Disk usage percent",
        "# TYPE disk_percent gauge",
        f"disk_percent {disk_percent}",
        "# HELP process_memory_mb Process memory usage in MB",
        "# TYPE process_memory_mb gauge",
        f"process_memory_mb {round(process_memory, 2)}",
    ]
    
    return Response(
        content="\n".join(metrics),
        media_type="text/plain"
    )
