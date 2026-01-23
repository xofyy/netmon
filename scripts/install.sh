#!/bin/bash
# netmon installer script v2.1.0
# Usage: sudo ./scripts/install.sh [COMMAND] [OPTIONS]

set -euo pipefail

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

VERSION="2.1.1"
SCRIPT_DIR=""
LOG_FILE="/tmp/netmon_install_$(date +%Y%m%d_%H%M%S).log"
TOTAL_STEPS=6
CURRENT_STEP=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Default flags
COMMAND="install"
FORCE=true           # Non-interactive by default
VERBOSE=false
KEEP_DATA=false

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" >> "$LOG_FILE"
    if [ "$VERBOSE" = true ]; then
        echo -e "${CYAN}[LOG]${NC} $message"
    fi
}

print_banner() {
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     netmon Installer v${VERSION}              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo
}

print_step() {
    CURRENT_STEP=$1
    local message="$2"
    echo -e "${YELLOW}[${CURRENT_STEP}/${TOTAL_STEPS}]${NC} ${message}..."
    log "STEP $CURRENT_STEP: $message"
}

print_ok() {
    local message="$1"
    echo -e "${GREEN}✓${NC} ${message}"
    log "OK: $message"
}

print_warn() {
    local message="$1"
    echo -e "${YELLOW}!${NC} ${message}"
    log "WARN: $message"
}

print_error() {
    local message="$1"
    echo -e "${RED}✗${NC} ${message}" >&2
    log "ERROR: $message"
}

print_info() {
    local message="$1"
    echo -e "${BLUE}→${NC} ${message}"
    log "INFO: $message"
}

version_gte() {
    # Returns 0 if $1 >= $2 (version comparison)
    local v1="$1"
    local v2="$2"
    [ "$(printf '%s\n' "$v2" "$v1" | sort -V | head -n1)" = "$v2" ]
}

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo
        print_error "Kurulum başarısız oldu (çıkış kodu: $exit_code)"
        print_error "Log dosyası: $LOG_FILE"
        echo
        echo "Hata ayıklama için:"
        echo "  cat $LOG_FILE"
        echo "  sudo journalctl -xe"
    fi
}

confirm() {
    local message="$1"
    if [ "$FORCE" = true ]; then
        return 0
    fi
    read -p "$message [e/H]: " -n 1 -r
    echo
    [[ $REPLY =~ ^[Ee]$ ]]
}

# ============================================================================
# CLI ARGUMENT PARSER
# ============================================================================

show_help() {
    echo -e "${BOLD}netmon Installer v${VERSION}${NC}"
    echo
    echo -e "${BOLD}Kullanım:${NC}"
    echo "  sudo ./scripts/install.sh [KOMUT] [SEÇENEK]"
    echo
    echo -e "${BOLD}Komutlar:${NC}"
    echo "  install       Yeni kurulum (varsayılan)"
    echo "  uninstall     netmon'u kaldır"
    echo "  upgrade       Mevcut kurulumu güncelle (veriyi koru)"
    echo "  status        Kurulum durumunu kontrol et"
    echo
    echo -e "${BOLD}Seçenekler:${NC}"
    echo "  -h, --help        Bu yardımı göster"
    echo "  -i, --interactive Sorular sor (varsayılan: sessiz mod)"
    echo "  -v, --verbose     Detaylı çıktı"
    echo "  --keep-data       Kaldırırken veri ve yapılandırmayı koru"
    echo "  --version         Installer sürümünü göster"
    echo
    echo -e "${BOLD}Örnekler:${NC}"
    echo "  sudo ./scripts/install.sh              # Sessiz kurulum"
    echo "  sudo ./scripts/install.sh -i           # Etkileşimli kurulum"
    echo "  sudo ./scripts/install.sh upgrade      # Güncelleme"
    echo "  sudo ./scripts/install.sh uninstall    # Kaldırma"
    echo "  sudo ./scripts/install.sh uninstall --keep-data  # Veriyi koruyarak kaldır"
    echo
    echo -e "${BOLD}Dizinler:${NC}"
    echo "  /etc/netmon/          Yapılandırma dosyaları"
    echo "  /var/lib/netmon/      Veritabanı"
    echo "  /var/log/netmon.log   Log dosyası"
    echo
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            install|uninstall|upgrade|status)
                COMMAND="$1"
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            --version)
                echo "netmon installer v${VERSION}"
                exit 0
                ;;
            -i|--interactive)
                FORCE=false
                ;;
            -v|--verbose)
                VERBOSE=true
                ;;
            --keep-data)
                KEEP_DATA=true
                ;;
            *)
                print_error "Bilinmeyen seçenek: $1"
                echo "Yardım için: $0 --help"
                exit 1
                ;;
        esac
        shift
    done
}

