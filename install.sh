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
echo "[1/5] nethogs kuruluyor..."
apt-get update -qq
apt-get install -y nethogs

# Dizinleri oluştur
echo "[2/5] Dizinler oluşturuluyor..."
mkdir -p /etc/netmon
mkdir -p /var/lib/netmon

# Varsayılan config dosyası oluştur (yoksa)
echo "[3/5] Config dosyası oluşturuluyor..."
if [ ! -f /etc/netmon/config.json ]; then
    cat > /etc/netmon/config.json << 'EOF'
{
  "interfaces": [],
  "db_write_interval": 300,
  "data_retention_days": 90,
  "log_level": "INFO"
}
EOF
    echo "  ✓ /etc/netmon/config.json oluşturuldu"
else
    echo "  ℹ /etc/netmon/config.json zaten mevcut, atlanıyor"
fi

# Ana scripti kopyala
echo "[4/5] netmon kuruluyor..."
cp netmon /usr/local/bin/netmon
chmod +x /usr/local/bin/netmon

# Systemd servisi
echo "[5/5] Systemd servisi kuruluyor..."
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

echo
echo "════════════════════════════════════════════════"
echo "✅ Kurulum tamamlandı!"
echo "════════════════════════════════════════════════"
echo
echo "TESPİT EDİLEN INTERFACE'LER:"
/usr/local/bin/netmon interfaces 2>/dev/null || echo "  (Servis başlatıldıktan sonra görüntülenecek)"
echo
echo "SONRAKİ ADIMLAR:"
echo
echo "1. PLC IP'lerini ekleyin:"
echo "   sudo netmon exclude add 192.168.1.50 \"PLC1 Torna\""
echo "   sudo netmon exclude add 192.168.1.51 \"PLC2 Freze\""
echo
echo "2. Servisi başlatın:"
echo "   sudo systemctl start netmon"
echo
echo "3. Yapılandırmayı görüntüleyin:"
echo "   netmon config show"
echo "   netmon interfaces"
echo
echo "4. Raporları görüntüleyin:"
echo "   netmon today    # Bugünkü kullanım"
echo "   netmon week     # Haftalık"
echo "   netmon month    # Aylık"
echo
echo "5. Servis durumu:"
echo "   netmon status"
echo "   journalctl -u netmon -f"
echo "   tail -f /var/lib/netmon/netmon.log"
echo
echo "6. Webhook ayarlamak için:"
echo "   sudo netmon webhook set https://api.example.com/netmon 60"
echo
