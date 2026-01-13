"""Daemon management for netmon."""

import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Optional

from netmon.collector import NethogsCollector
from netmon.config import NetmonConfig, load_config, setup_logging
from netmon.database import init_db

logger = logging.getLogger(__name__)


class GracefulKiller:
    """Signal handler for graceful shutdown."""
    
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self._exit_handler)
        signal.signal(signal.SIGTERM, self._exit_handler)
    
    def _exit_handler(self, signum, frame):
        self.kill_now = True


class DaemonManager:
    """Manage daemon process."""
    
    def __init__(self, pid_file: Path):
        self.pid_file = pid_file
        self._start_time: Optional[datetime] = None
    
    def is_running(self) -> bool:
        """Check if daemon is running.
        
        Returns:
            True if running
        """
        if not self.pid_file.exists():
            return False
        
        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False
    
    def get_pid(self) -> Optional[int]:
        """Get daemon PID.
        
        Returns:
            PID or None
        """
        if not self.pid_file.exists():
            return None
        
        try:
            return int(self.pid_file.read_text().strip())
        except ValueError:
            return None
    
    def write_pid(self) -> None:
        """Write current PID to file."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))
        self._start_time = datetime.now()
    
    def cleanup_pid(self) -> None:
        """Remove PID file."""
        self.pid_file.unlink(missing_ok=True)
    
    def stop(self) -> bool:
        """Stop running daemon.
        
        Returns:
            True if stopped
        """
        pid = self.get_pid()
        if pid is None:
            return False
        
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to stop
            for _ in range(50):  # 5 seconds
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except OSError:
                    break
            
            self.cleanup_pid()
            return True
        except OSError:
            self.cleanup_pid()
            return False
    
    def get_uptime(self) -> Optional[str]:
        """Get daemon uptime.
        
        Returns:
            Formatted uptime string
        """
        if not self.is_running():
            return None
        
        # Try to get process start time from /proc
        pid = self.get_pid()
        if pid:
            try:
                stat_file = Path(f"/proc/{pid}/stat")
                if stat_file.exists():
                    # Get system boot time
                    with open("/proc/uptime") as f:
                        system_uptime = float(f.read().split()[0])
                    
                    # Get process start time (in clock ticks)
                    with open(stat_file) as f:
                        fields = f.read().split()
                        start_time_ticks = int(fields[21])
                    
                    # Convert to seconds
                    clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
                    process_start = start_time_ticks / clock_ticks
                    
                    uptime_secs = system_uptime - process_start
                    
                    if uptime_secs < 60:
                        return f"{int(uptime_secs)}s"
                    elif uptime_secs < 3600:
                        return f"{int(uptime_secs // 60)}m"
                    elif uptime_secs < 86400:
                        return f"{int(uptime_secs // 3600)}h {int((uptime_secs % 3600) // 60)}m"
                    else:
                        return f"{int(uptime_secs // 86400)}d {int((uptime_secs % 86400) // 3600)}h"
            except Exception:
                pass
        
        return None
    
    def daemonize(self) -> None:
        """Daemonize the process."""
        # First fork
        if os.fork() > 0:
            sys.exit(0)
        
        os.setsid()
        
        # Second fork
        if os.fork() > 0:
            sys.exit(0)
        
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        
        with open('/dev/null', 'r') as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        
        # Write PID file
        self.write_pid()


def run_daemon(config: Optional[NetmonConfig] = None) -> None:
    """Run the main daemon loop.
    
    Args:
        config: Optional config object
    """
    if config is None:
        config = load_config()
    
    # Setup logging
    setup_logging(config)
    
    # Initialize database
    init_db(config)
    
    logger.info("=" * 60)
    logger.info("netmon daemon starting")
    
    # Create components
    collector = NethogsCollector(config)
    daemon_manager = DaemonManager(config.pid_path)
    killer = GracefulKiller()
    
    logger.info(f"Interfaces: {', '.join(collector.interfaces)}")
    logger.info(f"DB write interval: {config.db_write_interval}s")
    logger.info(f"Data retention: {config.data_retention_days} days")
    logger.info("=" * 60)
    
    # Write PID
    try:
        daemon_manager.write_pid()
    except PermissionError:
        logger.warning("Cannot write PID file")
    
    # Start nethogs
    try:
        collector.start()
    except FileNotFoundError:
        logger.error("nethogs not installed!")
        sys.exit(1)
    
    # Start threads
    collector.start_reader_thread()
    collector.start_writer_thread()
    
    # Start webhook worker
    webhook_thread = Thread(
        target=_webhook_worker,
        args=(config, collector.shutdown_event),
        daemon=True,
        name='webhook-worker'
    )
    webhook_thread.start()
    
    logger.info("All worker threads started")
    
    # Main loop
    while not killer.kill_now and not collector.shutdown_event.is_set():
        try:
            # Check nethogs process
            if collector._process and collector._process.poll() is not None:
                logger.warning("nethogs died, restarting...")
                time.sleep(5)
                collector.start()
                collector.refresh_excluded_ips()
                collector.start_reader_thread()
            
            # Check threads
            if not collector.is_reader_alive() and not collector.shutdown_event.is_set():
                logger.warning("Reader thread died, restarting...")
                collector.start_reader_thread()
            
            if not collector.is_writer_alive() and not collector.shutdown_event.is_set():
                logger.warning("Writer thread died, restarting...")
                collector.start_writer_thread()
            
            if not webhook_thread.is_alive() and not collector.shutdown_event.is_set():
                logger.warning("Webhook thread died, restarting...")
                webhook_thread = Thread(
                    target=_webhook_worker,
                    args=(config, collector.shutdown_event),
                    daemon=True,
                    name='webhook-worker'
                )
                webhook_thread.start()
            
            # Sleep
            collector.shutdown_event.wait(timeout=config.main_loop_check_sec)
            
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            collector.shutdown_event.wait(timeout=config.main_loop_check_sec)
    
    # Shutdown
    logger.info("Shutting down...")
    collector.stop()
    daemon_manager.cleanup_pid()
    logger.info("netmon daemon stopped")


def _webhook_worker(config: NetmonConfig, shutdown_event) -> None:
    """Webhook worker thread."""
    from netmon.database import get_webhook_config
    from netmon.webhook import send_webhook
    
    logger.info("Webhook worker started")
    
    while not shutdown_event.is_set():
        try:
            webhook_config = get_webhook_config(config)
            
            if webhook_config and webhook_config.enabled and webhook_config.url:
                interval_sec = webhook_config.interval_minutes * 60
                
                should_send = False
                if webhook_config.last_sent:
                    try:
                        last = datetime.fromisoformat(str(webhook_config.last_sent))
                        elapsed = (datetime.now() - last).total_seconds()
                        should_send = elapsed >= interval_sec
                    except Exception:
                        should_send = True
                else:
                    should_send = True
                
                if should_send:
                    send_webhook(config)
                
                shutdown_event.wait(timeout=60)
            else:
                shutdown_event.wait(timeout=300)
                
        except Exception as e:
            logger.error(f"Webhook worker error: {e}")
            shutdown_event.wait(timeout=60)
    
    logger.info("Webhook worker stopped")
