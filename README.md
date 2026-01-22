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

### Hızlı Kurulum

```bash
# Depoyu klonla
git clone https://github.com/xofyy/netmon.git
cd netmon

# Kurulum scriptini çalıştır (sessiz mod)
sudo ./scripts/install.sh
```

### Installer Komutları

```bash
# Yeni kurulum (sessiz mod)
sudo ./scripts/install.sh

# Etkileşimli kurulum (sorular sorar)
sudo ./scripts/install.sh -i

# Kurulum durumu
./scripts/install.sh status

# Yardım
./scripts/install.sh --help
```

### Güncelleme

**🚀 Tek Komutla Hızlı Güncelleme (Önerilen):**

```bash
# Mevcut kurulumu güncelle
cd netmon
sudo ./update.sh
```

**Manuel Güncelleme:**

```bash
# Git ile en son kodu çek ve güncelle
cd netmon
git pull
sudo ./scripts/install.sh upgrade
```

**Uzaktan Güncelleme (SSH):**

```bash
# GitHub'dan direkt çalıştır
curl -sSL https://raw.githubusercontent.com/xofyy/netmon/main/update.sh | sudo bash
```

> **Not:** `upgrade` komutu mevcut yapılandırma ve veritabanını korur.

### Kaldırma

```bash
# Tamamen kaldır
sudo ./scripts/install.sh uninstall

# Veri ve yapılandırmayı koruyarak kaldır
sudo ./scripts/install.sh uninstall --keep-data
```

### Manuel Kurulum

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

## ⚠️ Veri Doğruluğu Notu

**Önemli:** **23 Ocak 2026 öncesi** toplanan trafik verileri, nethogs hesaplama hatasından dolayı yaklaşık **%80 eksik** kaydedilmiştir. Bu durum v2.1.0 öncesi sürümlerin bilinen bir kısıtlamasıdır.

### Düzeltme Detayları

**v2.1.0'da Düzeltilen Sorunlar:**
- nethogs rate × süre çarpımı eksikliği (%80 veri kaybı) ✅ DÜZELTİLDİ
- IP bölünmesinde ondalık kayıplar ✅ DÜZELTİLDİ
- Parse hatalarının görünürlüğü ✅ İYİLEŞTİRİLDİ

**Etki:**
- v2.0.0 ve öncesi: ~%20 doğruluk
- v2.1.0 ve sonrası: ~%82+ doğruluk

### Kurulum Tarihinizi Kontrol Edin

```bash
# İlk veri tarihi
sqlite3 /var/lib/netmon/traffic.db \
  "SELECT MIN(timestamp) as ilk_kayit FROM traffic"

# Güncelleme öncesi vs sonrası karşılaştırma
sqlite3 /var/lib/netmon/traffic.db \
  "SELECT
     DATE(timestamp) as tarih,
     ROUND(SUM(bytes_sent + bytes_recv)/1024.0/1024.0, 2) as toplam_mb
   FROM traffic
   WHERE timestamp > DATE('now', '-7 days')
   GROUP BY DATE(timestamp)"
```

**Not:** Geçmiş veriler gerçek değerleriyle değiştirilemez. 23 Ocak 2026 öncesi veriler için yaklaşık tahmin elde etmek isterseniz değerleri **×5 ile çarpabilirsiniz** (yalnızca tahmin içindir).

## Lisans

MIT
