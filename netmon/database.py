"""SQLite database operations for netmon."""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from netmon.config import NetmonConfig, load_config
from netmon.models import AppTraffic, ExcludedIP, WebhookConfig
from netmon.utils import format_bytes

logger = logging.getLogger(__name__)


def get_connection(config: Optional[NetmonConfig] = None) -> sqlite3.Connection:
    """Get thread-safe database connection.
    
    Args:
        config: Optional config object
        
    Returns:
        SQLite connection
    """
    if config is None:
        config = load_config()
    
    # Ensure directory exists
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(
        config.db_path,
        timeout=30,
        check_same_thread=False
    )
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db(config: Optional[NetmonConfig] = None) -> None:
    """Initialize database tables.
    
    Args:
        config: Optional config object
    """
    conn = get_connection(config)
    c = conn.cursor()
    
    # Traffic table
    c.execute('''
        CREATE TABLE IF NOT EXISTS traffic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            app_name TEXT,
            remote_ip TEXT,
            bytes_sent INTEGER,
            bytes_recv INTEGER
        )
    ''')
    
    # Excluded IPs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS excluded_ips (
            ip TEXT PRIMARY KEY,
            description TEXT,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Webhook config table
    c.execute('''
        CREATE TABLE IF NOT EXISTS webhook_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            endpoint_url TEXT,
            interval_minutes INTEGER DEFAULT 60,
            enabled INTEGER DEFAULT 0,
            last_sent DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Webhook logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS webhook_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            response_code INTEGER,
            message TEXT
        )
    ''')
    
    # Indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON traffic(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_app ON traffic(app_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_remote_ip ON traffic(remote_ip)')
    
    # Default excluded IPs
    default_ips = [
        ("5.5.5.100", "PLC 1"),
        ("5.5.5.101", "PLC 2"),
        ("5.5.5.102", "PLC 3"),
        ("5.5.5.103", "PLC 4"),
    ]
    for ip, desc in default_ips:
        c.execute(
            'INSERT OR IGNORE INTO excluded_ips (ip, description) VALUES (?, ?)',
            (ip, desc)
        )
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def save_traffic(traffic_data: dict[str, dict], config: Optional[NetmonConfig] = None) -> None:
    """Save traffic data to database.
    
    Args:
        traffic_data: Dict of app -> {sent, recv, ips}
        config: Optional config object
    """
    if not traffic_data:
        return
    
    conn = get_connection(config)
    c = conn.cursor()
    
    for app, data in traffic_data.items():
        if data['sent'] > 0 or data['recv'] > 0:
            ips = list(data.get('ips', set()))

            if ips:
                # Split traffic across IPs, preserving all bytes
                num_ips = len(ips)
                base_sent = int(data['sent'] // num_ips)
                base_recv = int(data['recv'] // num_ips)

                # Calculate remainder to distribute to first N IPs
                remainder_sent = int(data['sent']) - (base_sent * num_ips)
                remainder_recv = int(data['recv']) - (base_recv * num_ips)

                for i, ip in enumerate(ips):
                    # Distribute remainder to first N IPs (where N = remainder)
                    ip_sent = base_sent + (1 if i < remainder_sent else 0)
                    ip_recv = base_recv + (1 if i < remainder_recv else 0)

                    c.execute('''
                        INSERT INTO traffic (app_name, remote_ip, bytes_sent, bytes_recv)
                        VALUES (?, ?, ?, ?)
                    ''', (app, ip, ip_sent, ip_recv))
            else:
                c.execute('''
                    INSERT INTO traffic (app_name, remote_ip, bytes_sent, bytes_recv)
                    VALUES (?, ?, ?, ?)
                ''', (app, None, int(data['sent']), int(data['recv'])))
    
    conn.commit()
    conn.close()
    logger.debug(f"Saved traffic: {len(traffic_data)} apps")


def get_traffic_report(days: float = 1, config: Optional[NetmonConfig] = None) -> list[AppTraffic]:
    """Get aggregated traffic report.
    
    Args:
        days: Number of days to query
        config: Optional config object
        
    Returns:
        List of AppTraffic objects sorted by total traffic
    """
    conn = get_connection(config)
    c = conn.cursor()
    
    since = datetime.utcnow() - timedelta(days=days)
    since_str = since.strftime('%Y-%m-%d %H:%M:%S')
    
    c.execute('''
        SELECT app_name, 
               SUM(bytes_sent) as total_sent,
               SUM(bytes_recv) as total_recv,
               SUM(bytes_sent + bytes_recv) as total
        FROM traffic
        WHERE timestamp > ?
        GROUP BY app_name
        ORDER BY total DESC
    ''', (since_str,))
    
    rows = c.fetchall()
    conn.close()
    
    total_all = sum(row[3] for row in rows) if rows else 0
    
    result = []
    for app, sent, recv, total in rows:
        pct = (total / total_all * 100) if total_all > 0 else 0
        result.append(AppTraffic(
            name=app,
            bytes_sent=sent,
            bytes_recv=recv,
            bytes_total=total,
            sent_formatted=format_bytes(sent),
            recv_formatted=format_bytes(recv),
            total_formatted=format_bytes(total),
            percentage=round(pct, 2)
        ))
    
    return result


def cleanup_old_data(config: Optional[NetmonConfig] = None) -> int:
    """Clean up old traffic data.
    
    Args:
        config: Optional config object
        
    Returns:
        Number of deleted records
    """
    if config is None:
        config = load_config()
    
    conn = get_connection(config)
    c = conn.cursor()
    
    cutoff = datetime.utcnow() - timedelta(days=config.data_retention_days)
    cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
    
    c.execute('DELETE FROM traffic WHERE timestamp < ?', (cutoff_str,))
    deleted = c.rowcount
    
    if deleted > 0:
        logger.info(f"Cleaned up {deleted} old records")
        c.execute('VACUUM')
    
    # Clean old webhook logs
    c.execute('''
        DELETE FROM webhook_logs WHERE id NOT IN (
            SELECT id FROM webhook_logs ORDER BY timestamp DESC LIMIT 1000
        )
    ''')
    
    conn.commit()
    conn.close()
    
    return deleted


# Excluded IPs operations

def get_excluded_ips(config: Optional[NetmonConfig] = None) -> set[str]:
    """Get set of excluded IP addresses.
    
    Returns:
        Set of IP strings
    """
    conn = get_connection(config)
    c = conn.cursor()
    c.execute('SELECT ip FROM excluded_ips')
    ips = set(row[0] for row in c.fetchall())
    conn.close()
    return ips


def get_excluded_ips_list(config: Optional[NetmonConfig] = None) -> list[ExcludedIP]:
    """Get list of excluded IPs with details.
    
    Returns:
        List of ExcludedIP objects
    """
    conn = get_connection(config)
    c = conn.cursor()
    c.execute('SELECT ip, description, added_at FROM excluded_ips ORDER BY added_at')
    rows = c.fetchall()
    conn.close()
    
    return [
        ExcludedIP(ip=row[0], description=row[1] or "", added_at=row[2])
        for row in rows
    ]


def add_excluded_ip(ip: str, description: str = "", config: Optional[NetmonConfig] = None) -> bool:
    """Add an excluded IP.
    
    Returns:
        True if successful
    """
    conn = get_connection(config)
    c = conn.cursor()
    
    try:
        c.execute(
            'INSERT OR REPLACE INTO excluded_ips (ip, description) VALUES (?, ?)',
            (ip, description)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add excluded IP: {e}")
        return False
    finally:
        conn.close()


def remove_excluded_ip(ip: str, config: Optional[NetmonConfig] = None) -> bool:
    """Remove an excluded IP.
    
    Returns:
        True if removed
    """
    conn = get_connection(config)
    c = conn.cursor()
    
    c.execute('DELETE FROM excluded_ips WHERE ip = ?', (ip,))
    removed = c.rowcount > 0
    conn.commit()
    conn.close()
    
    return removed


# Webhook operations

def get_webhook_config(config: Optional[NetmonConfig] = None) -> Optional[WebhookConfig]:
    """Get webhook configuration.
    
    Returns:
        WebhookConfig or None
    """
    conn = get_connection(config)
    c = conn.cursor()
    c.execute(
        'SELECT endpoint_url, interval_minutes, enabled, last_sent FROM webhook_config WHERE id = 1'
    )
    row = c.fetchone()
    conn.close()
    
    if row:
        return WebhookConfig(
            url=row[0],
            interval_minutes=row[1],
            enabled=bool(row[2]),
            last_sent=row[3]
        )
    return None


def set_webhook_config(
    url: str,
    interval: int = 60,
    enabled: bool = True,
    config: Optional[NetmonConfig] = None
) -> None:
    """Set webhook configuration."""
    conn = get_connection(config)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO webhook_config (id, endpoint_url, interval_minutes, enabled)
        VALUES (1, ?, ?, ?)
    ''', (url, interval, int(enabled)))
    conn.commit()
    conn.close()


def update_webhook_last_sent(config: Optional[NetmonConfig] = None) -> None:
    """Update webhook last_sent timestamp."""
    conn = get_connection(config)
    c = conn.cursor()
    c.execute(
        'UPDATE webhook_config SET last_sent = ? WHERE id = 1',
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),)
    )
    conn.commit()
    conn.close()


def set_webhook_enabled(enabled: bool, config: Optional[NetmonConfig] = None) -> bool:
    """Enable or disable webhook.
    
    Returns:
        True if updated
    """
    conn = get_connection(config)
    c = conn.cursor()
    c.execute('UPDATE webhook_config SET enabled = ? WHERE id = 1', (int(enabled),))
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def delete_webhook_config(config: Optional[NetmonConfig] = None) -> None:
    """Delete webhook configuration."""
    conn = get_connection(config)
    c = conn.cursor()
    c.execute('DELETE FROM webhook_config WHERE id = 1')
    conn.commit()
    conn.close()


def log_webhook_result(
    status: str,
    code: int,
    message: str,
    config: Optional[NetmonConfig] = None
) -> None:
    """Log webhook result."""
    conn = get_connection(config)
    c = conn.cursor()
    c.execute('''
        INSERT INTO webhook_logs (status, response_code, message)
        VALUES (?, ?, ?)
    ''', (status, code, message[:500]))
    
    # Keep only last 100 logs
    c.execute('''
        DELETE FROM webhook_logs WHERE id NOT IN (
            SELECT id FROM webhook_logs ORDER BY timestamp DESC LIMIT 100
        )
    ''')
    
    conn.commit()
    conn.close()


def get_webhook_logs(limit: int = 5, config: Optional[NetmonConfig] = None) -> list[tuple]:
    """Get recent webhook logs.
    
    Returns:
        List of (timestamp, status, code, message) tuples
    """
    conn = get_connection(config)
    c = conn.cursor()
    c.execute('''
        SELECT timestamp, status, response_code, message 
        FROM webhook_logs 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))
    logs = c.fetchall()
    conn.close()
    return logs


def get_last_traffic_timestamp(config: Optional[NetmonConfig] = None) -> Optional[str]:
    """Get timestamp of last traffic record.
    
    Returns:
        Timestamp string or None
    """
    conn = get_connection(config)
    c = conn.cursor()
    c.execute('SELECT MAX(timestamp) FROM traffic')
    result = c.fetchone()[0]
    conn.close()
    return result


def get_unknown_traffic(days: int = 7, config: Optional[NetmonConfig] = None) -> list[tuple]:
    """Get unknown traffic grouped by remote IP.
    
    Returns:
        List of (ip, sent, recv, total, count) tuples
    """
    conn = get_connection(config)
    c = conn.cursor()
    
    since = datetime.utcnow() - timedelta(days=days)
    since_str = since.strftime('%Y-%m-%d %H:%M:%S')
    
    c.execute('''
        SELECT remote_ip, 
               SUM(bytes_sent) as total_sent,
               SUM(bytes_recv) as total_recv,
               SUM(bytes_sent + bytes_recv) as total,
               COUNT(*) as count
        FROM traffic
        WHERE app_name = 'unknown' AND timestamp > ?
        GROUP BY remote_ip
        ORDER BY total DESC
    ''', (since_str,))
    
    rows = c.fetchall()
    conn.close()
    return rows


def fix_invalid_app_names(config: Optional[NetmonConfig] = None) -> int:
    """Fix invalid app names in database.
    
    Returns:
        Number of fixed records
    """
    conn = get_connection(config)
    c = conn.cursor()
    
    # Fix numeric app names (PIDs)
    c.execute("UPDATE traffic SET app_name = 'unknown' WHERE app_name GLOB '[0-9]*'")
    fixed_numeric = c.rowcount
    
    # Fix IP:port format app names
    c.execute("UPDATE traffic SET app_name = 'unknown' WHERE app_name LIKE '%.%.%.%:%'")
    fixed_ip = c.rowcount
    
    conn.commit()
    conn.close()
    
    return fixed_numeric + fixed_ip
