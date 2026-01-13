"""CLI commands for netmon using Typer."""

import os
import sys
from typing import Optional

import typer
from rich.console import Console

from netmon import __version__
from netmon.config import (
    NetmonConfig,
    load_config,
    save_config,
    set_config_value,
)
from netmon.database import (
    add_excluded_ip,
    delete_webhook_config,
    fix_invalid_app_names,
    get_excluded_ips_list,
    get_last_traffic_timestamp,
    get_traffic_report,
    get_unknown_traffic,
    get_webhook_config,
    get_webhook_logs,
    init_db,
    remove_excluded_ip,
    set_webhook_config,
    set_webhook_enabled,
)
from netmon.display import (
    console,
    print_config,
    print_error,
    print_excluded_ips,
    print_info,
    print_interfaces,
    print_status,
    print_success,
    print_traffic_table,
    print_unknown_traffic,
    print_webhook_status,
)
from netmon.utils import format_bytes, get_all_interfaces, get_default_interface, is_valid_ip

# Create Typer app
app = typer.Typer(
    name="netmon",
    help="Uygulama bazlı network trafik izleyici",
    add_completion=False,
    no_args_is_help=True,
)

# Subcommand groups
exclude_app = typer.Typer(help="IP hariç tutma komutları")
webhook_app = typer.Typer(help="Webhook komutları")
config_app = typer.Typer(help="Yapılandırma komutları")

app.add_typer(exclude_app, name="exclude")
app.add_typer(webhook_app, name="webhook")
app.add_typer(config_app, name="config")


def require_root() -> None:
    """Check for root privileges."""
    if os.geteuid() != 0:
        print_error("Root yetkisi gerekli. sudo ile çalıştırın.")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════
# SERVICE COMMANDS
# ═══════════════════════════════════════════════════════════════

@app.command()
def start(
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Daemon olarak başlat")
):
    """Daemon'u başlat."""
    require_root()
    init_db()
    
    from netmon.daemon import DaemonManager, run_daemon
    
    config = load_config()
    dm = DaemonManager(config.pid_path)
    
    if dm.is_running():
        print_error("netmon zaten çalışıyor")
        raise typer.Exit(1)
    
    if daemon:
        print_info("netmon daemon başlatılıyor...")
        dm.daemonize()
    
    run_daemon(config)


@app.command()
def stop():
    """Daemon'u durdur."""
    require_root()
    
    from netmon.daemon import DaemonManager
    
    config = load_config()
    dm = DaemonManager(config.pid_path)
    
    if not dm.is_running():
        print_info("netmon zaten çalışmıyor")
        return
    
    pid = dm.get_pid()
    print_info(f"Durduruluyor (PID: {pid})...")
    
    if dm.stop():
        print_success("netmon durduruldu")
    else:
        print_error("Durdurma başarısız")
        raise typer.Exit(1)


@app.command()
def status():
    """Servis durumunu göster."""
    init_db()
    
    from netmon.daemon import DaemonManager
    
    config = load_config()
    dm = DaemonManager(config.pid_path)
    
    running = dm.is_running()
    pid = dm.get_pid()
    uptime = dm.get_uptime()
    last_data = get_last_traffic_timestamp(config)
    interfaces = config.interfaces or get_all_interfaces()
    
    webhook_config = get_webhook_config(config)
    webhook_status = None
    if webhook_config and webhook_config.url:
        webhook_status = "Aktif" if webhook_config.enabled else "Devre dışı"
    
    print_status(
        running=running,
        pid=pid,
        uptime=uptime,
        last_data=last_data,
        interfaces=interfaces,
        db_interval=config.db_write_interval,
        webhook_status=webhook_status
    )


@app.command("live")
@app.command("-f", hidden=True)
def live_monitor():
    """Canlı trafik izleme."""
    require_root()
    init_db()
    
    from netmon.collector import NethogsCollector
    from netmon.display import run_live_monitor
    
    config = load_config()
    collector = NethogsCollector(config)
    
    try:
        collector.start()
        run_live_monitor(collector, collector.interfaces)
    except FileNotFoundError:
        print_error("nethogs kurulu değil! Kurmak için: sudo apt install nethogs")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        collector.stop()


# ═══════════════════════════════════════════════════════════════
# REPORT COMMANDS
# ═══════════════════════════════════════════════════════════════

