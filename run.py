#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

here = os.path.abspath(os.path.dirname(__file__))
sys.path.append(here)

from smart_qq_bot.main import patch
patch()

from oink import main
main.run()
