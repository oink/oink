#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

here = os.path.abspath(os.path.dirname(__file__))
sys.path.append(here)

from oink import main
main.run()