# ============================================================================
# CHECK FUNCTIONS
# ============================================================================

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Bu script root olarak çalıştırılmalı!"
        echo "Kullanım: sudo $0"
        exit 1
    fi
    log "Root check passed"
}

get_script_dir() {
    # Get script directory (resolving symlinks)
    SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
    log "Script directory: $SCRIPT_DIR"
    
    # Verify we're in netmon directory
    if [ ! -f "$SCRIPT_DIR/pyproject.toml" ]; then
        print_error "pyproject.toml bulunamadı!"
        print_error "Script'i netmon dizininden çalıştırın: sudo ./scripts/install.sh"
        exit 1
    fi
    
    if [ ! -d "$SCRIPT_DIR/netmon" ]; then
        print_error "netmon/ paketi bulunamadı!"
        exit 1
    fi
    
    print_info "Kurulum dizini: $SCRIPT_DIR"
}

check_existing() {
    if command -v netmon &> /dev/null; then
        local current_version=$(netmon version 2>/dev/null | grep -oP '[\d.]+' || echo "unknown")
        print_warn "Mevcut kurulum tespit edildi: v$current_version"
        log "Existing installation found: v$current_version"
        
        if [ "$COMMAND" = "install" ]; then
            if ! confirm "Yeniden kurmak istiyor musunuz?"; then
                echo "Kurulum iptal edildi."
                exit 0
            fi
            # Stop existing service
            systemctl stop netmon 2>/dev/null || true
        fi
        return 0
    fi
    return 1
}

check_python() {
    print_step 1 "Python kontrol ediliyor"
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 bulunamadı!"
        exit 1
    fi
    
    local python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local required_version="3.10"
    
    if ! version_gte "$python_version" "$required_version"; then
        print_error "Python $required_version veya üstü gerekli!"
        print_error "Mevcut sürüm: $python_version"
        exit 1
    fi
    
    print_ok "Python $python_version"
}

install_deps() {
    print_step 2 "Bağımlılıklar kontrol ediliyor"
    
    local need_update=false
    
    # Check nethogs
    if ! command -v nethogs &> /dev/null; then
        need_update=true
        log "nethogs not found, will install"
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        need_update=true
        log "pip3 not found, will install"
    fi
    
    # Update apt if needed
    if [ "$need_update" = true ]; then
        log "Running apt-get update"
        apt-get update -qq || {
            print_error "apt-get update başarısız"
            exit 1
        }
    fi
    
    # Install nethogs
    if ! command -v nethogs &> /dev/null; then
        print_info "nethogs kuruluyor..."
        apt-get install -y nethogs || {
            print_error "nethogs kurulumu başarısız"
            exit 1
        }
    fi
    print_ok "nethogs kurulu"
    
    # Install pip
    if ! command -v pip3 &> /dev/null; then
        print_info "pip kuruluyor..."
        apt-get install -y python3-pip || {
            print_error "pip kurulumu başarısız"
            exit 1
        }
    fi
    print_ok "pip kurulu"
}

# ============================================================================
# INSTALLATION FUNCTIONS
# ============================================================================

create_dirs() {
    print_step 3 "Dizinler oluşturuluyor"
    
    mkdir -p /etc/netmon
    mkdir -p /var/lib/netmon
    mkdir -p /var/log
    
    # Set permissions
    chmod 755 /etc/netmon
    chmod 755 /var/lib/netmon
    
    log "Directories created"
    print_ok "Dizinler oluşturuldu"
}

install_package() {
    print_step 4 "netmon paketi kuruluyor"
    
    log "Running pip install -e $SCRIPT_DIR"
    
    if ! pip3 install -e "$SCRIPT_DIR" 2>&1 | tee -a "$LOG_FILE"; then
        print_error "pip install başarısız!"
        print_error "Detaylar için: cat $LOG_FILE"
        exit 1
    fi
    
    # Verify installation
    print_info "Kurulum doğrulanıyor..."
    
    if ! python3 -c "import netmon; print(f'netmon v{netmon.__version__}')" 2>/dev/null; then
        print_error "netmon modülü yüklenemedi!"
        print_error "Manuel kurulum deneyin: cd $SCRIPT_DIR && sudo pip install -e ."
        exit 1
    fi
    
    # Verify CLI works
    if ! netmon version &>/dev/null; then
        print_error "netmon CLI çalışmıyor!"
        exit 1
    fi
    
    local installed_version=$(netmon version 2>/dev/null | grep -oP '[\d.]+' || echo "unknown")
    print_ok "Paket kuruldu ve doğrulandı (v$installed_version)"
}

