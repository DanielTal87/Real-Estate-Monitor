#!/usr/bin/env python3
"""Parse pytest JUnit XML results for GitHub Actions summary."""

import xml.etree.ElementTree as ET
import sys

def main():
    try:
        tree = ET.parse('pytest-results.xml')
        root = tree.getroot()

        tests = root.attrib.get('tests', '0')
        skipped = root.attrib.get('skipped', '0')
        failures = root.attrib.get('failures', '0')
        errors = root.attrib.get('errors', '0')
        time = float(root.attrib.get('time', '0'))

        print("| Tests | Skipped | Failures | Errors | Time |")
        print("|-------|---------|----------|--------|------|")
        print(f"| {tests} | {skipped} 🦘 | {failures} ❌ | {errors} 🔥 | {time:.2f}s ⏱️ |")
        print()

    except FileNotFoundError:
        print("⚠️ Test results file not found")
    except Exception as e:
        print(f"⚠️ Could not parse test results: {e}")

if __name__ == '__main__':
    main()
