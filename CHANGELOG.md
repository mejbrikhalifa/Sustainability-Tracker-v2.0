# Changelog

All notable changes to the Sustainability Tracker project.

---

## [2.0.0] - 2025-10-08

### 🎉 Major Release - Advanced Features

#### Added

**⚡ Electricity Breakdown by Source**
- 38 global regions with real grid mix data
- Interactive pie + stacked bar charts (Altair)
- Real-time metrics: implied intensity, factor in use, electricity share
- Chart download buttons (PNG export with altair_saver)
- Region-specific electricity factor calculations
- Automatic cache for performance (`@st.cache_data`)
- Metadata display (source, version, URL)

**🏠 Smart Home Energy Estimator**
- 50+ device presets organized in 12 categories
- Seasonal adjustments for climate devices (Summer/Winter/Spring/Autumn)
- 3 quick household profiles (Small Apartment, Family Home, High-Tech Home)
- Enhanced device browser with category expanders
- Device statistics (count, total power)
- One-click apply to electricity input
- CSV import/export for device configurations
- Period scaling (Daily/Monthly/Yearly)

**⏱️ Hourly/Seasonal Carbon Intensity**
- 8 enhanced profiles (seasonal + region-specific)
- Region-aware profile auto-detection (solar/wind/coal-heavy)
- Color-coded gradient visualization (green→yellow→red)
- What-if load shifting tool
- 💰 Annual savings calculator with cost projections
- 📊 Multi-task comparison tool
- Best hours suggestion (top 3 lowest-intensity)
- Chart download capability

**🎨 UI Polish**
- Enhanced header with feature highlights
- Quick action buttons in sidebar (Reset Today, Copy Total)
- 4-column metrics layout (Today, Yesterday, Change %, Streak)
- Better tooltips on all inputs
- Improved button labels with emojis
- Success messages with next-step guidance
- Enhanced help text throughout

#### Changed
- Default region now "EU-avg" (was "(default)")
- Season selector expanded to 4 options (Spring, Summer, Autumn, Winter)
- Sidebar header renamed to "⚙️ Settings & Tools"
- Metrics display enhanced with context caption
- Device library completely redesigned with categories

#### Technical
- Added 15+ new helper functions in `co2_engine.py`
- Created comprehensive test suite (9 automated tests)
- Added 3 documentation files (TESTING_GUIDE, IMPLEMENTATION_REPORT, FEATURES)
- Enhanced `data/regions.json` with 35 new regions
- Improved error handling and fallbacks
- Performance optimizations with caching

#### Fixed
- Annual savings calculation rounding precision
- Test suite tolerance for floating-point comparisons

---

## [1.0.0] - 2025-10-04

### Initial Release

#### Added

**Core Tracking**
- Multi-category emissions tracking (Energy, Transport, Meals)
- 23 activity types with emission factors
- Real-time CO₂ calculation
- Daily entry persistence to `history.csv`

**Dashboard & Analytics**
- Dashboard tab with real-time metrics
- History tab with full entry log
- Breakdown tab with per-activity details
- 7-day trends and averages
- Category-based analysis

**AI Features**
- GPT-powered eco tips with local fallback
- AI summary generation
- Source transparency badge (GPT vs Fallback)
- Prompt testing suite with 3 modes
- Configurable LLM parameters

**Exports**
- CSV export (Dashboard + History)
- PDF export with custom branding
- Logo upload support
- Color customization
- Optional charts and sparklines

**UX Features**
- Density modes (Compact/Comfy)
- Demo mode with snapshot restore
- User preferences persistence
- Theme-aware defaults
- Input validation and warnings

**Developer Tools**
- Debug controls in sidebar
- Prompt log viewer
- Performance logging
- LLM settings configuration

#### Technical
- Streamlit-based web application
- CSV-based data persistence
- JSON configuration files
- Caching for performance
- Comprehensive error handling

---

## Version Comparison