backup_config() {
    if [ -f /etc/netmon/config.yaml ]; then
        local backup_file="/etc/netmon/config.yaml.bak.$(date +%Y%m%d_%H%M%S)"
        cp /etc/netmon/config.yaml "$backup_file"
        log "Config backed up to $backup_file"
        print_ok "Mevcut yapılandırma yedeklendi: $backup_file"
    fi
}

setup_config() {
    print_step 5 "Yapılandırma dosyası oluşturuluyor"
    
    if [ -f /etc/netmon/config.yaml ]; then
        print_warn "Mevcut yapılandırma korundu"
    elif [ -f "$SCRIPT_DIR/config.default.yaml" ]; then
        cp "$SCRIPT_DIR/config.default.yaml" /etc/netmon/config.yaml
        chmod 644 /etc/netmon/config.yaml
        print_ok "Varsayılan yapılandırma oluşturuldu"
    else
        print_warn "config.default.yaml bulunamadı, atlanıyor"
    fi
}

setup_systemd() {
    print_step 6 "Systemd servisi kuruluyor"
    
    if [ -f "$SCRIPT_DIR/systemd/netmon.service" ]; then
        cp "$SCRIPT_DIR/systemd/netmon.service" /etc/systemd/system/
        log "Copied service file from $SCRIPT_DIR/systemd/netmon.service"
    else
        # Create service file inline as fallback
        log "Creating service file inline (fallback)"
        cat > /etc/systemd/system/netmon.service << 'EOF'
[Unit]
Description=netmon - Application-based Network Traffic Monitor
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/netmon start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    fi
    
    chmod 644 /etc/systemd/system/netmon.service
    
    # Reload systemd
    systemctl daemon-reload
    log "systemd daemon reloaded"
    
    # Enable service
    systemctl enable netmon 2>/dev/null
    log "netmon service enabled"
    
    print_ok "Systemd servisi kuruldu"
}

start_service() {
    print_info "Servis başlatılıyor..."
    
    if systemctl start netmon; then
        sleep 2
        if systemctl is-active --quiet netmon; then
            print_ok "Servis başlatıldı ve çalışıyor"
            log "Service started successfully"
        else
            print_warn "Servis başlatıldı ama durumu kontrol edin"
            print_warn "Komut: systemctl status netmon"
        fi
    else
        print_warn "Servis başlatılamadı"
        print_warn "Manuel deneyin: sudo systemctl start netmon"
        log "Service failed to start"
    fi
}

# ============================================================================
# MAIN COMMANDS
# ============================================================================

do_install() {
    print_banner
    
    check_existing || true
    
    check_python
    install_deps
    create_dirs
    install_package
    setup_config
    setup_systemd
    start_service
    
    echo
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     Kurulum Tamamlandı!                    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo
    echo "Komutlar:"
    echo "  sudo systemctl status netmon   # Servis durumu"
    echo "  netmon status                  # netmon durumu"
    echo "  netmon today                   # Bugünkü rapor"
    echo "  sudo netmon -f                 # Canlı izleme"
    echo "  netmon --help                  # Yardım"
    echo
    echo -e "${CYAN}Log dosyası:${NC} $LOG_FILE"
    echo
}

do_upgrade() {
    print_banner
    echo -e "${BLUE}Upgrade modu: Veri ve yapılandırma korunacak${NC}"
    echo
    
    if ! command -v netmon &> /dev/null; then
        print_error "netmon kurulu değil! Önce kurulum yapın."
        exit 1
    fi
    
    local current_version=$(netmon version 2>/dev/null | grep -oP '[\d.]+' || echo "unknown")
    print_info "Mevcut sürüm: v$current_version"
    
    # Stop service
    print_info "Servis durduruluyor..."
    systemctl stop netmon 2>/dev/null || true
    
    # Backup config
    backup_config
    
    # Reinstall package
    print_step 1 "Paket güncelleniyor"
    TOTAL_STEPS=3
    
    if ! pip3 install -e "$SCRIPT_DIR" --upgrade 2>&1 | tee -a "$LOG_FILE"; then
        print_error "Güncelleme başarısız!"
        exit 1
    fi
    
    local new_version=$(netmon version 2>/dev/null | grep -oP '[\d.]+' || echo "unknown")
    print_ok "Paket güncellendi: v$current_version → v$new_version"
    
    # Update systemd if needed
    print_step 2 "Servis dosyası güncelleniyor"
    if [ -f "$SCRIPT_DIR/systemd/netmon.service" ]; then
        cp "$SCRIPT_DIR/systemd/netmon.service" /etc/systemd/system/
        systemctl daemon-reload
    fi
    print_ok "Servis dosyası güncellendi"
    
    # Restart service
    print_step 3 "Servis başlatılıyor"
    start_service
    
    echo
    echo -e "${GREEN}Güncelleme tamamlandı!${NC}"
    echo
}

