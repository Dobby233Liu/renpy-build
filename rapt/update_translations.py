#!/usr/bin/env python

import sys
import os
import re


def main():

    base = os.path.dirname(__file__)

    with open(os.path.join(base, "renpy", "launcher", "game", "androidstrings.rpy"), "w") as out:
        out.write("""
# This file contains strings used by RAPT, so the Ren'Py translation framework
# can find them. It's automatically generated by rapt/update_translations.py, and
# hence should not be changed by hand.

init python hide:
""")

        dn = os.path.join(base, "buildlib", "rapt")

        for fn in sorted(os.listdir(dn)):

            fn = os.path.join(dn, fn)

            if not fn.endswith(".py"):
                continue

            with open(fn) as f:
                data = f.read()

            for m in re.finditer(r'__\(".*?"\)', data):
                out.write("    " + m.group(0) + "\n")


if __name__ == "__main__":

    main()