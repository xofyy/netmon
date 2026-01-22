"""Rich-based display functions for netmon."""

import os
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from netmon.models import AppTraffic
from netmon.utils import format_bytes

console = Console()


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_traffic_table(
    apps: list[AppTraffic],
    title: str,
    total_bytes: int,
    max_rows: int = 20
) -> None:
    """Print traffic report as a table.
    
    Args:
        apps: List of AppTraffic objects
        title: Report title
        total_bytes: Total traffic in bytes
        max_rows: Maximum rows to display
    """
    table = Table(
        title=f"[bold]{title}[/bold]\nToplam: {format_bytes(total_bytes)}",
        show_header=True,
        header_style="bold cyan"
    )
    
    table.add_column("Uygulama", style="white", width=25)
    table.add_column("Gönderim", justify="right", style="green")
    table.add_column("Alım", justify="right", style="blue")
    table.add_column("Toplam", justify="right", style="yellow")
    table.add_column("%", justify="right")
    table.add_column("", width=20)  # Progress bar
    
    for app in apps[:max_rows]:
        # Progress bar
        bar_width = int(app.percentage / 5)
        bar = "█" * bar_width
        
        table.add_row(
            app.name[:24],
            app.sent_formatted,
            app.recv_formatted,
            app.total_formatted,
            f"{app.percentage:.1f}%",
            f"[cyan]{bar}[/cyan]"
        )
    
    console.print()
    console.print(table)
    
    if len(apps) > max_rows:
        console.print(f"\n[dim]... ve {len(apps) - max_rows} uygulama daha[/dim]")
    
    console.print()


def print_status(
    running: bool,
    pid: Optional[int],
    uptime: Optional[str],
    last_data: Optional[str],
    interfaces: list[str],
    db_interval: int,
    webhook_status: Optional[str]
) -> None:
    """Print daemon status panel.
    
    Args:
        running: Whether daemon is running
        pid: Process ID
        uptime: Uptime string
        last_data: Last data timestamp
        interfaces: List of interfaces
        db_interval: DB write interval
        webhook_status: Webhook status string
    """
    if running:
        status_text = f"[green]✓ Çalışıyor[/green] (PID: {pid})"
        if uptime:
            status_text += f" - {uptime}"
    else:
        status_text = "[red]✗ Çalışmıyor[/red]"
    
    lines = [
        f"Durum: {status_text}",
        f"Son veri: {last_data or 'Henüz yok'}",
        f"Interface'ler: {', '.join(interfaces)}",
        f"DB yazma aralığı: {db_interval // 60} dakika",
    ]
    
    if webhook_status:
        lines.append(f"Webhook: {webhook_status}")
    
    panel = Panel(
        "\n".join(lines),
        title="[bold]netmon Durumu[/bold]",
        border_style="cyan"
    )
    
    console.print()
    console.print(panel)
    console.print()


def print_config(config_data: dict) -> None:
    """Print configuration panel."""
    lines = []
    
    interfaces = config_data.get('interfaces', [])
    if interfaces:
        lines.append(f"Interface'ler: {', '.join(interfaces)}")
    else:
        lines.append("Interface'ler: [dim]Otomatik[/dim]")
    
    interval = config_data.get('db_write_interval', 300)
    lines.append(f"DB yazma aralığı: {interval}s ({interval // 60} dakika)")
    
    retention = config_data.get('data_retention_days', 90)
    lines.append(f"Veri saklama süresi: {retention} gün")
    
    log_level = config_data.get('log_level', 'INFO')
    lines.append(f"Log seviyesi: {log_level}")
    
    panel = Panel(
        "\n".join(lines),
        title="[bold]Yapılandırma[/bold]",
        border_style="blue"
    )
    
    console.print()
    console.print(panel)
    console.print()


def print_interfaces(interfaces: list[str], default: Optional[str] = None) -> None:
    """Print interface list."""
    table = Table(title="[bold]Aktif Network Interface'leri[/bold]")
    table.add_column("Interface", style="cyan")
    table.add_column("", style="dim")
    
    for iface in sorted(interfaces):
        marker = "(varsayılan)" if iface == default else ""
        table.add_row(iface, marker)
    
    console.print()
    console.print(table)
    console.print(f"\nToplam: {len(interfaces)} interface")
    console.print()


def print_excluded_ips(ips: list) -> None:
    """Print excluded IPs table."""
    if not ips:
        console.print("\n[dim]Hariç tutulan IP yok.[/dim]\n")
        return
    
    table = Table(title="[bold]Hariç Tutulan IP'ler[/bold]")
    table.add_column("IP", style="cyan", width=18)
    table.add_column("Açıklama", width=25)
    table.add_column("Eklenme", style="dim", width=20)
    
    for ip_data in ips:
        table.add_row(
            ip_data.ip,
            ip_data.description or "-",
            str(ip_data.added_at)[:16] if ip_data.added_at else "-"
        )
    
    console.print()
    console.print(table)
    console.print()