do_uninstall() {
    print_banner
    echo -e "${RED}netmon kaldırılıyor...${NC}"
    echo
    
    if ! confirm "netmon'u kaldırmak istediğinizden emin misiniz?"; then
        echo "İşlem iptal edildi."
        exit 0
    fi
    
    # Stop and disable service
    print_info "Servis durduruluyor..."
    systemctl stop netmon 2>/dev/null || true
    systemctl disable netmon 2>/dev/null || true
    log "Service stopped and disabled"
    
    # Remove service file
    rm -f /etc/systemd/system/netmon.service
    systemctl daemon-reload
    print_ok "Systemd servisi kaldırıldı"
    
    # Uninstall Python package
    print_info "Python paketi kaldırılıyor..."
    pip3 uninstall -y netmon 2>/dev/null || true
    print_ok "Python paketi kaldırıldı"
    
    # Handle data
    if [ "$KEEP_DATA" = true ]; then
        print_warn "Veri ve yapılandırma korundu:"
        print_warn "  /etc/netmon/"
        print_warn "  /var/lib/netmon/"
    else
        if confirm "Veritabanı ve yapılandırmayı da silmek istiyor musunuz?"; then
            rm -rf /etc/netmon
            rm -rf /var/lib/netmon
            print_ok "Veri ve yapılandırma silindi"
            log "Data and config removed"
        else
            print_warn "Veri ve yapılandırma korundu"
        fi
    fi
    
    echo
    echo -e "${GREEN}netmon başarıyla kaldırıldı.${NC}"
    echo
}

do_status() {
    echo -e "${BOLD}netmon Kurulum Durumu${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    
    # Check if installed
    if command -v netmon &> /dev/null; then
        local version=$(netmon version 2>/dev/null | grep -oP '[\d.]+' || echo "unknown")
        echo -e "Paket:        ${GREEN}Kurulu${NC} (v$version)"
    else
        echo -e "Paket:        ${RED}Kurulu değil${NC}"
    fi
    
    # Check service
    if systemctl is-active --quiet netmon 2>/dev/null; then
        echo -e "Servis:       ${GREEN}Çalışıyor${NC}"
    elif systemctl is-enabled --quiet netmon 2>/dev/null; then
        echo -e "Servis:       ${YELLOW}Durdurulmuş (enabled)${NC}"
    else
        echo -e "Servis:       ${RED}Yok/Disabled${NC}"
    fi
    
    # Check config
    if [ -f /etc/netmon/config.yaml ]; then
        echo -e "Yapılandırma: ${GREEN}Mevcut${NC}"
    else
        echo -e "Yapılandırma: ${RED}Yok${NC}"
    fi
    
    # Check database
    if [ -f /var/lib/netmon/traffic.db ]; then
        local db_size=$(du -h /var/lib/netmon/traffic.db 2>/dev/null | cut -f1)
        echo -e "Veritabanı:   ${GREEN}Mevcut${NC} ($db_size)"
    else
        echo -e "Veritabanı:   ${YELLOW}Yok${NC}"
    fi
    
    # Check nethogs
    if command -v nethogs &> /dev/null; then
        echo -e "nethogs:      ${GREEN}Kurulu${NC}"
    else
        echo -e "nethogs:      ${RED}Kurulu değil${NC}"
    fi
    
    echo
}

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

main() {
    # Setup error trap
    trap cleanup EXIT
    
    # Parse command line arguments
    parse_args "$@"
    
    # Initialize log
    echo "=== netmon installer v${VERSION} ===" > "$LOG_FILE"
    echo "Date: $(date)" >> "$LOG_FILE"
    echo "Command: $COMMAND" >> "$LOG_FILE"
    echo "Args: $*" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    
    # Check root for commands that need it
    if [ "$COMMAND" != "status" ] && [ "$COMMAND" != "help" ]; then
        check_root
    fi
    
    # Get script directory
    get_script_dir
    
    # Dispatch command
    case "$COMMAND" in
        install)
            do_install
            ;;
        uninstall)
            do_uninstall
            ;;
        upgrade)
            do_upgrade
            ;;
        status)
            do_status
            ;;
        *)
            print_error "Bilinmeyen komut: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# Run main
main "$@"
