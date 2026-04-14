# 🚀 Turkey Lunar Rover Autonomous Navigation System

This project was developed as part of a hackathon organized by the Turkish Space Agency (TUA).
It simulates an autonomous rover designed to operate on the Moon’s surface, focusing on safe and intelligent navigation in harsh terrain conditions.

## 🧠 Overview

The system combines:

- Procedurally generated lunar terrain
- Autonomous path planning using A*
- Obstacle and risk evaluation
- Ice detection and excavation tasks
- Real-time HUD and minimap


## ⚙️ Technologies Used

- Python
- Ursina Engine
- A* Pathfinding Algorithm
- Perlin Noise
- Grid-based cost map system


## 🌕 Features

### 🗺️ Procedural Terrain
- Perlin noise-based heightmap
- Craters and hills
- Surface detailing (ambient occlusion, micro variations)


### 🤖 Autonomous Navigation
- A* pathfinding
- Cost evaluation based on:
  - Elevation
  - Slope
  - Obstacles
- Safety scoring system (mission abort if unsafe)


### 🧊 Ice Detection & Mission System
- Randomly generated ice craters
- Automatic nearest-target selection
- Robotic arm excavation simulation
- Mission completion logic


### 🧭 MiniMap & HUD
- Real-time rover tracking
- Click-based target selection
- Path visualization
- Telemetry and mission status


### 🦾 Robotic Arm Simulation
- Multi-joint arm (shoulder, elbow, wrist)
- Smooth animation transitions
- Excavation sequence simulation


## 🎮 Controls

| Key | Action |
|-----|------|
| Left Click | Select target on map |
| SPACE | Start autonomous navigation |
| H | Start ice collection tour |
| K | Manual digging |
| R | Reset system |
| ESC | Exit |


## 🧭 Algorithm Details

### A* Pathfinding
- 8-directional movement
- Heuristic: diagonal distance
- Dynamic cost map based on terrain


### Cost Map Logic
- Dangerous areas → infinite cost
- Slopes → higher cost
- Ice zones → lower cost (mission priority)


## 🎯 Purpose

This project aims to:

- Simulate real-world lunar rover missions
- Develop autonomous decision-making systems
- Model robotic exploration in extreme environments
