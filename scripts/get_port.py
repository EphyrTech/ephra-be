#!/usr/bin/env python3
"""
Script to get the port from the .port file or find a new one if it doesn't exist.
"""

import os
import sys
import subprocess

def get_port():
    """Get the port from the .port file or find a new one."""
    port_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.port')
    
    if os.path.exists(port_file):
        with open(port_file, 'r') as f:
            return f.read().strip()
    else:
        # Find a port using the find_port.py script
        find_port_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'find_port.py')
        result = subprocess.run(['python', find_port_script], capture_output=True, text=True)
        return result.stdout.strip()

if __name__ == "__main__":
    print(get_port())