@app.command()
def today():
    """Bugünkü kullanım raporu."""
    init_db()
    config = load_config()
    apps = get_traffic_report(days=1, config=config)
    total = sum(a.bytes_total for a in apps)
    print_traffic_table(apps, "BUGÜNKÜ KULLANIM", total)


@app.command()
def week():
    """Son 7 günlük rapor."""
    init_db()
    config = load_config()
    apps = get_traffic_report(days=7, config=config)
    total = sum(a.bytes_total for a in apps)
    print_traffic_table(apps, "SON 7 GÜNLÜK KULLANIM", total)


@app.command()
def month():
    """Son 30 günlük rapor."""
    init_db()
    config = load_config()
    apps = get_traffic_report(days=30, config=config)
    total = sum(a.bytes_total for a in apps)
    print_traffic_table(apps, "SON 30 GÜNLÜK KULLANIM", total)


@app.command()
def top(
    n: int = typer.Argument(10, help="Gösterilecek uygulama sayısı")
):
    """En çok trafik kullanan uygulamalar."""
    init_db()
    config = load_config()
    apps = get_traffic_report(days=30, config=config)
    total = sum(a.bytes_total for a in apps)
    print_traffic_table(apps[:n], f"EN ÇOK KULLANAN {n} UYGULAMA", total, max_rows=n)


@app.command()
def unknown(
    days: int = typer.Argument(7, help="Kaç günlük veri")
):
    """Tespit edilemeyen trafik detayı."""
    init_db()
    config = load_config()
    rows = get_unknown_traffic(days=days, config=config)
    total = sum(row[3] for row in rows) if rows else 0
    print_unknown_traffic(rows, total, days)


# ═══════════════════════════════════════════════════════════════
# EXCLUDE COMMANDS
# ═══════════════════════════════════════════════════════════════

@exclude_app.command("add")
def exclude_add(
    ip: str = typer.Argument(..., help="Hariç tutulacak IP adresi"),
    description: str = typer.Argument("", help="Açıklama")
):
    """IP adresi ekle."""
    if not is_valid_ip(ip):
        print_error(f"Geçersiz IP adresi: {ip}")
        raise typer.Exit(1)
    
    init_db()
    if add_excluded_ip(ip, description):
        print_success(f"Eklendi: {ip} ({description})")
    else:
        print_error("Ekleme başarısız")
        raise typer.Exit(1)


@exclude_app.command("remove")
def exclude_remove(
    ip: str = typer.Argument(..., help="Kaldırılacak IP adresi")
):
    """IP adresini kaldır."""
    init_db()
    if remove_excluded_ip(ip):
        print_success(f"Kaldırıldı: {ip}")
    else:
        print_error(f"Bulunamadı: {ip}")
        raise typer.Exit(1)


@exclude_app.command("list")
def exclude_list():
    """Hariç tutulan IP'leri listele."""
    init_db()
    ips = get_excluded_ips_list()
    print_excluded_ips(ips)


# ═══════════════════════════════════════════════════════════════
# WEBHOOK COMMANDS
# ═══════════════════════════════════════════════════════════════

@webhook_app.command("set")
def webhook_set(
    url: str = typer.Argument(..., help="Webhook URL"),
    interval: int = typer.Argument(60, help="Gönderim aralığı (dakika)")
):
    """Webhook endpoint ayarla."""
    init_db()
    set_webhook_config(url, interval, enabled=True)
    print_success("Webhook ayarlandı")
    print_info(f"URL: {url}")
    print_info(f"Gönderim aralığı: {interval} dakika")


@webhook_app.command("remove")
def webhook_remove():
    """Webhook'u kaldır."""
    init_db()
    delete_webhook_config()
    print_success("Webhook kaldırıldı")


@webhook_app.command("enable")
def webhook_enable():
    """Webhook'u etkinleştir."""
    init_db()
    if set_webhook_enabled(True):
        print_success("Webhook etkinleştirildi")
    else:
        print_error("Önce webhook ayarlayın: netmon webhook set <url>")


@webhook_app.command("disable")
def webhook_disable():
    """Webhook'u devre dışı bırak."""
    init_db()
    set_webhook_enabled(False)
    print_success("Webhook devre dışı bırakıldı")


@webhook_app.command("status")
def webhook_status():
    """Webhook durumunu göster."""
    init_db()
    config = load_config()
    wh = get_webhook_config(config)
    logs = get_webhook_logs(5, config)
    
    print_webhook_status(
        url=wh.url if wh else None,
        enabled=wh.enabled if wh else False,
        interval=wh.interval_minutes if wh else 60,
        last_sent=str(wh.last_sent) if wh and wh.last_sent else None,
        logs=logs
    )


