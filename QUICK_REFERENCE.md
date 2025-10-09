# 🚀 Quick Reference Guide

**Sustainability Tracker v2.0** - Essential commands and workflows

---

## ⚡ Quick Start (30 seconds)

```bash
# Install and run
pip install streamlit pandas altair python-dotenv
streamlit run app.py
```

Open: **http://localhost:8501**

---

## 🎯 Common Workflows

### Track Today's Emissions
1. Enter values in Energy/Transport/Meals
2. Click **💾 Calculate & Save**
3. View results in **📊 Dashboard**

### Estimate Home Energy
1. Go to **🔌 Estimator** tab
2. Click **📚 Device Library**
3. Add devices or use **🏠 Quick Profiles**
4. Click **↪️ Apply to Energy inputs**

### Optimize Appliance Timing
1. Go to **⏱️ Intensity** tab
2. Select your **Season**
3. Use **What-if tool** or **Multi-Task Comparison**
4. See **💰 Annual Savings** projection

### Compare Regions
1. Sidebar → **Regionalization**
2. Select different regions
3. Go to **⚡ Energy Mix** tab
4. Compare grid mixes and intensities

---

## 🔑 Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Navigate tabs | Click tab names |
| Expand/collapse | Click section headers |
| Copy code blocks | Click copy icon (top-right) |
| Reset inputs | Sidebar → Quick Actions → Reset |

---

## 📊 Key Metrics Explained

| Metric | Meaning | Good Value |
|--------|---------|------------|
| **Today's Total** | Total kg CO₂ today | <15 kg |
| **Change %** | vs Yesterday | Negative (decreasing) |
| **Streak** | Consecutive days logged | 7+ days |
| **Efficiency Score** | 0-100 rating | 70+ |
| **Implied Intensity** | Grid kg CO₂/kWh | <0.20 |

---

## 🌍 Region Quick Reference

| Region | Code | Intensity | Best For |
|--------|------|-----------|----------|
| **Cleanest** |
| Iceland | IS | 0.010 | Hydro + Geothermal |
| Norway | NO | 0.020 | Hydro-dominant |
| Sweden | SE | 0.040 | Nuclear + Hydro |
| France | FR | 0.070 | Nuclear-heavy |
| **Mid-Range** |
| Brazil | BR | 0.090 | Hydro + Wind |
| New Zealand | NZ | 0.110 | Hydro + Geothermal |
| Canada | CA | 0.120 | Hydro-dominant |
| Kenya | KE | 0.150 | Geothermal + Hydro |
| **High-Carbon** |
| China | CN | 0.580 | Coal-heavy |
| Australia | AU | 0.650 | Coal-dominant |
| India | IN | 0.710 | Coal-heavy |
| South Africa | ZA | 0.920 | Coal-dominant |

---

## 🏠 Device Power Quick Reference

| Device | Power (W) | Daily Use | kWh/day |
|--------|-----------|-----------|---------|
| **Always On** |
| Refrigerator | 150 | 24h | 3.6 |
| Router | 10 | 24h | 0.24 |
| Security Camera | 5 | 24h | 0.12 |
| **High Power** |
| Central AC | 3500 | 8h | 28.0 |
| EV Charging L2 | 7200 | 4h | 28.8 |
| Electric Water Heater | 4000 | 2h | 8.0 |
| Dryer | 3000 | 0.8h | 2.4 |
| **Medium Power** |
| Dishwasher | 1800 | 1h | 1.8 |
| Space Heater | 1500 | 4h | 6.0 |
| Hair Dryer | 1500 | 0.3h | 0.45 |
| **Low Power** |
| Laptop | 65 | 6h | 0.39 |
| TV LED | 90 | 4h | 0.36 |
| LED Bulb 10W | 10 | 5h | 0.05 |

---

## ⏱️ Best Hours by Region Type

