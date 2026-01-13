"""Network traffic collector using nethogs."""

import logging
import os
import select
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from threading import Event, Lock, Thread
from typing import Optional

from netmon.config import NetmonConfig, load_config
from netmon.database import get_excluded_ips, save_traffic
from netmon.parser import parse_nethogs_line
from netmon.utils import get_all_interfaces

logger = logging.getLogger(__name__)


class TrafficBuffer:
    """Thread-safe traffic buffer."""
    
    def __init__(self):
        self._data: dict = defaultdict(lambda: {'sent': 0, 'recv': 0, 'ips': set()})
        self._lock = Lock()
    
    def add(self, app: str, sent: float, recv: float, ip: Optional[str] = None) -> None:
        """Add traffic data to buffer."""
        with self._lock:
            self._data[app]['sent'] += sent
            self._data[app]['recv'] += recv
            if ip:
                self._data[app]['ips'].add(ip)
    
    def flush(self) -> dict:
        """Get and clear buffer data."""
        with self._lock:
            data = dict(self._data)
            self._data.clear()
            return data
    
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        with self._lock:
            return len(self._data) == 0


class NethogsCollector:
    """nethogs-based network traffic collector."""
    
    def __init__(self, config: Optional[NetmonConfig] = None):
        self.config = config or load_config()
        self.interfaces = self.config.interfaces or get_all_interfaces()
        self.buffer = TrafficBuffer()
        self.shutdown_event = Event()
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[Thread] = None
        self._writer_thread: Optional[Thread] = None
        self._excluded_ips: set[str] = set()
    
    def start(self) -> subprocess.Popen:
        """Start nethogs process.
        
        Returns:
            Popen process object
        """
        cmd = [
            'nethogs', '-t',
            '-d', str(self.config.nethogs_refresh_sec)
        ] + self.interfaces
        
        logger.info(f"Starting nethogs: {' '.join(cmd)}")
        
        env = {**os.environ, 'LANG': 'C', 'LC_ALL': 'C'}
        
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            return self._process
        except FileNotFoundError:
            logger.error("nethogs not installed! Install with: sudo apt install nethogs")
            raise
    
    def stop(self) -> None:
        """Stop nethogs process and threads."""
        self.shutdown_event.set()
        
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        
        logger.info("Collector stopped")
    
    def start_reader_thread(self) -> Thread:
        """Start reader thread that reads nethogs output."""
        self._excluded_ips = get_excluded_ips(self.config)
        
        self._reader_thread = Thread(
            target=self._reader_loop,
            daemon=True,
            name='nethogs-reader'
        )
        self._reader_thread.start()
        return self._reader_thread
    
    def start_writer_thread(self) -> Thread:
        """Start writer thread that periodically saves to database."""
        self._writer_thread = Thread(
            target=self._writer_loop,
            daemon=True,
            name='db-writer'
        )
        self._writer_thread.start()
        return self._writer_thread
    
    def _reader_loop(self) -> None:
        """Read nethogs output and buffer traffic data."""
        logger.info("Reader thread started")
        
        while not self.shutdown_event.is_set():
            try:
                if self._process is None or self._process.poll() is not None:
                    logger.warning("nethogs process not running")
                    break
                
                ready, _, _ = select.select([self._process.stdout], [], [], 1.0)
                if not ready:
                    continue
                
                line = self._process.stdout.readline()
                if not line:
                    if self._process.poll() is not None:
                        logger.warning("nethogs process terminated")
                        break
                    continue
                
                app, ip, sent, recv = parse_nethogs_line(line)
                
                if app:
                    # Check excluded IPs
                    if ip and ip in self._excluded_ips:
                        continue
                    
                    self.buffer.add(app, sent, recv, ip)
                    
            except Exception as e:
                if not self.shutdown_event.is_set():
                    logger.debug(f"Reader error: {e}")
                continue
        
        logger.info("Reader thread stopped")
    
    def _writer_loop(self) -> None:
        """Periodically write buffer to database."""
        logger.info(f"Writer thread started (interval: {self.config.db_write_interval}s)")
        last_cleanup = datetime.now()
        
        while not self.shutdown_event.is_set():
            # Interruptible sleep
            self.shutdown_event.wait(timeout=self.config.db_write_interval)
            
            if self.shutdown_event.is_set():
                break
            
            # Flush buffer and save
            data = self.buffer.flush()
            if data:
                try:
                    save_traffic(data, self.config)
                    logger.info(f"Saved to DB: {len(data)} apps")
                except Exception as e:
                    logger.error(f"DB write error: {e}")
            
            # Daily cleanup
            if (datetime.now() - last_cleanup).days >= 1:
                try:
                    from netmon.database import cleanup_old_data
                    cleanup_old_data(self.config)
                    last_cleanup = datetime.now()
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
        
        # Final flush on shutdown
        final_data = self.buffer.flush()
        if final_data:
            try:
                save_traffic(final_data, self.config)
                logger.info(f"Final buffer saved: {len(final_data)} apps")
            except Exception as e:
                logger.error(f"Final save error: {e}")
        
        logger.info("Writer thread stopped")
    
    def collect_once(self, duration: int = 60) -> dict:
        """Collect traffic for a specified duration (for testing).
        
        Args:
            duration: Collection duration in seconds
            
        Returns:
            Traffic data dict
        """
        excluded = get_excluded_ips(self.config)
        traffic_data = defaultdict(lambda: {'sent': 0, 'recv': 0, 'ips': set()})
        
        proc = self.start()
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                ready, _, _ = select.select([proc.stdout], [], [], 1.0)
                if not ready:
                    continue
                
                line = proc.stdout.readline()
                if not line:
                    break
                
                app, ip, sent, recv = parse_nethogs_line(line)
                if app:
                    if ip and ip in excluded:
                        continue
                    
                    traffic_data[app]['sent'] += sent
                    traffic_data[app]['recv'] += recv
                    if ip:
                        traffic_data[app]['ips'].add(ip)
        finally:
            self.stop()
        
        return dict(traffic_data)
    
    def is_reader_alive(self) -> bool:
        """Check if reader thread is alive."""
        return self._reader_thread is not None and self._reader_thread.is_alive()
    
    def is_writer_alive(self) -> bool:
        """Check if writer thread is alive."""
        return self._writer_thread is not None and self._writer_thread.is_alive()
    
    def refresh_excluded_ips(self) -> None:
        """Refresh excluded IPs from database."""
        self._excluded_ips = get_excluded_ips(self.config)
