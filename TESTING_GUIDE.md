# 🧪 End-to-End Testing Guide
## Sustainability Tracker - Comprehensive Test Plan

**Date:** 2025-10-08  
**Version:** v2.0 (with all enhancements)

---

## ✅ Test Checklist

### 1️⃣ **Basic Emissions Calculation** (5 min)

#### Test Case 1.1: Manual Input Entry
- [ ] Navigate to **Energy** section
- [ ] Enter: `Electricity: 10 kWh`
- [ ] Enter: `Natural Gas: 2 m³`
- [ ] Navigate to **Transport** section
- [ ] Enter: `Petrol: 5 L`
- [ ] Navigate to **Meals** section
- [ ] Enter: `Meat: 0.2 kg`
- [ ] Click **💾 Calculate & Save**
- [ ] **Expected:** Total should be calculated and saved
- [ ] **Verify:** Success message appears with next steps

#### Test Case 1.2: Region Impact
- [ ] In sidebar → **Regionalization**
- [ ] Change region from `EU-avg` to `CN` (China)
- [ ] **Expected:** Electricity factor changes (should increase)
- [ ] Re-calculate with same inputs
- [ ] **Verify:** Total emissions increase due to higher grid intensity

---

### 2️⃣ **Smart Home Energy Estimator** (10 min)

#### Test Case 2.1: Device Library
- [ ] Navigate to **🔌 Estimator** tab
- [ ] Click **📚 Device Library (50+ presets)**
- [ ] **Verify:** 10+ categories displayed (Kitchen, Climate, Electronics, etc.)
- [ ] Expand **Kitchen** category
- [ ] Click **➕ Refrigerator**
- [ ] **Expected:** Device added to table with 150W, 24h/day
- [ ] Expand **Climate** category
- [ ] Click **➕ Air Conditioner (Large)**
- [ ] **Verify:** Device added with seasonal adjustment

#### Test Case 2.2: Seasonal Adjustment
- [ ] In Device Library, change **Season** to `Winter`
- [ ] Add **Space Heater**
- [ ] **Expected:** Hours adjusted to 8.0 (winter usage)
- [ ] Change Season to `Summer`
- [ ] Add **Air Conditioner (Small)**
- [ ] **Expected:** Hours adjusted to 8.0 (summer usage)

#### Test Case 2.3: Quick Profiles
- [ ] Click **🏠 Quick Profiles**
- [ ] Click **🏡 Family Home**
- [ ] **Expected:** Table populated with 10 devices
- [ ] **Verify:** Total energy shows realistic daily kWh (30-50 kWh)
- [ ] **Verify:** CO₂ estimate matches region factor

#### Test Case 2.4: Apply to Inputs
- [ ] Review total kWh/day in metrics
- [ ] Click **↪️ Apply to Energy inputs (electricity_kwh)**
- [ ] **Expected:** Page reloads
- [ ] Navigate back to **Energy** section
- [ ] **Verify:** Electricity field pre-filled with estimated value

---

### 3️⃣ **Energy Mix by Region** (8 min)

#### Test Case 3.1: EU Average
- [ ] Sidebar → Select region `EU-avg`
- [ ] Navigate to **⚡ Energy Mix** tab
- [ ] **Verify:** Pie chart shows mix (coal, gas, nuclear, hydro, wind, solar)
- [ ] **Verify:** Stacked bar chart displays exact percentages
- [ ] **Verify:** Metrics show:
  - Implied mix intensity: ~0.280 kg/kWh
  - Factor in use matches
  - Today's electricity CO₂ calculated

#### Test Case 3.2: Low-Carbon Region (France)
- [ ] Change region to `FR`
- [ ] **Expected:** Pie chart updates
- [ ] **Verify:** Nuclear dominates (~66%)
- [ ] **Verify:** Implied intensity very low (~0.070 kg/kWh)

#### Test Case 3.3: High-Carbon Region (China)
- [ ] Change region to `CN`
- [ ] **Expected:** Coal dominates (~62%)
- [ ] **Verify:** Implied intensity high (~0.580 kg/kWh)

#### Test Case 3.4: Solar-Heavy Region (California)
- [ ] Change region to `US-CA`
- [ ] **Verify:** Solar share >15%
- [ ] **Verify:** Gas still significant (~42%)

#### Test Case 3.5: Chart Download (if altair_saver installed)
- [ ] Click **💾 Download Pie** button
- [ ] **Expected:** PNG file downloads
- [ ] Click **💾 Download Bar** button
- [ ] **Verify:** Second PNG downloads

---

### 4️⃣ **Hourly/Seasonal Carbon Intensity** (12 min)

#### Test Case 4.1: Seasonal Profiles
- [ ] Navigate to **⏱️ Intensity** tab
- [ ] Select **Season: Spring**
- [ ] **Verify:** Chart shows low midday intensity (solar peak)
- [ ] Change to **Season: Summer**
- [ ] **Verify:** Chart shows evening peak
- [ ] Change to **Season: Winter**
- [ ] **Verify:** Chart shows dual peaks (morning + evening)

#### Test Case 4.2: Region-Specific Patterns
- [ ] Keep season as `Summer`
- [ ] Sidebar → Change region to `US-CA` (solar-heavy)
- [ ] **Expected:** Chart shows dramatic midday dip (solar generation)
- [ ] Change region to `UK` (wind-heavy)
- [ ] **Expected:** More variable pattern
- [ ] Change region to `CN` (coal-heavy)
- [ ] **Expected:** Flatter profile with modest peaks

#### Test Case 4.3: What-If Load Shifting
- [ ] Select **Activity: Laundry**
- [ ] Set **Task energy: 2.0 kWh**
- [ ] Set **Operating hour: 20** (8 PM)
- [ ] **Verify:** Metrics show:
  - Intensity at 20:00
  - Estimated CO₂ for task
  - Suggestion for best hour (likely early morning)
  - Delta savings in kg

