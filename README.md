# netmon - Uygulama Bazlı Network Trafik İzleyici

PLC ve diğer yerel cihazları hariç tutarak, internet kullanımını uygulama bazında izler ve raporlar.

## Özellikler

- ✅ **Sürekli veri toplama** - %100 trafik yakalama
- ✅ Uygulama bazlı trafik izleme
- ✅ **Çoklu interface desteği** (ethernet, docker, tailscale, wifi)
- ✅ **Dinamik interface tespiti**
- ✅ PLC/cihaz IP'lerini hariç tutma (IP validation ile)
- ✅ Günlük, haftalık, aylık raporlar
- ✅ **Webhook desteği** - Uzak sunucuya rapor gönderme
- ✅ **JSON config dosyası** ile yapılandırma
- ✅ Hafif ve minimal kaynak kullanımı
- ✅ Systemd entegrasyonu
- ✅ **Graceful shutdown** - Veri kaybı yok

## Kurulum

```bash
# Scripti indir
git clone ... veya dosyaları kopyala

# Kurulumu çalıştır
cd netmon
sudo ./install.sh
```

## Kullanım

### Servis Yönetimi

```bash
# Başlat
sudo systemctl start netmon

# Durdur
sudo systemctl stop netmon

# Durum
netmon status
# veya
systemctl status netmon

# Loglar
journalctl -u netmon -f
# veya
tail -f /var/lib/netmon/netmon.log
```

### Raporlar

```bash
# Bugünkü kullanım
netmon today

# Son 7 gün
netmon week

# Son 30 gün
netmon month

# En çok kullanan uygulamalar
netmon top 10
```

### Unknown Trafik Analizi

Bazı trafik kaynaklarını nethogs tespit edemeyebilir (kernel trafiği, kısa ömürlü bağlantılar vb.). Bu trafiği analiz etmek için:

```bash
# Son 7 günün unknown trafiğini göster
netmon unknown

# Son 30 günün unknown trafiğini göster
netmon unknown 30
```

Çıktı, unknown trafiğin hangi IP adreslerine gittiğini gösterir. Bilinen cihazları (PLC, yazıcı vb.) `exclude` listesine ekleyebilirsiniz.

### Veritabanı Bakımı

Eski sürümlerden kalan hatalı kayıtları düzeltmek için:

```bash
# Geçersiz uygulama adlarını (PID, IP:port) düzelt
netmon cleanup
```

### PLC/Cihaz IP'lerini Hariç Tutma

```bash
# IP ekle (IP validation ile)
sudo netmon exclude add 192.168.1.50 "PLC1 Torna"
sudo netmon exclude add 192.168.1.51 "PLC2 Freze"
sudo netmon exclude add 5.5.5.10 "Ana PLC"

# Listeyi görüntüle
netmon exclude list

# IP kaldır
sudo netmon exclude remove 192.168.1.50
```

### Webhook Yapılandırması

```bash
# Webhook ayarla (60 dakikada bir gönderim)
sudo netmon webhook set https://api.example.com/netmon 60

# Durumu görüntüle
netmon webhook status

# Test gönderimi
netmon webhook test

# Gönderilecek JSON'u görüntüle
netmon webhook payload

# Webhook'u devre dışı bırak/etkinleştir
sudo netmon webhook disable
sudo netmon webhook enable

# Webhook'u kaldır
sudo netmon webhook remove
```

### Yapılandırma

```bash
# Aktif interface'leri göster
netmon interfaces

# DB yazma aralığını göster
netmon interval

# DB yazma aralığını değiştir (dakika cinsinden)
sudo netmon interval set 10

# Tüm yapılandırmayı göster
netmon config show
```

## Örnek Çıktı

```
══════════════════════════════════════════════════════════════════════
  SON 7 GÜNLÜK KULLANIM
  Toplam: 12.45 GB
══════════════════════════════════════════════════════════════════════

Uygulama                  Gönderim     Alım         Toplam       %     
──────────────────────────────────────────────────────────────────────
firefox                   1.23 GB      4.56 GB      5.79 GB      46.5% █████████
apt                       12.34 MB     2.10 GB      2.11 GB      17.0% ███
docker                    456.78 MB    1.23 GB      1.69 GB      13.6% ██
code                      89.12 MB     892.34 MB    981.46 MB     7.7% █
ssh                       123.45 MB    234.56 MB    358.01 MB     2.8% 
```

## Yapılandırma Dosyası

Config dosyası: `/etc/netmon/config.json`

```json
{
  "interfaces": [],
  "db_write_interval": 300,
  "data_retention_days": 90,
  "log_level": "INFO"
}
```

| Parametre | Varsayılan | Açıklama |
|-----------|------------|----------|
| `interfaces` | `[]` (otomatik) | İzlenecek network interface listesi |
| `db_write_interval` | `300` (5 dk) | Buffer'dan DB'ye yazma aralığı (saniye) |
| `data_retention_days` | `90` | Eski verilerin tutulma süresi (gün) |
| `log_level` | `INFO` | Log detay seviyesi (DEBUG, INFO, WARNING, ERROR) |

## Mimari

netmon sürekli veri toplama modeli kullanır:

1. **nethogs** sürekli çalışır ve tüm network trafiğini izler
2. **Reader Thread** nethogs çıktısını sürekli okur ve RAM buffer'a yazar
3. **Writer Thread** periyodik olarak (varsayılan 5 dk) buffer'ı SQLite'a yazar
4. **Webhook Thread** yapılandırılmış aralıklarla rapor gönderir

Bu mimari sayesinde **%100 trafik yakalanır**, veri kaybı olmaz.

## Desteklenen Interface'ler

Otomatik tespit edilen interface türleri:
- `eth*`, `enp*`, `ens*`, `eno*` - Ethernet
- `wlan*`, `wlp*` - WiFi
- `docker0` - Docker ana bridge
- `tailscale*` - Tailscale VPN

Hariç tutulan:
- `lo` - Loopback
- `veth*` - Docker container virtual interfaces
- `br-*` - Docker bridge networks
- `virbr*` - Libvirt bridges

## Veritabanı

Veriler SQLite'da saklanır:
- Konum: `/var/lib/netmon/traffic.db`
- Tablo: `traffic` (uygulama, remote_ip, bytes_sent, bytes_recv)
- Tablo: `excluded_ips` (hariç tutulan IP'ler)
- Tablo: `webhook_config` (webhook ayarları)
- Tablo: `webhook_logs` (gönderim logları)

WAL (Write-Ahead Logging) modu ile concurrent erişim desteklenir.

## Gereksinimler

- Python 3.8+
- nethogs
- SQLite3 (Python ile birlikte gelir)

## Log Dosyası

Log dosyası: `/var/lib/netmon/netmon.log`

```bash
# Logları takip et
tail -f /var/lib/netmon/netmon.log

# Son 100 satır
tail -100 /var/lib/netmon/netmon.log
```

## Kaldırma

```bash
sudo systemctl stop netmon
sudo systemctl disable netmon
sudo rm /etc/systemd/system/netmon.service
sudo rm /usr/local/bin/netmon
sudo rm -rf /var/lib/netmon
sudo rm -rf /etc/netmon
sudo systemctl daemon-reload
```
