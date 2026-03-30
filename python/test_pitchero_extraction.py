#!/usr/bin/env python3
"""
Test Pitchero scorers extraction from /events endpoint.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.data import DataExtractor
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_sample_match():
    """Test extraction on a sample match."""
    
    print("=" * 80)
    print("TESTING PITVHERO SCORERS EXTRACTION")
    print("=" * 80)
    
    # Initialize extractor
    try:
        extractor = DataExtractor()
    except Exception as e:
        print(f"⚠️  Could not initialize with Google Sheets (expected in test): {e}")
        extractor = None
    
    # Test HTML parsing with a sample
    print("\n🧪 Test 1: HTML Parsing\n")
    
    sample_html = """
    <div style="grid-area: homeExtra; text-align: left; margin-top: 0px;">
        <div class="sc-bZQynM bsYjWC" style="gap: 5px;">
            <span class="sc-bwzfXH fzIOWS">
                <span style="font-weight: bold;">Tries: </span>
                <span class="sc-bxivhb dTuwPt" style="display: inline-block;">A Moffatt (2), </span>
                <span class="sc-bxivhb dTuwPt" style="display: inline-block;">A Yaffa, </span>
                <span class="sc-bxivhb dTuwPt" style="display: inline-block;">J Radcliffe</span>
            </span>
            <span class="sc-bwzfXH fzIOWS">
                <span style="font-weight: bold;">Conversions: </span>
                <span class="sc-bxivhb dTuwPt" style="display: inline-block;">L Maker (2)</span>
            </span>
            <span class="sc-bwzfXH fzIOWS">
                <span style="font-weight: bold;">Penalties: </span>
                <span class="sc-bxivhb dTuwPt" style="display: inline-block;">N Roberts (2)</span>
            </span>
        </div>
    </div>
    """
    
    soup = BeautifulSoup(sample_html, "html.parser")
    
    # Test the text parsing directly
    from python.data import DataExtractor
    extractor_test = DataExtractor.__new__(DataExtractor)  # Create instance without __init__
    
    # Test raw text parsing
    test_text = "Tries: A Moffatt (2), A Yaffa, J Radcliffe Conversions: L Maker (2) Penalties: N Roberts (2)"
    
    result = {}
    extractor_test._extract_scorers_from_text(test_text, result)
    
    print(f"  Input: {test_text}\n")
    print(f"  Parsed tries: {result.get('tries_scorers', {})}")
    print(f"  Parsed conversions: {result.get('conversions_scorers', {})}")
    print(f"  Parsed penalties: {result.get('penalties_scorers', {})}\n")
    
    if result.get('tries_scorers'):
        print("  ✅ Tries parsing: OK")
    else:
        print("  ❌ Tries parsing: FAILED")
    
    if result.get('conversions_scorers'):
        print("  ✅ Conversions parsing: OK")
    else:
        print("  ❌ Conversions parsing: FAILED")
    
    if result.get('penalties_scorers'):
        print("  ✅ Penalties parsing: OK")
    else:
        print("  ❌ Penalties parsing: FAILED")
    
    # Test HTML parsing from soup
    print("\n🧪 Test 2: HTML Soup Parsing\n")
    
    parsed = extractor_test._parse_pitchero_scorers_from_events_page(soup)
    print(f"  Parsed from soup: {parsed}")
    
    if parsed.get('tries_scorers'):
        print("  ✅ HTML soup parsing: OK")
    else:
        print("  ❌ HTML soup parsing: FAILED")
    
    # Test URL normalization
    print("\n🧪 Test 3: URL Normalization\n")
    
    test_urls = [
        ("https://www.egrfc.com/teams/142068/match-centre/1-15439074", 
         "https://www.egrfc.com/teams/142068/match-centre/1-15439074/events"),
        ("https://www.egrfc.com/teams/142068/match-centre/1-15439074/lineup",
         "https://www.egrfc.com/teams/142068/match-centre/1-15439074/events"),
        ("https://www.egrfc.com/teams/142068/match-centre/1-15439074/events",
         "https://www.egrfc.com/teams/142068/match-centre/1-15439074/events"),
    ]
    
    for input_url, expected in test_urls:
        result_url = extractor_test._normalise_events_url(input_url)
        status = "✅" if result_url == expected else "❌"
        print(f"  {status} {input_url}")
        print(f"     → {result_url}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_sample_match()