@webhook_app.command("test")
def webhook_test():
    """Test gönderimi yap."""
    init_db()
    print_info("Webhook test gönderimi yapılıyor...")
    
    from netmon.webhook import send_webhook
    send_webhook(test=True)


@webhook_app.command("payload")
def webhook_payload():
    """Gönderilecek JSON'u göster."""
    init_db()
    
    import json
    from netmon.webhook import build_webhook_payload
    
    payload = build_webhook_payload(period='daily')
    console.print("\n[bold]Gönderilecek JSON yapısı:[/bold]")
    console.print_json(json.dumps(payload, ensure_ascii=False))
    console.print()


# ═══════════════════════════════════════════════════════════════
# CONFIG COMMANDS
# ═══════════════════════════════════════════════════════════════

@config_app.command("show")
def config_show():
    """Yapılandırmayı göster."""
    config = load_config()
    print_config(config.model_dump())


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Ayar anahtarı"),
    value: str = typer.Argument(..., help="Yeni değer")
):
    """Yapılandırma değeri ayarla.
    
    Anahtarlar:
    - db_write_interval: DB yazma aralığı (saniye)
    - data_retention_days: Veri saklama süresi (gün)
    - log_level: Log seviyesi (DEBUG, INFO, WARNING, ERROR)
    - interfaces: Interface listesi (virgülle ayrılmış)
    """
    require_root()
    
    try:
        set_config_value(key, value)
        print_success(f"{key} = {value}")
        print_info("Değişiklik için servisi yeniden başlatın: sudo systemctl restart netmon")
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except PermissionError:
        print_error("İzin hatası. sudo ile çalıştırın.")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════
# OTHER COMMANDS
# ═══════════════════════════════════════════════════════════════

@app.command()
def interfaces():
    """Aktif network interface'lerini göster."""
    ifaces = get_all_interfaces()
    default = get_default_interface()
    print_interfaces(ifaces, default)


@app.command()
def cleanup():
    """Veritabanındaki geçersiz uygulama adlarını düzelt."""
    init_db()
    print_info("Geçersiz uygulama adları düzeltiliyor...")
    fixed = fix_invalid_app_names()
    
    if fixed > 0:
        print_success(f"{fixed} kayıt düzeltildi")
    else:
        print_success("Düzeltilecek kayıt bulunamadı")


@app.command()
def version():
    """Versiyon bilgisi."""
    console.print(f"netmon v{__version__}")


@app.command()
def test(
    duration: int = typer.Argument(60, help="Test süresi (saniye)")
):
    """Test modunda veri topla."""
    require_root()
    init_db()
    
    print_info(f"Test modu - {duration} saniye veri toplanıyor...")
    
    from netmon.collector import NethogsCollector
    
    config = load_config()
    collector = NethogsCollector(config)
    
    try:
        traffic = collector.collect_once(duration)
        
        console.print(f"\n[bold]Toplanan veri ({len(traffic)} uygulama):[/bold]")
        for app, data in sorted(traffic.items(), key=lambda x: x[1]['sent']+x[1]['recv'], reverse=True):
            total = data['sent'] + data['recv']
            if total > 0:
                console.print(f"  {app}: {format_bytes(total)}")
        console.print()
        
    except FileNotFoundError:
        print_error("nethogs kurulu değil! Kurmak için: sudo apt install nethogs")
        raise typer.Exit(1)


@app.command()
def install():
    """Systemd servisi olarak kur."""
    require_root()
    
    import subprocess
    from pathlib import Path
    
    # Get script path
    script_path = Path(sys.executable).parent / "netmon"
    if not script_path.exists():
        script_path = Path("/usr/local/bin/netmon")
    
    service_content = f"""[Unit]
Description=netmon - Network Traffic Monitor
After=network.target

[Service]
Type=simple
ExecStart={script_path} start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_path = Path("/etc/systemd/system/netmon.service")
    service_path.write_text(service_content)
    
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'netmon'], check=True)
    subprocess.run(['systemctl', 'start', 'netmon'], check=True)
    
    print_success("netmon servisi kuruldu ve başlatıldı")
    print_info("Durum: systemctl status netmon")
    print_info("Loglar: journalctl -u netmon -f")


if __name__ == "__main__":
    app()
