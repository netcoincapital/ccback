#!/usr/bin/env python3
import sys
import os
sys.path.append('/www/wwwroot/coinceeper.com/CC')
os.chdir('/www/wwwroot/coinceeper.com/CC')

from utils.price_simulator.NCCPRICE import start_simulator

if __name__ == "__main__":
    start_simulator()
