#!/bin/bash
cd ~/Desktop/HumanSupercapacitorOutreach
source venv/bin/activate
echo "🌇 Afternoon session – running daily outreach (max 30 emails)…"
python auto_outreach.py
echo "✅ Afternoon batch complete."