| Region Type | Best Hours | Worst Hours | Reason |
|-------------|------------|-------------|--------|
| **Solar-Heavy** (CA, AU) | 11:00-14:00 | 18:00-21:00 | Midday solar peak |
| **Wind-Heavy** (UK, NO) | 02:00-05:00 | 17:00-20:00 | Night wind generation |
| **Coal-Heavy** (PL, IN) | 03:00-06:00 | 18:00-21:00 | Off-peak demand |
| **Default** | 02:00-05:00 | 18:00-21:00 | Low demand period |

---

## 💰 Savings Calculator Quick Math

**Formula:**
```
Daily Savings (kg) = kWh × (Peak Intensity - Off-Peak Intensity)
Yearly Savings (kg) = Daily Savings × 365
Cost Savings ($) = Yearly Savings × $0.015 (at $15/tonne)
```

**Example:**
```
EV Charging: 15 kWh/day
Peak (18:00): 0.35 kg/kWh
Off-Peak (03:00): 0.22 kg/kWh

Daily: 15 × (0.35 - 0.22) = 1.95 kg
Yearly: 1.95 × 365 = 712 kg
Cost: 712 × $0.015 = $10.68/year
```

---

## 🔧 Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| **App won't start** | `pip install -r requirements.txt` |
| **Charts not showing** | `pip install --upgrade altair` |
| **Slow performance** | `streamlit cache clear` |
| **API errors (429)** | App auto-falls back to local tips |
| **Data not saving** | Check file permissions |
| **Import errors** | Reinstall dependencies |

---

## 📱 Quick Commands

### Development
```bash
# Run app
streamlit run app.py

# Run tests
python test_core_features.py

# Clear cache
streamlit cache clear

# Check dependencies
pip list | grep streamlit
```

### Data Management
```bash
# Backup history
cp history.csv history_backup.csv

# Reset preferences
rm .user_prefs.json

# Export regions
cp data/regions.json regions_backup.json
```

---

## 🎨 Customization Quick Tips

### Change Default Region
Edit `app.py` line ~880:
```python
default_idx = available_regions.index("YOUR-REGION")
```

### Add Custom Device
Edit `co2_engine.py` `DEVICE_PRESETS`:
```python
"Your Device": {"power_w": 1000, "hours_per_day": 4.0, "category": "Custom"}
```

### Adjust Emission Factors
Edit `co2_engine.py` `CO2_FACTORS`:
```python
"electricity_kwh": 0.233,  # Change to your local factor
```

---

## 📞 Quick Links

- **Full Documentation**: README.md
- **Feature Details**: FEATURES.md
- **Testing Guide**: TESTING_GUIDE.md
- **Implementation Report**: IMPLEMENTATION_REPORT.md
- **GitHub Repo**: [Your repo URL]
- **Live Demo**: [Your demo URL]

---

## 🎓 Learning Resources

### Understanding Carbon Intensity
- Lower intensity = cleaner grid
- Varies by time of day and season
- Affected by renewable generation

### Load Shifting Benefits
- Move high-power tasks to low-intensity hours
- Typical savings: 10-30% CO₂ reduction
- Best for: EV charging, laundry, dishwasher, pool pumps

### Regional Differences
- **Hydro/Nuclear regions**: Very low intensity (0.01-0.10)
- **Mixed grids**: Medium intensity (0.20-0.40)
- **Coal-heavy grids**: High intensity (0.50-0.90)

---

---

## 🔮 Coming Soon (Future Perspectives)

### v2.1 Highlights
- 🌐 **Real-time API Integration** - Live grid intensity data
- 👤 **User Accounts** - Cloud storage and sync
- 📱 **Mobile Optimization** - Full smartphone support
- 🌍 **100+ Regions** - Expanded global coverage

### v3.0 Vision
- 🤝 **Social Features** - Share & compare with friends
- 🎮 **Gamification** - Badges, challenges, leaderboards
- 🌏 **Multi-language** - Global accessibility (i18n)
- 🏡 **Smart Home APIs** - Auto-sync with Nest, Tesla, etc.

**Want to contribute?** See FEATURES.md for full roadmap!

---

**Need more help?** See full README.md or open an issue on GitHub!

Version 2.0 | 2025-10-08