def print_webhook_status(
    url: Optional[str],
    enabled: bool,
    interval: int,
    last_sent: Optional[str],
    logs: list[tuple]
) -> None:
    """Print webhook status panel."""
    if not url:
        console.print("\n[dim]Webhook yapılandırılmamış.[/dim]")
        console.print("Ayarlamak için: [cyan]netmon webhook set <url>[/cyan]\n")
        return
    
    status = "[green]✓ Aktif[/green]" if enabled else "[red]✗ Devre dışı[/red]"
    
    lines = [
        f"Durum: {status}",
        f"URL: {url}",
        f"Gönderim aralığı: {interval} dakika",
        f"Son gönderim: {last_sent or 'Henüz gönderilmedi'}"
    ]
    
    panel = Panel(
        "\n".join(lines),
        title="[bold]Webhook Durumu[/bold]",
        border_style="cyan"
    )
    
    console.print()
    console.print(panel)
    
    if logs:
        console.print("\n[bold]Son Gönderimler:[/bold]")
        for ts, status, code, msg in logs:
            icon = "[green]✓[/green]" if status == 'success' else "[red]✗[/red]"
            console.print(f"  {icon} {ts[:16]} - HTTP {code} - {msg[:40]}")
    
    console.print()


def print_unknown_traffic(rows: list[tuple], total_bytes: int, days: int) -> None:
    """Print unknown traffic details."""
    if not rows:
        console.print(f"\n[dim]Son {days} günde unknown trafik bulunamadı.[/dim]\n")
        return
    
    table = Table(
        title=f"[bold]Unknown Trafik Detayı (Son {days} gün)[/bold]\nToplam: {format_bytes(total_bytes)}"
    )
    
    table.add_column("Remote IP", style="cyan", width=24)
    table.add_column("Gönderim", justify="right", style="green")
    table.add_column("Alım", justify="right", style="blue")
    table.add_column("Toplam", justify="right", style="yellow")
    table.add_column("Kayıt", justify="right")
    
    for ip, sent, recv, total, count in rows[:20]:
        ip_display = ip if ip else "(yerel/bilinmeyen)"
        table.add_row(
            ip_display[:23],
            format_bytes(sent),
            format_bytes(recv),
            format_bytes(total),
            str(count)
        )
    
    console.print()
    console.print(table)
    
    if len(rows) > 20:
        console.print(f"\n[dim]... ve {len(rows) - 20} IP daha[/dim]")
    
    console.print("\n[dim]İpucu: Bilinen cihazları hariç tutmak için:[/dim]")
    console.print("  [cyan]sudo netmon exclude add <IP> \"Açıklama\"[/cyan]\n")


def build_live_panel(
    traffic: dict,
    interfaces: list[str],
    timestamp: str
) -> Panel:
    """Build live traffic panel for Rich Live display.
    
    Args:
        traffic: Traffic data dict
        interfaces: List of interfaces
        timestamp: Current timestamp
        
    Returns:
        Rich Panel object
    """
    table = Table(show_header=True, header_style="bold")
    table.add_column("Uygulama", width=25)
    table.add_column("Hız ↑", justify="right", width=12)
    table.add_column("Hız ↓", justify="right", width=12)
    table.add_column("Toplam", justify="right", width=15)
    
    # Sort by total traffic
    sorted_apps = sorted(
        traffic.items(),
        key=lambda x: x[1]['sent'] + x[1]['recv'],
        reverse=True
    )[:15]
    
    for app, data in sorted_apps:
        total = data['sent'] + data['recv']
        if total > 0:
            rate_up = format_bytes(data.get('rate_sent', 0)) + "/s"
            rate_down = format_bytes(data.get('rate_recv', 0)) + "/s"
            table.add_row(
                app[:24],
                f"[green]{rate_up}[/green]",
                f"[blue]{rate_down}[/blue]",
                f"[yellow]{format_bytes(total)}[/yellow]"
            )
    
    return Panel(
        table,
        title=f"[bold]Canlı Trafik - {timestamp}[/bold]\n[dim]Interface'ler: {', '.join(interfaces)}[/dim]",
        subtitle="[dim]Çıkış için Ctrl+C[/dim]",
        border_style="cyan"
    )


def run_live_monitor(collector, interfaces: list[str]) -> None:
    """Run live traffic monitor with Rich Live.
    
    Args:
        collector: NethogsCollector instance
        interfaces: List of interfaces
    """
    import select
    import time
    
    from netmon.parser import parse_nethogs_line
    
    traffic = {}
    
    console.print()
    
    try:
        with Live(
            build_live_panel({}, interfaces, datetime.now().strftime('%H:%M:%S')),
            console=console,
            refresh_per_second=4
        ) as live:
            last_update = time.time()
            
            while True:
                try:
                    ready, _, _ = select.select([collector._process.stdout], [], [], 0.5)
                    if not ready:
                        continue
                    
                    line = collector._process.stdout.readline()
                    if not line:
                        break

                    # Parse with refresh_sec to get bytes transferred during interval
                    app, ip, sent, recv = parse_nethogs_line(line, collector.config.nethogs_refresh_sec)

                    if app:
                        if app not in traffic:
                            traffic[app] = {'sent': 0, 'recv': 0, 'rate_sent': 0, 'rate_recv': 0}

                        # Display rate (bytes/second) - divide by refresh interval
                        traffic[app]['rate_sent'] = sent / collector.config.nethogs_refresh_sec
                        traffic[app]['rate_recv'] = recv / collector.config.nethogs_refresh_sec
                        # Accumulate total bytes transferred
                        traffic[app]['sent'] += sent
                        traffic[app]['recv'] += recv
                    
                    # Update display every refresh interval
                    if time.time() - last_update >= collector.config.nethogs_refresh_sec:
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        live.update(build_live_panel(traffic, interfaces, timestamp))
                        last_update = time.time()
                        
                except KeyboardInterrupt:
                    break
                    
    except KeyboardInterrupt:
        pass
    
    console.print("\n[dim]Canlı izleme sonlandırıldı.[/dim]\n")
