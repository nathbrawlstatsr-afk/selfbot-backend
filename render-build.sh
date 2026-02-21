#!/bin/bash
pip install --upgrade pip
pip uninstall discord.py discord.py-self -y
pip install discord.py-self==2.0.0
pip install flask flask-cors
