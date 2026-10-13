# SolarFlow — AIoT Smart Greenhouse Farming System

**SolarFlow** is an Artificial Intelligence of Things (AIoT) project powered by solar that aims to predict changes in greenhouse environmental conditions and proactively control the growing environment before conditions become unfavorable for crops.

Rather than relying only on current sensor readings, SolarFlow is designed to combine environmental monitoring, machine-learning-based forecasting and automated control to support smarter greenhouse management.

##  The Problem

Greenhouse conditions can change quickly and delayed responses to rising temperatures, changing humidity or unsuitable soil moisture can negatively affect crop growth.

Traditional monitoring and reactive control systems may only respond after conditions have already crossed a configured limit.

SolarFlow aims to address this challenge by using environmental sensor data and forecasting to identify potential risks early and support timely intervention.

## Our Solution

SolarFlow will collect greenhouse sensor readings, estimate how temperature and humidity may change over the next 30 minutes and use configurable safety rules to determine whether preventive action is needed.

For example, if a forecast indicates that the greenhouse may overheat, the system can activate ventilation before the temperature reaches the configured upper limit.

The 30-minute forecasting window is a development and evaluation target. Forecast accuracy will be measured against actual sensor readings.

##  Project Objectives

- Monitor greenhouse temperature, humidity and soil moisture.
- Collect and store timestamped environmental readings.
- Forecast future greenhouse temperature and humidity.
- Identify potential environmental risks using configurable thresholds.
- Support proactive ventilation and automated irrigation.
- Visualize current readings, forecasts, alerts and actuator status.
- Evaluate forecasting accuracy by comparing predictions with actual measurements.

##  Proposed System Architecture

SolarFlow is organized into five main layers.

### 1. Sensor Layer
Collects environmental data using temperature, humidity and soil moisture sensors.

### 2. Embedded System Layer
Uses an Arduino Uno to read sensor values and control connected actuators.

### 3. Prediction Engine
Uses Python, pandas, scikit-learn and a forecasting model or external forecasting service to estimate future environmental conditions.

### 4. Control Layer
Applies configurable safety rules to support proactive ventilation and moisture-based irrigation using suitable relay or driver circuits.

### 5. Monitoring Dashboard
Uses React, Vite and TypeScript to display sensor readings, forecasts, historical charts, alerts and actuator status.

##  Proposed Technology Stack

| Component | Technology |
|---|---|
| Microcontroller | Arduino Uno |
| Sensors | DHT22 temperature/humidity sensor and soil moisture sensor |
| Programming and firmware | Arduino C/C++ |
| Initial communication | USB serial |
| Backend and data processing | Python |
| Data analysis | pandas |
| Forecasting | scikit-learn and a suitable forecasting API |
| Frontend | React, Vite, TypeScript |
| Charts | A suitable React charting library |
| Version control | Git and GitHub |

The technology stack may be refined as the prototype develops.

##  How SolarFlow Will Work

1. **Monitor:** Sensors continuously collect greenhouse environmental readings.
2. **Predict:** The forecasting engine estimates temperature and humidity changes over the target 30-minute horizon.
3. **Act early:** The control layer evaluates predicted risks and can trigger appropriate actions, such as ventilation, within configured safety limits.
4. **Evaluate:** The system records predictions, actual readings and control events to assess forecasting accuracy and system performance.

##  Safety and Reliability

- Local control rules should remain safe if the computer, forecasting service or communication link becomes unavailable.
- Pumps and fans must use suitably rated drivers, power supplies and switching hardware.
- Maximum actuator runtime and manual shutdown mechanisms should be provided.
- API credentials and other secrets must not be committed to the repository.
- Forecasting performance must be evaluated before predictive control is relied upon.

##  Future Possibilities

- Support for multiple greenhouse zones.
- Improved forecasting using additional historical sensor data.
- Configurable crop-specific environmental thresholds.
- Notifications when unfavorable conditions are predicted.
- Remote monitoring and connectivity beyond the initial USB prototype.

##  Contributors
Vane Meta Apeli
Emmanuella Omondi

##  Vision

To make greenhouse farming more proactive, efficient and data-driven through accessible AIoT technology.