| Feature | v1.0 | v2.0 |
|---------|------|------|
| **Regions** | 3 | 38 |
| **Device Presets** | 3 | 50+ |
| **Seasonal Profiles** | 3 | 8 |
| **Charts** | Basic | Interactive + Downloads |
| **Hourly Analysis** | Basic | Multi-task + Savings |
| **Test Coverage** | Manual | 9 automated + 30+ manual |
| **Documentation** | 1 file | 6 files |

---

## Upgrade Guide (v1.0 → v2.0)

### Breaking Changes
None - fully backward compatible!

### New Dependencies
```bash
# Optional for enhanced features
pip install altair_saver  # Chart downloads
```

### Data Migration
No migration needed - existing `history.csv` works as-is.

### Configuration Updates
1. **Regions**: `data/regions.json` auto-loads (35 new regions added)
2. **Preferences**: Existing `.user_prefs.json` compatible
3. **Environment**: `.env` format unchanged

### New Files Created
- `data/regions.json` (if not exists)
- `TESTING_GUIDE.md`
- `IMPLEMENTATION_REPORT.md`
- `FEATURES.md`
- `QUICK_REFERENCE.md`
- `test_core_features.py`

---

## Deprecation Notices

### v2.0
- None

### Future (v3.0)
- May deprecate CSV-only storage in favor of SQLite
- May require user authentication for cloud features

---

## Security Updates

### v2.0
- Enhanced input sanitization
- Improved API key handling
- Better error messages (no sensitive data leaks)

### v1.0
- Initial security measures
- Environment variable support
- No PII collection

---

## Performance Improvements

### v2.0
- Caching for grid mix retrieval
- Caching for intensity calculations
- Optimized chart rendering
- Reduced redundant computations

### v1.0
- Basic caching for AI tips
- Session state optimization

---

## Known Issues

### v2.0
- Chart downloads require `altair_saver` + Selenium (optional)
- PDF export requires `reportlab` (optional)
- AI tips require OpenAI API key (optional - has fallback)

### v1.0
- Limited regional coverage (3 regions)
- Basic device presets (3 devices)
- No multi-task comparison

---

## Roadmap & Future Perspectives

### v2.1 (Next Release - Planned)
- **Real-time API Integration** - Connect to live grid intensity APIs (ElectricityMap, WattTime)
- **User Accounts** - Save data per user with authentication and cloud storage
- **Mobile Optimization** - Responsive design improvements for smartphones and tablets
- **Additional Regions** - Expand to 100+ global coverage
- **Batch CSV Import** - Import historical data from utility providers

### v3.0 (Future Vision)
- **Social Features** - Share achievements, compare with friends, community challenges
- **Gamification** - Badges, challenges, leaderboards, achievement system
- **Multi-language Support** - Internationalization (i18n) for global accessibility
- **Multi-user Households** - Role-based access, family/team sharing
- **Advanced Forecasting** - ML models for predictive analytics
- **Smart Home Integration** - APIs for Nest, Ecobee, Tesla, smart meters

### Optional Enhancements (Community Driven)
- Voice assistant integration (Alexa, Google Home)
- Wearable device sync (Fitbit, Apple Watch)
- Blockchain-based carbon credits
- AR/VR visualization of carbon footprint
- Integration with corporate sustainability platforms
- Educational mode for schools and universities
- Carbon offset marketplace integration
- Automated utility bill parsing (OCR)

---

## Contributors

### v2.0
- Core development: [Dr. Khalifa Mejbri]
- Testing: [Dr. Khalifa Mejbri]
- Documentation: [Dr. Khalifa Mejbri]

### v1.0
- Initial release: [Dr. Khalifa Mejbri]

---

## Release Notes

### How to Update

**From v1.0 to v2.0:**
```bash
# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Run tests
python test_core_features.py

# Restart app
streamlit run app.py
```

**No data migration required** - your existing history and preferences work as-is!

---

## Support

For issues or questions about specific versions:
- **v2.0**: See IMPLEMENTATION_REPORT.md
- **v1.0**: See original README.md
- **General**: Open GitHub issue

---

**Stay updated:** Watch this repo for new releases! ⭐

Last updated: 2025-10-08
