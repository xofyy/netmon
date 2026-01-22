#!/bin/bash
# netmon Quick Update Script
# Usage: curl -sSL https://raw.githubusercontent.com/xofyy/netmon/main/update.sh | sudo bash
#    Or: sudo ./update.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     netmon Quick Update                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo

# Root check
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}✗${NC} Bu script root olarak çalıştırılmalı!"
    echo "Kullanım: sudo $0"
    exit 1
fi

# Check if netmon is installed
if ! command -v netmon &> /dev/null; then
    echo -e "${RED}✗${NC} netmon kurulu değil!"
    echo -e "${YELLOW}→${NC} İlk kurulum için: sudo ./scripts/install.sh"
    exit 1
fi

CURRENT_VERSION=$(netmon version 2>/dev/null | grep -oP '[\d.]+' || echo "unknown")
echo -e "${BLUE}→${NC} Mevcut sürüm: v${CURRENT_VERSION}"

# Determine update method
if [ -d ".git" ]; then
    # Git repo exists - use git pull
    echo -e "${BLUE}→${NC} Git repo tespit edildi, güncelleme çekiliyor..."

    # Stash local changes if any
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}!${NC} Yerel değişiklikler stash'leniyor..."
        git stash
        STASHED=true
    fi

    # Pull latest
    git pull origin main || git pull origin master || {
        echo -e "${RED}✗${NC} Git pull başarısız!"
        exit 1
    }

    # Restore stash if needed
    if [ "${STASHED:-false}" = true ]; then
        git stash pop || true
    fi

    echo -e "${GREEN}✓${NC} Kod güncellendi"
else
    echo -e "${YELLOW}!${NC} Git repo bulunamadı, mevcut dosyalar kullanılıyor"
fi

# Run installer upgrade
if [ -f "scripts/install.sh" ]; then
    echo -e "${BLUE}→${NC} Paket güncelleniyor..."
    ./scripts/install.sh upgrade
else
    echo -e "${RED}✗${NC} scripts/install.sh bulunamadı!"
    exit 1
fi

NEW_VERSION=$(netmon version 2>/dev/null | grep -oP '[\d.]+' || echo "unknown")

echo
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Güncelleme Tamamlandı!                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo
echo -e "${BLUE}→${NC} Sürüm: v${CURRENT_VERSION} → v${NEW_VERSION}"
echo
echo "Servis durumu kontrol edin:"
echo "  sudo systemctl status netmon"
echo "  netmon status"
echo
