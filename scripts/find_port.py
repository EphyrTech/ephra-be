#!/usr/bin/env python3
"""
Script to find an available port starting from a preferred port.
If the preferred port is available, it will be used.
Otherwise, it will increment and check until it finds an available port.
"""

import socket
import sys
import os

def is_port_available(port):
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

def find_available_port(start_port=8000, max_attempts=100):
    """Find an available port starting from start_port."""
    port = start_port
    for _ in range(max_attempts):
        if is_port_available(port):
            return port
        port += 1
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

if __name__ == "__main__":
    # Get preferred port from command line or use default
    preferred_port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    
    # Find an available port
    port = find_available_port(preferred_port)
    
    # Print the port (this will be captured by the calling script)
    print(port)
    
    # Also save to a file for other scripts to use
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.port'), 'w') as f:
        f.write(str(port))
