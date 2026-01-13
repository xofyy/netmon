# netmon

Uygulama bazlı network trafik izleyici. PLC ve diğer cihazları hariç tutarak internet kullanımını takip eder.

## Özellikler

- 🔄 **Sürekli veri toplama** - Veri kaybı olmadan %100 trafik yakalama
- 📊 **Zengin raporlar** - Günlük, haftalık, aylık trafik raporları
- 🔴 **Canlı izleme** - Anlık trafik görselleştirme
- 🚫 **IP hariç tutma** - PLC ve yerel cihazları filtrele
- 🔔 **Webhook entegrasyonu** - Periyodik rapor gönderimi
- 🐳 **Docker desteği** - Docker container trafiğini izleme
- 🌐 **Dinamik interface** - Otomatik interface tespiti

## Gereksinimler

- Ubuntu 22.04 LTS veya üstü
- Python 3.10+
- nethogs

## Kurulum

```bash
# Depoyu klonla
git clone https://github.com/xofyy/netmon.git
cd netmon

# Kurulum scriptini çalıştır
sudo ./scripts/install.sh
```

Veya manuel kurulum:

```bash
# nethogs kur
sudo apt install nethogs

# Python paketini kur
sudo pip install -e .

# Servisi başlat
sudo systemctl start netmon
sudo systemctl enable netmon
```

## Kullanım

### Servis Kontrolü

```bash
# Daemon başlat
sudo netmon start --daemon

# Durumu kontrol et
netmon status

# Daemon durdur
sudo netmon stop
```

### Raporlar

```bash
# Bugünkü kullanım
netmon today

# Son 7 gün
netmon week

# Son 30 gün  
netmon month

# En çok kullanan 10 uygulama
netmon top 10
```

### Canlı İzleme

```bash
# Anlık trafik görselleştirme
sudo netmon -f

# veya
sudo netmon live
```

### IP Hariç Tutma

```bash
# IP ekle
sudo netmon exclude add 192.168.1.100 "PLC Ana"

# IP kaldır
sudo netmon exclude remove 192.168.1.100

# Listeyi göster
netmon exclude list
```

### Webhook

```bash
# Webhook ayarla (60 dakikada bir gönder)
sudo netmon webhook set https://api.example.com/netmon 60

# Durumu göster
netmon webhook status

# Test gönderimi
netmon webhook test

# Devre dışı bırak
sudo netmon webhook disable
```

### Yapılandırma

```bash
# Yapılandırmayı göster
netmon config show

# DB yazma aralığını değiştir (dakika)
sudo netmon config set db_write_interval 600

# Interface listele
netmon interfaces
```

### Bakım

```bash
# Geçersiz uygulama adlarını düzelt
netmon cleanup

# Tespit edilemeyen trafik detayı
netmon unknown 7
```

## Yapılandırma Dosyası

Konum: `/etc/netmon/config.yaml`

```yaml
# Network interfaces (boş = otomatik tespit)
interfaces: []

# DB yazma aralığı (saniye)
db_write_interval: 300

# Veri saklama süresi (gün)
data_retention_days: 90

# Log seviyesi
log_level: INFO
```

## Webhook JSON Formatı

```json
{
  "version": "2.0",
  "hostname": "server-01",
  "timestamp": "2026-01-13T15:30:00+00:00",
  "report_period": "daily",
  "summary": {
    "total_bytes": 1073741824,
    "total_formatted": "1.00 GB",
    "application_count": 15
  },
  "applications": [
    {
      "name": "firefox",
      "bytes_total": 536870912,
      "total_formatted": "512.00 MB",
      "percentage": 50.0
    }
  ],
  "excluded_ips": [
    {"ip": "5.5.5.100", "description": "PLC 1"}
  ]
}
```

## Systemd

```bash
# Servis durumu
sudo systemctl status netmon

# Logları görüntüle
sudo journalctl -u netmon -f

# Servisi yeniden başlat
sudo systemctl restart netmon
```

## Dosya Konumları

| Dosya | Konum |
|-------|-------|
| Yapılandırma | `/etc/netmon/config.yaml` |
| Veritabanı | `/var/lib/netmon/traffic.db` |
| Log dosyası | `/var/log/netmon.log` |
| PID dosyası | `/var/run/netmon.pid` |

## Geliştirme

```bash
# Geliştirme modunda kur
pip install -e .

# Test modunda çalıştır
sudo netmon test 60
```

## Lisans

MIT
