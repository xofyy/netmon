#!/bin/bash
# netmon installer script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     netmon Installer v2.0              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Bu script root olarak çalıştırılmalı!${NC}"
    echo "Kullanım: sudo ./scripts/install.sh"
    exit 1
fi

# Get script directory (resolving symlinks)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
echo -e "${YELLOW}Kurulum dizini:${NC} $SCRIPT_DIR"

# Verify netmon package exists
if [ ! -f "$SCRIPT_DIR/pyproject.toml" ]; then
    echo -e "${RED}Hata: pyproject.toml bulunamadı!${NC}"
    echo "Script'i netmon dizininden çalıştırın: sudo ./scripts/install.sh"
    exit 1
fi

if [ ! -d "$SCRIPT_DIR/netmon" ]; then
    echo -e "${RED}Hata: netmon/ paketi bulunamadı!${NC}"
    exit 1
fi

echo

# Check Python version
echo -e "${YELLOW}[1/6]${NC} Python kontrol ediliyor..."
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Python $REQUIRED_VERSION veya üstü gerekli!${NC}"
    echo "Mevcut sürüm: $PYTHON_VERSION"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"

# Check/install nethogs
echo -e "${YELLOW}[2/6]${NC} Bağımlılıklar kontrol ediliyor..."

if ! command -v nethogs &> /dev/null; then
    echo "nethogs kuruluyor..."
    apt-get update -qq
    apt-get install -y nethogs
fi
echo -e "${GREEN}✓${NC} nethogs kurulu"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "pip kuruluyor..."
    apt-get install -y python3-pip
fi
echo -e "${GREEN}✓${NC} pip kurulu"

# Create directories
echo -e "${YELLOW}[3/6]${NC} Dizinler oluşturuluyor..."

mkdir -p /etc/netmon
mkdir -p /var/lib/netmon
mkdir -p /var/log

echo -e "${GREEN}✓${NC} Dizinler oluşturuldu"

# Install Python package
echo -e "${YELLOW}[4/6]${NC} netmon paketi kuruluyor..."

if ! pip3 install -e "$SCRIPT_DIR" 2>&1; then
    echo -e "${RED}Hata: pip install başarısız!${NC}"
    exit 1
fi

# Verify installation
echo "Kurulum doğrulanıyor..."
if ! python3 -c "import netmon; print(f'netmon v{netmon.__version__}')" 2>/dev/null; then
    echo -e "${RED}Hata: netmon modülü yüklenemedi!${NC}"
    echo "Manuel kurulum deneyin: cd $SCRIPT_DIR && sudo pip install -e ."
    exit 1
fi

# Verify CLI works
if ! netmon version &>/dev/null; then
    echo -e "${RED}Hata: netmon CLI çalışmıyor!${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Paket kuruldu ve doğrulandı"

# Copy config
echo -e "${YELLOW}[5/6]${NC} Yapılandırma dosyası oluşturuluyor..."

if [ ! -f /etc/netmon/config.yaml ]; then
    if [ -f "$SCRIPT_DIR/config.default.yaml" ]; then
        cp "$SCRIPT_DIR/config.default.yaml" /etc/netmon/config.yaml
        echo -e "${GREEN}✓${NC} Varsayılan yapılandırma oluşturuldu"
    else
        echo -e "${YELLOW}!${NC} config.default.yaml bulunamadı, atlanıyor"
    fi
else
    echo -e "${YELLOW}!${NC} Mevcut yapılandırma korundu"
fi

# Setup systemd service
echo -e "${YELLOW}[6/6]${NC} Systemd servisi kuruluyor..."

if [ -f "$SCRIPT_DIR/systemd/netmon.service" ]; then
    cp "$SCRIPT_DIR/systemd/netmon.service" /etc/systemd/system/
else
    # Create service file if not exists
    cat > /etc/systemd/system/netmon.service << EOF
[Unit]
Description=netmon - Application-based Network Traffic Monitor
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/netmon start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi

# Reload and enable
systemctl daemon-reload
systemctl enable netmon

# Start service
echo "Servis başlatılıyor..."
if systemctl start netmon; then
    sleep 2
    if systemctl is-active --quiet netmon; then
        echo -e "${GREEN}✓${NC} Servis başlatıldı"
    else
        echo -e "${YELLOW}!${NC} Servis başlatıldı ama durumu kontrol edin: systemctl status netmon"
    fi
else
    echo -e "${YELLOW}!${NC} Servis başlatılamadı. Manuel deneyin: sudo systemctl start netmon"
fi

echo
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Kurulum Tamamlandı!                ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo
echo "Komutlar:"
echo "  sudo systemctl status netmon   # Servis durumu"
echo "  netmon status                  # netmon durumu"
echo "  netmon today                   # Bugünkü rapor"
echo "  sudo netmon -f                 # Canlı izleme"
echo "  netmon --help                  # Yardım"
echo
