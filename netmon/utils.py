"""Utility functions for netmon."""

import ipaddress
import os
import re
import socket
import subprocess
from datetime import datetime, timezone
from typing import Optional


def format_bytes(bytes_val: float) -> str:
    """Format bytes to human readable string.
    
    Args:
        bytes_val: Number of bytes
        
    Returns:
        Formatted string like "1.23 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


def is_valid_ip(ip_string: str) -> bool:
    """Check if string is a valid IP address.
    
    Args:
        ip_string: String to validate
        
    Returns:
        True if valid IP address
    """
    try:
        ipaddress.ip_address(ip_string)
        return True
    except ValueError:
        return False


def get_hostname() -> str:
    """Get system hostname.
    
    Returns:
        System hostname or 'unknown'
    """
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_timestamp_utc() -> str:
    """Get current UTC timestamp in ISO format.
    
    Returns:
        ISO formatted timestamp
    """
    return datetime.now(timezone.utc).isoformat()


def get_timestamp_local() -> str:
    """Get current local timestamp.
    
    Returns:
        Formatted timestamp string
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_all_interfaces() -> list[str]:
    """Detect all active network interfaces to monitor.
    
    Returns:
        List of interface names
    """
    interfaces = []
    
    # Exclude patterns
    EXCLUDE_PATTERNS = ('lo', 'veth', 'virbr')
    
    # Include patterns
    INCLUDE_PATTERNS = (
        'eth', 'enp', 'ens', 'eno',  # Ethernet
        'wlan', 'wlp',                # WiFi
        'docker0',                    # Docker main bridge
        'br-',                        # Docker custom network bridges
        'tailscale',                  # Tailscale VPN
    )
    
    try:
        env = {**os.environ, 'LANG': 'C'}
        result = subprocess.run(
            ['ip', '-o', 'link', 'show', 'up'],
            capture_output=True, text=True, timeout=5,
            env=env
        )
        
        for line in result.stdout.splitlines():
            match = re.search(r'^\d+:\s+(\S+?)[@:]', line)
            if match:
                iface = match.group(1)
                
                # Skip excluded
                if any(iface.startswith(p) for p in EXCLUDE_PATTERNS):
                    continue
                
                # Include matching
                if any(iface.startswith(p) for p in INCLUDE_PATTERNS):
                    interfaces.append(iface)
                    
    except Exception:
        pass
    
    if not interfaces:
        interfaces = ['eth0']
        
    return list(set(interfaces))


def get_default_interface() -> Optional[str]:
    """Detect default internet interface.
    
    Returns:
        Interface name or None
    """
    try:
        env = {**os.environ, 'LANG': 'C'}
        result = subprocess.run(
            ['ip', 'route', 'get', '8.8.8.8'],
            capture_output=True, text=True, timeout=5,
            env=env
        )
        if result.returncode == 0:
            match = re.search(r'dev\s+(\S+)', result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None
