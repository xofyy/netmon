"""nethogs output parser for netmon."""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def parse_nethogs_line(line: str) -> Tuple[Optional[str], Optional[str], float, float]:
    """Parse a single line of nethogs trace output.
    
    Example formats:
    - /usr/bin/firefox/12345/192.168.1.5:443-10.0.0.1:54321	1.234	5.678
    - /usr/bin/python3/1234	0.5	1.2
    - firefox/12345	0.5	1.2
    - unknown TCP/0/0	0	0
    
    Args:
        line: Raw nethogs output line
        
    Returns:
        Tuple of (app_name, remote_ip, bytes_sent, bytes_recv)
        Returns (None, None, 0, 0) for invalid/skipped lines
    """
    line = line.strip()
    
    # Skip empty lines and refresh messages
    if not line or line.startswith('Refreshing'):
        return None, None, 0, 0
    
    parts = line.split('\t')
    if len(parts) < 3:
        return None, None, 0, 0
    
    try:
        prog_info = parts[0]
        sent = float(parts[1]) * 1024  # KB -> Bytes
        recv = float(parts[2]) * 1024
        
        # Extract app name and remote IP
        app_name = extract_app_name(prog_info)
        remote_ip = extract_remote_ip(prog_info)
        
        # Validate app name
        app_name = validate_app_name(app_name)
        
        return app_name, remote_ip, sent, recv
        
    except (ValueError, IndexError) as e:
        logger.debug(f"Parse error: {line} - {e}")
        return None, None, 0, 0


def extract_app_name(prog_info: str) -> Optional[str]:
    """Extract application name from nethogs program info.
    
    Args:
        prog_info: Program info string like /usr/bin/firefox/12345/...
        
    Returns:
        Application name or None
    """
    app_name = None
    
    if '/' in prog_info:
        path_parts = prog_info.split('/')
        
        # Find PID (first numeric part) and get the part before it
        for i, part in enumerate(path_parts):
            if part.isdigit():
                if i > 0:
                    app_name = path_parts[i-1]
                break
        
        # Fallback: find last non-numeric, non-IP part
        if not app_name:
            for part in reversed(path_parts):
                if part and not part.isdigit() and ':' not in part and '-' not in part:
                    app_name = part
                    break
    else:
        # Simple format: binary/PID or binary-PID
        app_name = prog_info.split('/')[0].split('-')[0]
    
    return app_name


def extract_remote_ip(prog_info: str) -> Optional[str]:
    """Extract remote IP address from nethogs program info.
    
    Format: local_ip:port-remote_ip:port
    
    Args:
        prog_info: Program info string
        
    Returns:
        Remote IP address or None
    """
    # Full connection pattern: local_ip:port-remote_ip:port
    ip_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):\d+-(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):\d+'
    match = re.search(ip_pattern, prog_info)
    
    if match:
        return match.group(2)  # Remote IP (second group)
    
    # Single IP pattern
    single_ip = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', prog_info)
    if single_ip:
        return single_ip.group(1)
    
    return None


def validate_app_name(app_name: Optional[str]) -> str:
    """Validate and clean application name.
    
    Returns 'unknown' for invalid names.
    
    Args:
        app_name: Raw application name
        
    Returns:
        Validated application name
    """
    if not app_name:
        return 'unknown'
    
    app_name = app_name.strip()
    
    # Invalid patterns
    is_invalid = (
        app_name.isdigit() or  # PID
        re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', app_name) or  # IP address
        re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+-', app_name) or  # IP:port-...
        app_name in ('unknown', 'TCP', 'UDP', '')
    )
    
    if is_invalid:
        return 'unknown'
    
    return app_name
