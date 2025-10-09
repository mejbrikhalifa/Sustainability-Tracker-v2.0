# Sustainability-Tracker-v2.0 🌍

![Updated](https://img.shields.io/badge/updated-2025--10--08-blue) ![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-ff4b4b) ![Version](https://img.shields.io/badge/version-2.0-green) ![Tests](https://img.shields.io/badge/tests-9%2F9%20passing-brightgreen)

**A comprehensive CO₂ emissions tracking application with advanced features for sustainability analysis.**

Track your daily carbon footprint across Energy, Transport, and Meals with region-specific calculations, smart home energy estimation, hourly intensity profiles, and AI-powered recommendations.

---

## 🌟 Key Features

### ⚡ Electricity Breakdown by Source
- **38 global regions** with real grid mix data (coal, gas, nuclear, hydro, wind, solar)
- **Interactive visualizations**: Side-by-side pie + stacked bar charts
- **Real-time metrics**: Implied intensity, factor in use, electricity share of total
- **Chart downloads**: Export as PNG (optional: requires altair_saver)

**Regions covered:**
- 🇪🇺 Europe: EU-avg, UK, FR, DE, NO, SE, IS, TR, PL
- 🇺🇸 Americas: US-avg, US-CA, CA, MX, BR, AR, CL
- 🇨🇳 Asia: CN, IN, JP, KR, SG, TH, VN, ID, MY, PH
- 🇿🇦 Africa: ZA, NG, EG, KE
- 🇷🇺 Russia: RU
- 🇦🇺 Oceania: AU, NZ
- 🇦🇪 Middle East: AE, SA

### 🏠 Smart Home Energy Estimator
- **50+ device presets** organized in 12 categories
- **Seasonal adjustments**: Automatic usage adaptation for climate devices
- **Quick household profiles**: Small Apartment, Family Home, High-Tech Home
- **One-click apply**: Transfer estimates directly to electricity input
- **CSV import/export**: Save and load custom configurations

**Device categories:**
- Kitchen (9 devices): Refrigerator, Dishwasher, Microwave, Oven, Stove, Coffee Maker, Toaster, Kettle
- Laundry & Cleaning (4): Washer, Dryer, Vacuum, Iron
- Climate Control (7): AC (Small/Large/Central), Space Heater, Electric Radiator, Ceiling Fan, Dehumidifier
- Electronics (6): Desktop PC, Laptop, Monitor, Router, Printer
- Entertainment (3): TVs (LED/OLED), Gaming Console, Sound System
- Lighting (5): LED, CFL, Halogen bulbs, Strip lights
- EV & Mobility (4): EV Charging (Level 1/2), E-Bike, E-Scooter
- Water Heating (2): Electric Water Heater, Tankless
- Outdoor (3): Pool Pump, Hot Tub, Outdoor Lighting
- Personal Care (2): Hair Dryer, Electric Shaver
- Security (2): Security Camera, Doorbell Camera
- Miscellaneous (3): Phone/Tablet Chargers, Smart Speaker

### ⏱️ Hourly/Seasonal Carbon Intensity
- **8 enhanced profiles**: Seasonal + region-specific patterns
  - Standard: Flat, Evening Peak, Winter Dual Peak
  - Seasonal: Spring Solar, Autumn Transition
  - Regional: Solar-Heavy, Wind-Heavy, Coal-Heavy (auto-detected)
- **Color-coded visualization**: Green→Yellow→Red intensity zones with gradient
- **What-if load shifting**: Compare task timing and find optimal hours
- **💰 Annual savings calculator**: Project yearly CO₂ and cost savings ($15/tonne)
- **📊 Multi-task comparison**: Analyze multiple appliances side-by-side
- **Best hours suggestion**: Automatically identify 3 lowest-intensity hours

### 🤖 AI-Powered Eco Tips
- **GPT-backed tips** with resilient local fallback
- **Source badge** (GPT vs Fallback) for transparency
- **Copy-ready blocks** with built-in copy icons
- **Personalized recommendations** based on dominant emissions category
- **AI summary generation** with contextual insights

### 📊 Analytics & Insights
- **Dashboard**: Real-time metrics with 4-column layout (Today, Yesterday, Change %, Streak)
- **History tracking**: Persistent storage in CSV with full activity breakdown
- **Trend analysis**: 7-day averages, category breakdowns, sparklines
- **Efficiency score**: 0-100 rating based on category baselines
- **Comparisons**: Today vs yesterday, weekly trends, per-category analysis
- **Forecasting**: Simple 7-day projection based on history
- **Offset estimation**: Calculate carbon offset costs and project mix

### ⚙️ Advanced Features
- **Quick Actions**: Reset Today, Copy Total shortcuts in sidebar
- **Regionalization**: Override electricity factors by region + renewable adjustment (0-80%)
- **LLM settings**: Configurable temperature and token limits
- **Prompt testing suite**: Experiment with different prompt modes
- **Demo mode**: One-click demo with snapshot restore
- **PDF export**: Server-side generation with custom branding
- **Data persistence**: User preferences saved across sessions

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip or conda

### Installation

**Using pip:**
```bash
# Clone the repository
git clone https://github.com/yourusername/sustainability-tracker.git
cd sustainability-tracker

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Using conda:**
```bash
conda create -n sustain python=3.10 -y
conda activate sustain
pip install -r requirements.txt
```

### Run the App
```bash
streamlit run app.py
```

The app will open at: **http://localhost:8501**

---

## 📦 Dependencies

### Required
```
streamlit>=1.28.0
pandas>=2.0.0
altair>=5.0.0
python-dotenv>=1.0.0
```

### Optional (Enhanced Features)
```
openai>=1.0.0          # AI-powered tips
reportlab>=4.0.0       # PDF export
altair_saver>=0.5.0    # Chart downloads (requires selenium)
matplotlib>=3.7.0      # PDF charts
```

Install all:
```bash
pip install streamlit pandas altair python-dotenv openai reportlab altair_saver matplotlib
```

---

## 🎯 Usage Guide

### 1. Basic Tracking
1. **Enter daily activities** in Energy, Transport, and Meals sections
2. **Click "💾 Calculate & Save"** to compute and store emissions
3. **View results** in Dashboard tab with metrics and trends

### 2. Region Selection
1. **Sidebar → Regionalization**
2. **Select your region** from 38 options (default: EU-avg)
3. **Adjust renewable %** if using default region
4. **View grid mix** in sidebar or ⚡ Energy Mix tab

### 3. Smart Home Estimator
1. **Navigate to 🔌 Estimator tab**
2. **Click "📚 Device Library"** to browse 50+ presets
3. **Add devices** by category or use Quick Profiles
4. **Adjust season** for automatic climate device adjustments
5. **Click "↪️ Apply to Energy inputs"** to use estimate

### 4. Hourly Intensity Analysis
1. **Navigate to ⏱️ Intensity tab**
2. **Select season** (Spring/Summer/Autumn/Winter)
3. **View 24-hour profile** with color-coded zones
4. **Use What-if tool** to compare task timing
5. **Try Multi-Task Comparison** for multiple appliances
6. **Calculate annual savings** for recurring tasks

### 5. AI Eco Tips
1. **Navigate to 💡 Eco Tips tab**
2. **Click "Generate Tip"** (requires OpenAI API key)
3. **View personalized recommendation** based on your inputs
4. **Copy tip** using built-in code block copy icon
5. **Download as PDF** with custom branding

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# OpenAI API Key (optional - for AI tips)
OPENAI_API_KEY=sk-your-key-here

# Simulate API failures for testing (optional)
SIMULATE_API_FAILURES=0
```

### Regional Data

Edit `data/regions.json` to add or modify regions:

```json
{
  "YOUR-REGION": {
    "__meta__": {
      "source": "Your data source",
      "version": "2024.1",
      "url": "https://example.com"
    },
    "factors": {
      "electricity_kwh": 0.35
    },
    "grid_mix": {
      "coal": 0.30,
      "gas": 0.25,
      "nuclear": 0.20,
      "hydro": 0.10,
      "wind": 0.10,
      "solar": 0.05
    }
  }
}
```

### Device Presets

Modify `DEVICE_PRESETS` in `co2_engine.py` to add custom devices:

```python
DEVICE_PRESETS: Dict[str, dict] = {
    "Your Device": {
        "power_w": 1000,
        "hours_per_day": 4.0,
        "category": "Custom"
    },
}
```

---

## 🧪 Testing

### Automated Tests

Run the comprehensive test suite:

```bash
python test_core_features.py
```

**Expected output:**
```
============================================================
📊 TEST RESULTS: 9 passed, 0 failed
============================================================
✅ ALL TESTS PASSED! 🎉
```

**Tests cover:**
1. ✅ Basic emissions calculation
2. ✅ Region impact on electricity
3. ✅ Grid mix & intensity computation
4. ✅ Hourly intensity profiles (12 combinations)
5. ✅ Device presets library (50 devices)
6. ✅ Seasonal adjustments
7. ✅ Multi-task comparison
8. ✅ Annual savings calculator
9. ✅ Global regions coverage (38 regions)

### Manual Testing

Follow the comprehensive guide:

```bash
# View testing guide
cat TESTING_GUIDE.md
```

**30+ test cases** covering:
- Basic emissions calculation
- Smart Home Estimator
- Energy Mix by region
- Hourly Intensity features
- Data persistence
- Quick actions & UI

---

## 📁 Project Structure

```
sustainability-tracker/
├── app.py                          # Main Streamlit application
├── co2_engine.py                   # Core emissions calculations & helpers
├── ai_tips.py                      # AI tip generation with fallbacks
├── utils.py                        # Formatting & utility functions
├── app_helpers.py                  # UI helper functions
├── data/
│   └── regions.json                # 38 global regions with grid mix
├── tests/
│   └── test_co2_engine.py         # Unit tests
├── test_core_features.py          # Integration tests (9 tests)
├── TESTING_GUIDE.md               # Manual testing guide (30+ cases)
├── IMPLEMENTATION_REPORT.md       # Complete feature documentation
├── history.csv                     # User data (auto-created)
├── .user_prefs.json               # Saved preferences (auto-created)
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables template
└── README.md                       # This file
```

---

## 🎨 Screenshots

### Dashboard
![Dashboard](assets/screenshot_dashboard.png)
*Compact layout with real-time metrics and quick actions*

### Energy Mix by Region
![Energy Mix](assets/screenshot_energy_mix.png)
*Interactive pie and stacked bar charts showing grid composition*

### Smart Home Estimator
![Estimator](assets/screenshot_estimator.png)
*50+ device presets with seasonal adjustments*

### Hourly Intensity
![Hourly Intensity](assets/screenshot_intensity.png)
*Color-coded 24-hour profiles with load shifting recommendations*

### Eco Tips
![Eco Tips](assets/screenshot_tips.png)
*AI-powered personalized recommendations*

---

## 🔬 Technical Details

### Architecture

**Frontend:** Streamlit (Python web framework)
**Data Layer:** CSV for persistence, JSON for configuration
**Caching:** `@st.cache_data` for performance optimization
**AI Integration:** OpenAI API with exponential backoff and fallbacks

### Key Algorithms

**Emissions Calculation:**
```python
# Region-aware calculation with renewable adjustment
total_co2 = calculate_co2_v2(
    activity_data,
    region_code="EU-avg",
    renewable_adjust=0.30  # 30% renewable
)
```

**Grid Mix Intensity:**
```python
# Compute implied kg CO₂/kWh from generation mix
mix = get_grid_mix("FR")  # {"nuclear": 0.66, "hydro": 0.12, ...}
intensity = compute_mix_intensity(mix)  # 0.049 kg/kWh
```

**Hourly Profile:**
```python
# Get 24-hour intensity profile with seasonal/regional adaptation
profile = hourlyIntensityProfile("US-CA", "Summer")
# Returns: [0.85, 0.83, ..., 0.52, ..., 1.30, ...] (24 values)
```

**Multi-Task Comparison:**
```python
tasks = [
    {"name": "Laundry", "kwh": 2.0, "hour": 20},
    {"name": "EV Charging", "kwh": 15.0, "hour": 18},
]
results = compare_tasks_at_hours(profile, tasks)
# Returns savings kg and % for each task
```

### Performance

- **Load time:** <2s with caching
- **Calculation speed:** <100ms for typical inputs
- **Chart rendering:** <500ms with Altair
- **Memory usage:** ~50MB base + ~10MB per 1000 history entries

---

## 📊 Data Sources

### Emission Factors
- **Default factors**: IPCC, EPA guidelines
- **Regional factors**: National grid operators, Ember Climate, IEA
- **Device power ratings**: Energy Star, manufacturer specifications

### Grid Mix Data
- **Europe**: Ember Climate, national TSOs
- **Americas**: EIA (US), CER (Canada), national utilities
- **Asia**: NEA (China), CEA (India), METI (Japan)
- **Others**: National energy authorities and grid operators

**Note:** All data is illustrative and should be validated for production use. See `data/regions.json` for sources and versions.

---

## 🛠️ Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/mejbrikhalifa/sustainability-tracker.git
cd sustainability-tracker
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dev dependencies
pip install -r requirements.txt
pip install pytest black flake8

# Run tests
python test_core_features.py

# Run app
streamlit run app.py
```

### Running Tests

**Automated tests:**
```bash
python test_core_features.py
```

**Manual testing:**
```bash
# Follow comprehensive guide
cat TESTING_GUIDE.md
```

### Code Quality

**Linting:**
```bash
flake8 app.py co2_engine.py ai_tips.py utils.py
```

**Formatting:**
```bash
black app.py co2_engine.py ai_tips.py utils.py
```

---

## 🚀 Deployment

### Streamlit Community Cloud

1. **Push to GitHub**
2. **Go to** [share.streamlit.io](https://share.streamlit.io)
3. **Create new app** → Select your repo/branch
4. **Set main file:** `app.py`
5. **Add secrets** (optional):
   ```toml
   OPENAI_API_KEY = "sk-your-key-here"
   ```
6. **Deploy!**

### Docker (Optional)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```bash
docker build -t sustainability-tracker .
docker run -p 8501:8501 sustainability-tracker
```

---

## 📖 Documentation

### User Guides
- **TESTING_GUIDE.md** - 30+ manual test cases with step-by-step instructions
- **IMPLEMENTATION_REPORT.md** - Complete feature documentation and technical details

### API Reference

**Core Functions:**

```python
# Emissions calculation
calculate_co2_v2(activity_data, region_code=None, renewable_adjust=None) -> float

# Grid mix
get_grid_mix(region_code) -> Dict[str, float]
compute_mix_intensity(mix) -> float
get_effective_electricity_factor(region_code, renewable_adjust) -> float

# Hourly intensity
hourlyIntensityProfile(region_code, season) -> List[float]
suggest_low_hours(profile, top_n=3) -> List[int]
compare_tasks_at_hours(profile, tasks) -> List[dict]
calculate_annual_savings(daily_kwh, current_hour, profile) -> dict

# Device presets
get_device_presets_by_category() -> Dict[str, List[str]]
apply_seasonal_adjustment(device_name, season, base_hours) -> float

# Efficiency & planning
efficiency_score(activity_data) -> dict
weekly_goal_plan(current_week_sum, remaining_days, target_week_sum) -> dict
estimate_offsets(kg_today, kg_week, price_per_tonne_usd) -> dict
```

---

## 🎯 Use Cases

### Individual Users
- Track daily carbon footprint
- Identify high-impact activities
- Get personalized reduction tips
- Plan optimal appliance usage times
- Monitor progress over time

### Households
- Estimate total home energy consumption
- Compare different appliance schedules
- Calculate savings from load shifting
- Share results with family members

### Educators
- Demonstrate carbon impact of daily activities
- Compare regional grid mixes
- Teach about renewable energy
- Show real-world optimization scenarios

### Researchers
- Collect anonymized emissions data
- Test different prompt strategies
- Analyze user behavior patterns
- Validate emission factor accuracy

---

## 🐛 Troubleshooting

### Common Issues

**Import errors:**
```bash
# Install missing dependencies
pip install streamlit pandas altair
```

**Chart rendering issues:**
```bash
# Update Altair
pip install --upgrade altair
```

**Slow performance:**
```bash
# Clear Streamlit cache
streamlit cache clear
```

**Data not saving:**
- Check file permissions in project directory
- Ensure `history.csv` is writable

**API errors (429 quota):**
- App automatically falls back to local tips
- Check your OpenAI account billing
- Tips will show "AI source: Fallback"

**Chart download not working:**
```bash
# Install altair_saver and selenium
pip install altair_saver selenium
# Download ChromeDriver for your system
```

---

## 🤝 Contributing

We welcome contributions! Here's how:

### Reporting Issues
1. Check existing issues first
2. Provide reproduction steps
3. Include error messages and screenshots
4. Specify your environment (OS, Python version)

### Submitting Pull Requests
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes with tests
4. Run tests: `python test_core_features.py`
5. Commit: `git commit -m "Add your feature"`
6. Push: `git push origin feature/your-feature`
7. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guide
- Add type hints to new functions
- Include docstrings for public APIs
- Add tests for new features
- Update README for user-facing changes

---

## 📈 Roadmap & Future Perspectives

### v2.1 (Next Release - Planned)
- [ ] **Real-time API Integration** - Connect to live grid intensity APIs (e.g., ElectricityMap, WattTime)
- [ ] **User Accounts** - Save data per user with authentication
- [ ] **Mobile Optimization** - Responsive design improvements for smartphones
- [ ] **Additional regions** - Expand to 100+ global coverage
- [ ] **Batch CSV import** - Import historical data from utilities

### v3.0 (Future Vision)
- [ ] **Social Features** - Share achievements, compare with friends, community challenges
- [ ] **Gamification** - Badges, challenges, leaderboards, achievement system
- [ ] **Multi-language Support** - Internationalization (i18n) for global users
- [ ] **Multi-user Households** - Role-based access, family/team sharing
- [ ] **Advanced Forecasting** - ML models for predictive analytics
- [ ] **Smart Home Integration** - APIs for Nest, Ecobee, Tesla, etc.

### Optional Enhancements (Community Requests)
- [ ] Voice assistant integration (Alexa, Google Home)
- [ ] Wearable device sync (Fitbit, Apple Watch)
- [ ] Blockchain-based carbon credits
- [ ] AR/VR visualization of carbon footprint
- [ ] Integration with corporate sustainability platforms
- [ ] Educational mode for schools and universities

---

## 📜 License

MIT License - see LICENSE file for details

---

## 🙏 Acknowledgments

### Data Sources
- **Ember Climate** - European grid mix data
- **IEA** - International energy statistics
- **EPA** - US emission factors
- **Energy Star** - Device power ratings
- **National Grid Operators** - Regional grid data

### Technologies
- **Streamlit** - Web framework
- **Altair** - Declarative visualizations
- **OpenAI** - AI-powered tips
- **Pandas** - Data manipulation
- **ReportLab** - PDF generation

### Contributors
- Dr. Khalifa Mejbri – Professor of Energy Engineering, Expert in Data Science & Machine Learning

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/mejbrikhalifa/sustainability-tracker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mejbrikhalifa/sustainability-tracker/discussions)
- **Email**: mejbri_khalifa@yahoo.fr

---

## 📊 Project Stats

- **Version:** 2.0
- **Lines of Code:** ~6,000+
- **Features:** 13 major features
- **Regions:** 38 global coverage
- **Device Presets:** 50+
- **Test Coverage:** 9 automated tests (100% passing)
- **Documentation:** 3 comprehensive guides

---

## ⭐ Star History

If you find this project useful, please consider giving it a star! ⭐

---

**Built with ❤️ for a sustainable future 🌱**

Last updated: 2025-10-08 | Version 2.0

