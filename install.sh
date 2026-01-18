#!/bin/bash

# netmon Kurulum Scripti

set -e

echo "╔════════════════════════════════════════════╗"
echo "║  netmon - Network Trafik İzleyici Kurulum  ║"
echo "║  Sürekli Veri Toplama Modeli v2.0          ║"
echo "╚════════════════════════════════════════════╝"
echo

# Root kontrolü
if [ "$EUID" -ne 0 ]; then
    echo "❌ Bu scripti root olarak çalıştırın: sudo ./install.sh"
    exit 1
fi

# nethogs kurulumu
echo "[1/6] nethogs kuruluyor..."
apt-get update -qq
apt-get install -y nethogs python3-pip

# Dizinleri oluştur
echo "[2/6] Dizinler oluşturuluyor..."
mkdir -p /etc/netmon
mkdir -p /var/lib/netmon

# Varsayılan config dosyası oluştur (yoksa)
echo "[3/6] Config dosyası oluşturuluyor..."
if [ ! -f /etc/netmon/config.yaml ]; then
    if [ -f config.default.yaml ]; then
        cp config.default.yaml /etc/netmon/config.yaml
        echo "  ✓ /etc/netmon/config.yaml oluşturuldu"
    else
        cat > /etc/netmon/config.yaml << 'EOF'
# netmon Configuration
interfaces: []  # Boş = otomatik tespit
db_write_interval: 60
data_retention_days: 90
log_level: INFO
nethogs_refresh_sec: 5
EOF
        echo "  ✓ /etc/netmon/config.yaml oluşturuldu (varsayılan)"
    fi
else
    echo "  ℹ /etc/netmon/config.yaml zaten mevcut, atlanıyor"
fi

# Python paketini kur
echo "[4/6] netmon Python paketi kuruluyor..."

# Eski kurulumları temizle
pip3 uninstall -y netmon 2>/dev/null || true
pip3 uninstall -y UNKNOWN 2>/dev/null || true
rm -rf build/ dist/ *.egg-info

# setup.py ile kur
python3 setup.py install

# Kurulum kontrolü
if ! command -v netmon &> /dev/null; then
    echo "❌ netmon kurulumu başarısız!"
    exit 1
fi
echo "  ✓ netmon kuruldu: $(which netmon)"

# Systemd servisi
echo "[5/6] Systemd servisi kuruluyor..."
cat > /etc/systemd/system/netmon.service << 'EOF'
[Unit]
Description=netmon - Network Traffic Monitor (Continuous Collection)
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/netmon daemon
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Graceful shutdown için
TimeoutStopSec=30
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable netmon

# Servisi başlat
echo "[6/6] Servis başlatılıyor..."
systemctl restart netmon
sleep 2

if systemctl is-active --quiet netmon; then
    echo "  ✓ netmon servisi çalışıyor"
else
    echo "  ⚠ Servis başlatılamadı, logları kontrol edin: journalctl -u netmon -e"
fi

echo
echo "════════════════════════════════════════════════"
echo "✅ Kurulum tamamlandı!"
echo "════════════════════════════════════════════════"
echo
echo "TESPİT EDİLEN INTERFACE'LER:"
netmon interfaces 2>/dev/null || echo "  (Servis başlatıldıktan sonra görüntülenecek)"
echo
echo "SONRAKİ ADIMLAR:"
echo
echo "1. PLC IP'lerini ekleyin:"
echo "   sudo netmon exclude add 192.168.1.50 \"PLC1 Torna\""
echo "   sudo netmon exclude add 192.168.1.51 \"PLC2 Freze\""
echo
echo "2. Yapılandırmayı görüntüleyin:"
echo "   netmon config show"
echo "   netmon interfaces"
echo
echo "3. Raporları görüntüleyin:"
echo "   netmon today    # Bugünkü kullanım"
echo "   netmon week     # Haftalık"
echo "   netmon month    # Aylık"
echo "   netmon -f       # Canlı izleme"
echo
echo "4. Servis durumu:"
echo "   netmon status"
echo "   journalctl -u netmon -f"
echo
echo "5. Webhook ayarlamak için:"
echo "   sudo netmon webhook set https://api.example.com/netmon 60"
echo
