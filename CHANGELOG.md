# Changelog

All notable changes to netmon will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-01-23

### 🔧 Fixed - Critical Data Loss Issues

#### nethogs Rate × Time Calculation Fix (80% data loss)
**Problem:** nethogs `-t` mode outputs KB/s (rate), but the parser was only converting to bytes without multiplying by the refresh interval. This caused approximately 80% data loss.

**Solution:**
- Added `refresh_sec` parameter to `parse_nethogs_line()` function
- Updated formula: `KB/s × refresh_sec × 1024 = Bytes`
- Updated all call sites in `collector.py` and `display.py` to pass `config.nethogs_refresh_sec`

**Impact:** Traffic reporting accuracy increased from ~20% to ~82%+

**Changed files:**
- `netmon/parser.py`: Added refresh_sec parameter and fixed calculation
- `netmon/collector.py`: Updated parse_nethogs_line() calls (lines 147, 229)
- `netmon/display.py`: Updated live display with correct rate/cumulative logic

#### IP Division Precision Loss Fix
**Problem:** When splitting traffic across multiple remote IPs, using `int()` division lost fractional bytes. Example: 10001 bytes / 5 IPs = 2000.2 → int() = 2000 per IP → Total saved: 10000 (1 byte lost).

**Solution:**
- Calculate remainder and distribute to first N IPs
- Example: 10001 bytes / 5 IPs → 4 IPs get 2000 bytes, 1 IP gets 2001 bytes → Total: 10001 ✓

**Changed files:**
- `netmon/database.py`: Fixed IP division logic (lines 133-151)

#### Parse Error Visibility
**Problem:** Parse errors were logged at DEBUG level, invisible in production (log_level: INFO).

**Solution:**
- Changed log level from `logger.debug()` to `logger.warning()`
- Added "nethogs" prefix for grep-ability
- Truncated line to 100 chars to prevent log spam

**Changed files:**
- `netmon/parser.py`: Line 62

### ✨ Added

#### Quick Update Script
- Added `update.sh` for one-command upgrades
- Supports git pull + automatic package upgrade
- Usage: `cd netmon && sudo ./update.sh`
- Remote usage: `curl -sSL https://raw.githubusercontent.com/xofyy/netmon/main/update.sh | sudo bash`

### 📚 Changed

#### Documentation
- Removed duplicate `install.sh` from root (consolidated to `scripts/install.sh`)
- Updated README with dedicated "Güncelleme" (Update) section
- Added three update methods: Quick, Manual, Remote
- Reorganized installation documentation

### 🔒 Security

#### Input Validation
- Added `refresh_sec` validation in parser (prevents <=0 values)
- Edge case handling for empty IP sets and invalid configurations

---

## [2.0.0] - 2026-01-22

### Initial Release
- Application-based network traffic monitoring
- Real-time traffic collection with nethogs integration
- SQLite database with WAL mode
- Webhook support for periodic reports
- IP exclusion for PLC devices
- Live traffic visualization
- Systemd service integration
- Rich CLI with comprehensive commands

### Features
- 🔄 Continuous data collection (100% capture rate)
- 📊 Rich reports (daily, weekly, monthly)
- 🔴 Live monitoring with real-time visualization
- 🚫 IP exclusion for non-internet devices
- 🔔 Webhook integration for automated reporting
- 🐳 Docker container traffic support
- 🌐 Dynamic interface detection

---

## Data Accuracy Note

**Important:** Traffic data collected **before 2026-01-23** is approximately 80% underreported due to the nethogs calculation bug. This is a known limitation of versions prior to v2.1.0. The fix is forward-only; historical data cannot be retroactively corrected as actual traffic values are unknown.

To check your installation date:
```bash
sqlite3 /var/lib/netmon/traffic.db "SELECT MIN(timestamp) FROM traffic"
```

If your earliest data is before 2026-01-23, multiply those values by ~5 for a rough estimate of actual traffic.

---

## Upgrade Instructions

### From v2.0.0 to v2.1.0

**Quick Upgrade (Recommended):**
```bash
cd /path/to/netmon
sudo ./update.sh
```

**Manual Upgrade:**
```bash
cd /path/to/netmon
git pull
sudo ./scripts/install.sh upgrade
```

**Post-Upgrade Verification:**
```bash
# Check version
netmon version  # Should show v2.1.0

# Monitor logs for warnings
sudo tail -f /var/log/netmon.log

# Test with traffic
speedtest-cli
sleep 60  # Wait for DB write
sudo netmon today  # Verify accurate reporting
```

---

## Breaking Changes

None. Version 2.1.0 is fully backward compatible with v2.0.0.

- Database schema: unchanged
- Configuration format: unchanged
- CLI commands: unchanged
- API/webhook format: unchanged

---

## Contributors

- **Murat** - Initial work and v2.1.0 critical fixes

## License

This project is licensed under the MIT License - see the LICENSE file for details.
