import xml.etree.ElementTree as ET
import sys

filename = "skin.AIODI/xml/DialogVideoInfo.xml"
try:
    tree = ET.parse(filename)
    print("XML is valid!")
except ET.ParseError as e:
    print(f"XML Error: {e}")
    with open(filename, 'r') as f:
        lines = f.readlines()
        if e.position:
            line_num, col = e.position
            print(f"Line {line_num}: {lines[line_num-1].strip()}")
