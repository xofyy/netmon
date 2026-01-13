"""Webhook HTTP client for netmon."""

import logging
import socket
import time
from datetime import datetime
from typing import Any, Optional

import httpx

from netmon.config import NetmonConfig, load_config
from netmon.database import (
    get_excluded_ips_list,
    get_traffic_report,
    get_webhook_config,
    log_webhook_result,
    update_webhook_last_sent,
)
from netmon.utils import format_bytes, get_all_interfaces, get_hostname

logger = logging.getLogger(__name__)


class WebhookSender:
    """HTTP client for sending webhook data."""
    
    def __init__(
        self,
        endpoint: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get HTTP client (lazy init)."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client
    
    def send(self, payload: dict[str, Any]) -> bool:
        """Send payload to webhook endpoint.
        
        Args:
            payload: JSON payload to send
            
        Returns:
            True if successful
        """
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.post(
                    self.endpoint,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "netmon/2.0",
                        "X-Netmon-Hostname": get_hostname()
                    }
                )
                response.raise_for_status()
                logger.info(f"Webhook sent successfully to {self.endpoint}")
                return True
                
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"HTTP error {e.response.status_code} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                
            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"Request error: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Unexpected error: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        logger.error(f"Failed after {self.max_retries} attempts: {last_error}")
        return False
    
    def test_connection(self) -> tuple[bool, str]:
        """Test connection to endpoint.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            response = self.client.post(
                self.endpoint,
                json={"test": True},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code < 500:
                return True, f"Bağlantı OK (HTTP {response.status_code})"
            else:
                return False, f"Sunucu hatası (HTTP {response.status_code})"
                
        except httpx.ConnectError:
            return False, f"Bağlantı reddedildi: {self.endpoint}"
            
        except httpx.TimeoutException:
            return False, f"Zaman aşımı: {self.endpoint}"
            
        except Exception as e:
            return False, f"Bağlantı hatası: {e}"
    
    def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None


def build_webhook_payload(
    period: str = 'daily',
    config: Optional[NetmonConfig] = None
) -> dict[str, Any]:
    """Build webhook JSON payload.
    
    Args:
        period: Report period (hourly, daily, weekly, monthly)
        config: Optional config object
        
    Returns:
        Payload dict
    """
    if config is None:
        config = load_config()
    
    days_map = {
        'hourly': 1/24,
        'daily': 1,
        'weekly': 7,
        'monthly': 30
    }
    days = days_map.get(period, 1)
    
    # Get traffic report
    apps = get_traffic_report(days=days, config=config)
    
    total_sent = sum(a.bytes_sent for a in apps)
    total_recv = sum(a.bytes_recv for a in apps)
    total_bytes = sum(a.bytes_total for a in apps)
    
    # Get excluded IPs
    excluded = get_excluded_ips_list(config)
    
    # Get interfaces
    interfaces = config.interfaces or get_all_interfaces()
    
    payload = {
        'version': '2.0',
        'hostname': get_hostname(),
        'timestamp': datetime.now().isoformat(),
        'report_period': period,
        'report_generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'interfaces': interfaces,
        'summary': {
            'total_bytes_sent': total_sent,
            'total_bytes_recv': total_recv,
            'total_bytes': total_bytes,
            'total_sent_formatted': format_bytes(total_sent),
            'total_recv_formatted': format_bytes(total_recv),
            'total_formatted': format_bytes(total_bytes),
            'application_count': len(apps)
        },
        'applications': [
            {
                'name': app.name,
                'bytes_sent': app.bytes_sent,
                'bytes_recv': app.bytes_recv,
                'bytes_total': app.bytes_total,
                'sent_formatted': app.sent_formatted,
                'recv_formatted': app.recv_formatted,
                'total_formatted': app.total_formatted,
                'percentage': app.percentage
            }
            for app in apps[:50]  # Limit to 50 apps
        ],
        'excluded_ips': [
            {'ip': ip.ip, 'description': ip.description}
            for ip in excluded
        ]
    }
    
    return payload


def send_webhook(
    config: Optional[NetmonConfig] = None,
    test: bool = False
) -> bool:
    """Send webhook with current data.
    
    Args:
        config: Optional config object
        test: Whether this is a test send
        
    Returns:
        True if successful
    """
    if config is None:
        config = load_config()
    
    webhook_config = get_webhook_config(config)
    
    if not webhook_config or not webhook_config.url:
        if test:
            from netmon.display import print_error
            print_error("Webhook ayarlanmamış")
        return False
    
    if not webhook_config.enabled and not test:
        return False
    
    # Determine period based on interval
    interval = webhook_config.interval_minutes
    if interval <= 60:
        period = 'hourly'
    elif interval <= 1440:
        period = 'daily'
    elif interval <= 10080:
        period = 'weekly'
    else:
        period = 'monthly'
    
    # Build payload
    payload = build_webhook_payload(period=period, config=config)
    
    # Send
    sender = WebhookSender(webhook_config.url)
    
    try:
        success = sender.send(payload)
        
        if success:
            log_webhook_result('success', 200, 'OK', config)
            update_webhook_last_sent(config)
            
            if test:
                from netmon.display import print_success
                print_success(f"Webhook başarıyla gönderildi")
        else:
            log_webhook_result('error', 0, 'Send failed', config)
            
            if test:
                from netmon.display import print_error
                print_error("Webhook gönderilemedi")
        
        return success
        
    except Exception as e:
        log_webhook_result('error', 0, str(e), config)
        
        if test:
            from netmon.display import print_error
            print_error(f"Hata: {e}")
        
        return False
    finally:
        sender.close()
