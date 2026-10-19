"""Pull the app's main inline <script> out of index.html so it can be checked with Node."""
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
if not scripts:
    sys.exit("no inline <script> found in " + sys.argv[1])
open(sys.argv[2], "w", encoding="utf-8").write(scripts[-1])
