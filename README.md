# Real-time Heart Rate & HRV Analysis (RP2040 W)

##  Overview
An advanced medical IoT system that measures heart rate and Heart Rate Variability (HRV). This project integrates real-time signal processing with cloud analytics to provide clinical-grade health insights.

##  My Core Contributions (Algorithm & Logic)
  **Real-time Peak Detection**: Developed a slope-based algorithm to process 250Hz PPG analog signals, ensuring accurate R-peak identification.
  **HRV Analytics**: Implemented on-device calculations for **RMSSD** and **SDNN** using 30s data windows.
  **Cloud & Data Logic**: Managed data formatting and synchronization with **Kubios Cloud** and **MQTT** brokers.

##  Hardware System
  **MCU**: Raspberry Pi Pico W
  **Sensors**: Crowtail PPG Pulse Sensor v2.0
  **Interface**: OLED Display (SSD1306) & Rotary Encoder
