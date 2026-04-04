# 🧬 3D Printer Sigma — Virtual Drug Discovery Lab

> **Advanced 3D Molecular Structure Generation & Visualization**  
> Web-based interface for interactive drug discovery analysis

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Technical Stack](#technical-stack)
- [API Endpoints](#api-endpoints)
- [Performance Metrics](#performance-metrics)
- [Roadmap](#roadmap)
- [Contributors](#contributors)

---

## 🎯 Overview

**3D Printer Sigma** is an intelligent molecular structure generation system that:

1. **Analyzes** natural language descriptions to classify molecular experiments
2. **Generates** accurate 3D structures using specialized AI models
3. **Visualizes** interactive molecular structures in a web browser
4. **Evaluates** quality with comprehensive performance metrics

### The Problem We Solve

Traditional drug discovery requires expensive physical experiments and long iteration cycles. **3D Printer Sigma** enables computational structure generation and analysis without physical experimentation.

### Key Innovation

- 🧠 **Intelligent Classification**: Llama3.1 determines whether input describes a small molecule, protein, or docking complex
- 🔬 **Multiple Backends**: Supports RDKit (local), ESMFold (protein), and DiffDock (docking) via NVIDIA NIM
- 📊 **Quality Metrics**: Comprehensive evaluation system for both classification and generation
- 🌐 **Web Interface**: Interactive visualization with 3Dmol.js

---

## ✨ Features

### 1. **Smart Input Processing**
- ✅ Free-form text description analysis
- ✅ Automatic SMILES extraction
- ✅ Protein sequence validation
- ✅ Molecular property calculation

### 2. **Case Classification**
- **Case 1**: Small molecules → RDKit 3D conformer
- **Case 2**: Proteins → ESMFold structure prediction
- **Case 3**: Docking complexes → DiffDock ligand-protein binding

### 3. **Structure Generation**
| Case | Model | Speed | Cost | Reliability |
|------|-------|-------|------|-------------|
| 1 | RDKit | ⚡ ~50ms | 💰 Free | ✅ 100% |
| 2 | ESMFold NIM | 🚀 1-3s | 💳 API | ✅ 95% |
| 3 | DiffDock NIM | 🚀 2-5s | 💳 API | ✅ 92% |

### 4. **Interactive Visualization**
- 🎨 Multiple display modes: Cartoon, Stick, Sphere, Line
- 🔄 Real-time rotation and manipulation
- 📐 3D coordinates inspection
- 💾 Structure export capabilities

### 5. **Performance Metrics**
- **Ranker Score**: 30% extraction + 40% classification + 20