#### Test Case 4.4: Annual Savings Calculator
- [ ] Scroll to **💰 Annual Savings Calculator**
- [ ] Set **Daily energy use: 3.0 kWh**
- [ ] Set **Current operating hour: 18** (6 PM - peak time)
- [ ] **Verify:** Metrics display:
  - Best hour (likely 2-4 AM)
  - Daily savings (kg)
  - Yearly savings (kg)
  - Cost savings/year ($)
- [ ] **Expected:** Savings % should be 10-30% depending on region

#### Test Case 4.5: Multi-Task Comparison
- [ ] Scroll to **📊 Multi-Task Comparison**
- [ ] **Verify:** Default tasks loaded (Laundry, Dishwasher, EV Charging)
- [ ] Edit **Laundry** hour to `20`
- [ ] Edit **EV Charging** hour to `18`
- [ ] Click **🔍 Compare Tasks**
- [ ] **Verify:** Table shows:
  - Current CO₂ for each task
  - Optimal hour for each
  - Savings kg and %
- [ ] **Verify:** Summary metrics show total savings
- [ ] **Verify:** Best opportunity highlighted (likely EV Charging)

#### Test Case 4.6: Add Custom Task
- [ ] In task table, click **+** to add row
- [ ] Enter: `Pool Pump`, `1.5 kWh`, hour `14`
- [ ] Click **🔍 Compare Tasks**
- [ ] **Verify:** New task included in comparison

---

### 5️⃣ **Data Persistence & History** (5 min)

#### Test Case 5.1: Save Entry
- [ ] Navigate to main inputs
- [ ] Enter realistic daily data
- [ ] Click **💾 Calculate & Save**
- [ ] **Expected:** Success message
- [ ] Navigate to **📜 History** tab
- [ ] **Verify:** Today's entry appears in table

#### Test Case 5.2: Multi-Day History
- [ ] Change date to yesterday
- [ ] Enter different values
- [ ] Save
- [ ] Navigate to **📊 Dashboard** tab
- [ ] **Verify:** Line chart shows 2 data points
- [ ] **Verify:** Trend visible

#### Test Case 5.3: CSV Export
- [ ] In **📜 History** tab
- [ ] Click **Download CSV**
- [ ] **Expected:** File downloads
- [ ] Open CSV in Excel/text editor
- [ ] **Verify:** All columns present (date, total_kg, all activities)

---

### 6️⃣ **Quick Actions & UI Polish** (5 min)

#### Test Case 6.1: Quick Actions
- [ ] Sidebar → Expand **⚡ Quick Actions**
- [ ] Click **🔄 Reset Today**
- [ ] **Expected:** All inputs cleared
- [ ] **Verify:** Page reloads with zeros

#### Test Case 6.2: Copy Total
- [ ] Enter some data and calculate
- [ ] Click **📋 Copy Total**
- [ ] **Verify:** Total displayed in code block

#### Test Case 6.3: Enhanced Metrics
- [ ] Main page → Check metrics row
- [ ] **Verify:** 4 columns displayed:
  - Today's Total
  - Yesterday
  - Change (%)
  - Streak
- [ ] **Verify:** Caption shows: Region, Renewable %, Date

#### Test Case 6.4: Tooltips
- [ ] Hover over **Electricity (kWh)** input
- [ ] **Verify:** Tooltip mentions Smart Home Estimator
- [ ] Hover over other inputs
- [ ] **Verify:** Help text appears

---

### 7️⃣ **AI Tips & Advanced Features** (Optional - 5 min)

#### Test Case 7.1: Generate Eco Tip
- [ ] Navigate to **💡 Eco Tips** tab
- [ ] Click **Generate Tip**
- [ ] **Expected:** AI-generated tip appears (if API key configured)
- [ ] **Verify:** Tip is relevant to inputs

#### Test Case 7.2: Efficiency Score
- [ ] Navigate to **🏅 Score** tab
- [ ] **Verify:** Score displayed (0-100)
- [ ] **Verify:** Category breakdown shown
- [ ] **Verify:** Guidance notes provided

---

## 🎯 Success Criteria

### Must Pass (Critical)
- ✅ Basic emissions calculation works
- ✅ Region selection changes electricity factor
- ✅ Device library loads and adds devices
- ✅ Energy Mix charts display correctly
- ✅ Hourly intensity profiles adapt to region
- ✅ Data saves and persists

### Should Pass (Important)
- ✅ Seasonal adjustments apply correctly
- ✅ Multi-task comparison calculates savings
- ✅ Quick profiles load successfully
- ✅ Charts are interactive and downloadable
- ✅ Quick actions work (reset, copy)

### Nice to Have (Enhancement)
- ✅ AI tips generate (requires API key)
- ✅ PDF export works (requires reportlab)
- ✅ Chart downloads work (requires altair_saver)

---

## 🐛 Bug Reporting Template

If you find any issues, report them using this format:

```
**Test Case:** [e.g., 2.1 - Device Library]
**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Result:**

**Actual Result:**

**Screenshots:** (if applicable)

**Error Messages:** (if any)
```

---

## 📊 Test Results Summary

After completing all tests, fill this out:

```
Total Tests: 30+
Passed: ___
Failed: ___
Skipped: ___

Critical Issues: ___
Minor Issues: ___

Overall Status: [ ] PASS  [ ] FAIL  [ ] NEEDS FIXES
```

---

## 🚀 Next Steps After Testing

1. **If all tests pass:** Ready for production use!
2. **If minor issues:** Document and prioritize fixes
3. **If critical issues:** Debug and re-test

---

**Happy Testing! 🎉**
